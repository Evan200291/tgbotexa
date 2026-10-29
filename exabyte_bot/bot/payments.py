"""Payment flow: plan selection, order creation, screenshot upload FSM, admin notification."""

from __future__ import annotations

import contextlib
import re

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ..config import Settings
from ..packages import get_plan
from ..service import OpenOrderExists, Service, ServiceError
from ..strings import t
from .messages import (
    admin_order_review_kb,
    back_home_kb,
    branded,
    format_order_message,
    format_plans_message,
    order_created_kb,
    plans_kb,
    status_label,
)
from .user import send_key_card

CODE_RE = re.compile(r"^EX[A-Z2-9]{6}$")


class PaymentStates(StatesGroup):
    waiting_screenshot = State()


def build_payments_router() -> Router:
    r = Router(name="payments")

    @r.callback_query(F.data == "nav:plans")
    async def cb_plans(cb: CallbackQuery, bot: Bot) -> None:
        await cb.answer()
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await bot.send_message(
            chat_id, format_plans_message(), parse_mode="HTML", reply_markup=plans_kb()
        )

    @r.callback_query(F.data.startswith("plan:"))
    async def cb_select_plan(
        cb: CallbackQuery, svc: Service, settings: Settings, state: FSMContext, bot: Bot
    ) -> None:
        await cb.answer()
        plan_id = (cb.data or "").split(":", 1)[1]
        if get_plan(plan_id) is None:
            return
        uid = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else uid
        try:
            order = await svc.create_order(uid, plan_id)
        except OpenOrderExists as e:
            open_ord = await svc.open_order(uid)
            kb = order_created_kb(open_ord.code) if open_ord else back_home_kb()
            await bot.send_message(
                chat_id, branded(e.message()), parse_mode="HTML", reply_markup=kb
            )
            return
        except ServiceError as e:
            await bot.send_message(
                chat_id, branded(e.message()), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return

        await state.set_state(PaymentStates.waiting_screenshot)
        await state.update_data(order_code=order.code)
        await bot.send_message(
            chat_id,
            format_order_message(order, settings),
            parse_mode="HTML",
            reply_markup=order_created_kb(order.code),
        )

    @r.callback_query(F.data.startswith("ord:cancel:"))
    async def cb_cancel_order(
        cb: CallbackQuery, svc: Service, state: FSMContext, bot: Bot
    ) -> None:
        await cb.answer()
        code = (cb.data or "").split(":", 2)[2]
        if not CODE_RE.match(code):
            return
        uid = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else uid
        try:
            await svc.cancel_order(uid, code)
        except ServiceError as e:
            await bot.send_message(
                chat_id, branded(e.message()), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        await state.clear()
        await bot.send_message(
            chat_id,
            branded(t("order_cancelled", code=code)),
            parse_mode="HTML",
            reply_markup=back_home_kb(),
        )

    @r.message(F.photo)
    async def on_screenshot_photo(
        msg: Message, svc: Service, settings: Settings, state: FSMContext, bot: Bot
    ) -> None:
        if not msg.from_user or not msg.photo:
            return
        uid = msg.from_user.id
        data = await state.get_data()
        code = data.get("order_code")
        if not code:
            open_ord = await svc.open_order(uid)
            if not open_ord or open_ord.state != "pending_payment":
                await msg.answer(
                    branded(t("unknown_message")), parse_mode="HTML", reply_markup=back_home_kb()
                )
                return
            code = open_ord.code

        best_photo = msg.photo[-1]
        try:
            order = await svc.attach_screenshot(
                uid, code, best_photo.file_id, best_photo.file_unique_id
            )
        except ServiceError as e:
            await msg.answer(
                branded(e.message()), parse_mode="HTML", reply_markup=order_created_kb(code)
            )
            return

        with contextlib.suppress(Exception):
            shots_dir = settings.data_dir / "screenshots"
            shots_dir.mkdir(parents=True, exist_ok=True)
            f_info = await bot.get_file(best_photo.file_id)
            if f_info.file_path:
                await bot.download_file(f_info.file_path, destination=shots_dir / f"{code}.jpg")

        await state.clear()
        kv = await svc.get_key(uid)
        if kv is not None:
            intro = t("order_instant_key_intro", code=order.code, plan_name=order.plan.name)
            await send_key_card(
                bot, msg.chat.id, kv, svc.now(), intro=intro, svc=svc, settings=settings
            )
        else:
            await msg.answer(
                branded(t("order_received_wait", code=order.code)),
                parse_mode="HTML",
                reply_markup=back_home_kb(),
            )

        # Forward screenshot + account ID + package + key details + rich buttons to admin.
        if settings.admin_ids:
            uname = f"@{msg.from_user.username}" if msg.from_user.username else "-"
            caption = branded(
                t(
                    "adm_new_order_caption",
                    code=order.code,
                    user_id=uid,
                    username=uname,
                    plan_name=order.plan.name,
                    days=order.plan.days,
                    amount=order.amount_text,
                    key_email=kv.email if kv else "-",
                    key_status=status_label(kv.status) if kv else "-",
                )
            )
            await bot.send_photo(
                chat_id=settings.admin_ids[0],
                photo=best_photo.file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=admin_order_review_kb(
                    order.code, uid, key_enabled=kv.enabled if kv else True
                ),
            )

    @r.message(StateFilter(PaymentStates.waiting_screenshot))
    async def on_non_photo_while_waiting(msg: Message, state: FSMContext) -> None:
        data = await state.get_data()
        code = data.get("order_code", "")
        await msg.answer(
            branded(t("order_send_photo_prompt", code=code)),
            parse_mode="HTML",
            reply_markup=order_created_kb(code) if code else back_home_kb(),
        )

    return r

