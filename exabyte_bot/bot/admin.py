"""Admin panel (/admin): payment approvals, stats, user management, broadcast, maintenance, CSV."""

from __future__ import annotations

import asyncio
from html import escape
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import BaseFilter, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ..config import Settings
from ..service import KeyView, Service, ServiceError
from ..strings import t
from ..util import fmt_bytes, fmt_date, fmt_mmk
from ..xui import PanelUnavailable
from .messages import admin_order_review_kb, branded
from .payments import CODE_RE
from .user import send_key_card


class AdminOnly(BaseFilter):
    """Hard gate: only configured ADMIN_IDS may trigger any admin handler."""

    async def __call__(self, event: Message | CallbackQuery, settings: Settings) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and settings.is_admin(user.id))


class AdminStates(StatesGroup):
    reject_reason = State()
    find_user = State()
    broadcast_text = State()


async def queue_approval_retry(svc: Service, code: str, admin_id: int) -> None:
    raw = await svc.db.get_setting("retry_approvals", "") or ""
    items = {x for x in raw.split(",") if x}
    items.add(f"{code}:{admin_id}")
    await svc.db.set_setting("retry_approvals", ",".join(sorted(items)))


async def _admin_menu_kb(svc: Service) -> InlineKeyboardMarkup:
    pend = len(await svc.pending_orders())
    maint = "ON" if await svc.is_maintenance() else "OFF"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_adm_pending", n=pend), callback_data="adm:pend")],
            [
                InlineKeyboardButton(text=t("btn_adm_stats"), callback_data="adm:stats"),
                InlineKeyboardButton(text=t("btn_adm_find"), callback_data="adm:find"),
            ],
            [
                InlineKeyboardButton(text=t("btn_adm_broadcast"), callback_data="adm:bcast"),
                InlineKeyboardButton(
                    text=t("btn_adm_maint", state=maint), callback_data="adm:maint"
                ),
            ],
            [InlineKeyboardButton(text=t("btn_adm_csv"), callback_data="adm:csv")],
        ]
    )


def _back_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("back"), callback_data="adm:menu")]]
    )


def _user_manage_kb(uid: int, banned: bool) -> InlineKeyboardMarkup:
    ban_btn = (
        InlineKeyboardButton(text="🔓 Unban", callback_data=f"adm:uact:unban:{uid}")
        if banned
        else InlineKeyboardButton(text="🚫 Ban", callback_data=f"adm:uact:ban:{uid}")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+7 ရက်", callback_data=f"adm:uact:add7d:{uid}"),
                InlineKeyboardButton(text="+30 ရက်", callback_data=f"adm:uact:add30d:{uid}"),
                InlineKeyboardButton(text="+5 GB", callback_data=f"adm:uact:add5g:{uid}"),
            ],
            [
                InlineKeyboardButton(text="Grant 1လ", callback_data=f"adm:uact:grant:{uid}:vpn_1m"),
                InlineKeyboardButton(text="Grant 3လ", callback_data=f"adm:uact:grant:{uid}:vpn_3m"),
                InlineKeyboardButton(text="Grant 6လ", callback_data=f"adm:uact:grant:{uid}:vpn_6m"),
            ],
            [
                InlineKeyboardButton(text="🗑️ Key ဖျက်မည်", callback_data=f"adm:uact:revoke:{uid}"),
                ban_btn,
            ],
            [InlineKeyboardButton(text=t("back"), callback_data="adm:menu")],
        ]
    )


def _format_user_card(info: dict[str, Any]) -> str:
    kv: KeyView | None = info["key"]
    if kv is None:
        ksum = "မရှိပါ"
    else:
        quota = "Unlimited" if kv.unlimited else fmt_bytes(kv.quota_bytes)
        ksum = (
            f"{kv.kind} ({kv.status}) • {fmt_bytes(kv.used_bytes)}/{quota} • "
            f"exp {fmt_date(kv.expiry_ms)}"
        )
    return branded(
        t(
            "adm_user_card",
            user_id=info["user_id"],
            username=escape(str(info["username"])),
            banned="Yes" if info["banned"] else "No",
            key_summary=ksum,
            order_count=info["order_count"],
        )
    )


def build_admin_router() -> Router:
    r = Router(name="admin")
    r.message.filter(AdminOnly())
    r.callback_query.filter(AdminOnly())

    @r.message(Command("admin"))
    async def cmd_admin(msg: Message, svc: Service, state: FSMContext) -> None:
        await state.clear()
        await msg.answer(
            branded(t("admin_menu")), parse_mode="HTML", reply_markup=await _admin_menu_kb(svc)
        )

    @r.callback_query(F.data == "adm:menu")
    async def cb_admin_menu(
        cb: CallbackQuery, svc: Service, state: FSMContext, bot: Bot
    ) -> None:
        await state.clear()
        await cb.answer()
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await bot.send_message(
            chat_id,
            branded(t("admin_menu")),
            parse_mode="HTML",
            reply_markup=await _admin_menu_kb(svc),
        )

    @r.callback_query(F.data == "adm:pend")
    async def cb_pending(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        await cb.answer()
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        orders = await svc.pending_orders()
        if not orders:
            await bot.send_message(
                chat_id, branded(t("adm_no_pending")), parse_mode="HTML", reply_markup=_back_admin_kb()
            )
            return
        for o in orders:
            caption = branded(
                t(
                    "adm_new_order_caption",
                    code=o.code,
                    user_id=o.user_id,
                    username="-",
                    plan_name=o.plan.name,
                    amount=o.amount_text,
                )
            )
            if o.screenshot_file_id:
                await bot.send_photo(
                    chat_id,
                    photo=o.screenshot_file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=admin_order_review_kb(o.code),
                )
            else:
                await bot.send_message(
                    chat_id,
                    caption,
                    parse_mode="HTML",
                    reply_markup=admin_order_review_kb(o.code),
                )

    @r.callback_query(F.data.startswith("adm:ap:"))
    async def cb_approve(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        code = (cb.data or "").split(":", 2)[2]
        if not CODE_RE.match(code):
            await cb.answer()
            return
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        try:
            res = await svc.approve_order(code, cb.from_user.id)
        except PanelUnavailable:
            await queue_approval_retry(svc, code, cb.from_user.id)
            await cb.answer(t("panel_down"), show_alert=True)
            await bot.send_message(chat_id, branded(t("panel_down")), parse_mode="HTML")
            return
        except ServiceError as e:
            await cb.answer(e.message(), show_alert=True)
            return

        await cb.answer(t("adm_action_done"))
        if not res.already and res.key is not None:
            try:
                await send_key_card(
                    bot, res.order.user_id, res.key, svc.now(), intro=t("order_approved")
                )
            except TelegramForbiddenError:
                await svc.mark_blocked(res.order.user_id)
            await bot.send_message(
                chat_id,
                branded(f"{t('adm_action_done')} (<code>{code}</code>)"),
                parse_mode="HTML",
                reply_markup=_back_admin_kb(),
            )

    @r.callback_query(F.data.startswith("adm:rj:"))
    async def cb_reject_prompt(
        cb: CallbackQuery, state: FSMContext, bot: Bot
    ) -> None:
        code = (cb.data or "").split(":", 2)[2]
        if not CODE_RE.match(code):
            await cb.answer()
            return
        await cb.answer()
        await state.set_state(AdminStates.reject_reason)
        await state.update_data(reject_code=code)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t("btn_skip_reason"), callback_data=f"adm:rjskip:{code}")],
                [InlineKeyboardButton(text=t("back"), callback_data="adm:menu")],
            ]
        )
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await bot.send_message(
            chat_id,
            branded(t("adm_ask_reject_reason", code=code)),
            parse_mode="HTML",
            reply_markup=kb,
        )

    @r.callback_query(F.data.startswith("adm:rjskip:"))
    async def cb_reject_skip(
        cb: CallbackQuery, svc: Service, state: FSMContext, bot: Bot
    ) -> None:
        code = (cb.data or "").split(":", 2)[2]
        await state.clear()
        await cb.answer()
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await _finish_reject(svc, bot, chat_id, cb.from_user.id, code, None)

    @r.message(StateFilter(AdminStates.reject_reason))
    async def on_reject_reason(
        msg: Message, svc: Service, state: FSMContext, bot: Bot
    ) -> None:
        data = await state.get_data()
        code = data.get("reject_code", "")
        await state.clear()
        if not msg.from_user or not code:
            return
        await _finish_reject(svc, bot, msg.chat.id, msg.from_user.id, code, (msg.text or "").strip() or None)

    @r.callback_query(F.data == "adm:stats")
    async def cb_stats(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        await cb.answer()
        st = await svc.stats()
        body = t(
            "adm_stats_body",
            total_users=st["total_users"],
            active_paid=st["active_paid"],
            active_trials=st["active_trials"],
            pending_orders=st["pending_orders"],
            today_revenue=fmt_mmk(st["today_revenue"]),
            month_revenue=fmt_mmk(st["month_revenue"]),
        )
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await bot.send_message(
            chat_id, branded(body), parse_mode="HTML", reply_markup=_back_admin_kb()
        )

    @r.callback_query(F.data == "adm:find")
    async def cb_find_prompt(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
        await cb.answer()
        await state.set_state(AdminStates.find_user)
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await bot.send_message(
            chat_id, branded(t("adm_ask_find")), parse_mode="HTML", reply_markup=_back_admin_kb()
        )

    @r.message(StateFilter(AdminStates.find_user))
    async def on_find_query(msg: Message, svc: Service, state: FSMContext) -> None:
        await state.clear()
        info = await svc.find_user(msg.text or "")
        if not info:
            await msg.answer(
                branded(t("adm_user_not_found")), parse_mode="HTML", reply_markup=_back_admin_kb()
            )
            return
        await msg.answer(
            _format_user_card(info),
            parse_mode="HTML",
            reply_markup=_user_manage_kb(info["user_id"], info["banned"]),
        )

    @r.callback_query(F.data.startswith("adm:uact:"))
    async def cb_user_action(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        parts = (cb.data or "").split(":")
        if len(parts) < 4 or not parts[3].isdigit():
            await cb.answer()
            return
        action, uid = parts[2], int(parts[3])
        admin_id = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else admin_id
        try:
            if action == "add7d":
                await svc.admin_adjust_key(admin_id, uid, add_days=7)
            elif action == "add30d":
                await svc.admin_adjust_key(admin_id, uid, add_days=30)
            elif action == "add5g":
                await svc.admin_adjust_key(admin_id, uid, add_gb=5)
            elif action == "grant" and len(parts) == 5:
                kv = await svc.grant_plan(admin_id, uid, parts[4])
                try:
                    await send_key_card(bot, uid, kv, svc.now(), intro=t("order_approved"))
                except TelegramForbiddenError:
                    await svc.mark_blocked(uid)
            elif action == "revoke":
                await svc.admin_revoke_key(admin_id, uid)
            elif action == "ban":
                await svc.admin_set_banned(admin_id, uid, True)
            elif action == "unban":
                await svc.admin_set_banned(admin_id, uid, False)
            else:
                await cb.answer()
                return
        except (ServiceError, PanelUnavailable) as e:
            msg_txt = t("panel_down") if isinstance(e, PanelUnavailable) else e.message()
            await cb.answer(msg_txt, show_alert=True)
            return

        await cb.answer(t("adm_action_done"))
        info = await svc.find_user(str(uid))
        if info:
            await bot.send_message(
                chat_id,
                _format_user_card(info),
                parse_mode="HTML",
                reply_markup=_user_manage_kb(uid, info["banned"]),
            )

    @r.callback_query(F.data == "adm:maint")
    async def cb_toggle_maint(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        await svc.toggle_maintenance(cb.from_user.id)
        await cb.answer(t("adm_action_done"))
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await bot.send_message(
            chat_id,
            branded(t("admin_menu")),
            parse_mode="HTML",
            reply_markup=await _admin_menu_kb(svc),
        )

    @r.callback_query(F.data == "adm:csv")
    async def cb_export_csv(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        await cb.answer()
        data = await svc.export_orders_csv(cb.from_user.id)
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        doc = BufferedInputFile(data, filename="exabyte-orders.csv")
        await bot.send_document(
            chat_id, document=doc, caption=branded(t("adm_action_done")), parse_mode="HTML"
        )

    @r.callback_query(F.data == "adm:bcast")
    async def cb_bcast_prompt(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
        await cb.answer()
        await state.set_state(AdminStates.broadcast_text)
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await bot.send_message(
            chat_id, branded(t("adm_ask_broadcast")), parse_mode="HTML", reply_markup=_back_admin_kb()
        )

    @r.message(StateFilter(AdminStates.broadcast_text))
    async def on_bcast_preview(msg: Message, svc: Service, state: FSMContext) -> None:
        text = (msg.text or "").strip()
        if not text:
            return
        await state.update_data(bcast_text=text)
        recipients = await svc.broadcast_recipients()
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t("btn_adm_broadcast_confirm"), callback_data="adm:bcast_go")],
                [InlineKeyboardButton(text=t("cancel"), callback_data="adm:menu")],
            ]
        )
        preview = branded(t("adm_broadcast_preview", count=len(recipients), text=escape(text)))
        await msg.answer(preview, parse_mode="HTML", reply_markup=kb)

    @r.callback_query(F.data == "adm:bcast_go")
    async def cb_bcast_execute(
        cb: CallbackQuery, svc: Service, state: FSMContext, bot: Bot
    ) -> None:
        data = await state.get_data()
        text = data.get("bcast_text", "")
        await state.clear()
        await cb.answer()
        if not text:
            return
        recipients = await svc.broadcast_recipients()
        ok_cnt, fail_cnt = 0, 0
        payload = branded(escape(text))
        for uid in recipients:
            try:
                await bot.send_message(uid, payload, parse_mode="HTML")
                ok_cnt += 1
            except TelegramForbiddenError:
                await svc.mark_blocked(uid)
                fail_cnt += 1
            except Exception:
                fail_cnt += 1
            await asyncio.sleep(0.04)  # <= 25 messages/sec
        await svc.db.audit(
            cb.from_user.id,
            "broadcast",
            None,
            {"ok": ok_cnt, "failed": fail_cnt},
            int(svc.now().timestamp() * 1000),
        )
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await bot.send_message(
            chat_id,
            branded(t("adm_broadcast_done", ok=ok_cnt, failed=fail_cnt)),
            parse_mode="HTML",
            reply_markup=_back_admin_kb(),
        )

    return r


async def _finish_reject(
    svc: Service, bot: Bot, admin_chat_id: int, admin_id: int, code: str, reason: str | None
) -> None:
    try:
        res = await svc.reject_order(code, admin_id, reason)
    except ServiceError as e:
        await bot.send_message(
            admin_chat_id, branded(e.message()), parse_mode="HTML", reply_markup=_back_admin_kb()
        )
        return
    if not res.already:
        user_msg = (
            t("order_rejected_reason", reason=escape(reason))
            if reason
            else t("order_rejected")
        )
        try:
            await bot.send_message(res.order.user_id, branded(user_msg), parse_mode="HTML")
        except TelegramForbiddenError:
            await svc.mark_blocked(res.order.user_id)
    await bot.send_message(
        admin_chat_id,
        branded(f"{t('adm_action_done')} (<code>{code}</code>)"),
        parse_mode="HTML",
        reply_markup=_back_admin_kb(),
    )
