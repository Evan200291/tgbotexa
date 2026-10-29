"""Customer-facing bot handlers: /start, /help, /myid, trial, key, usage, guides, support."""

from __future__ import annotations

from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from .. import packages as P
from ..config import Settings
from ..service import KeyView, Service, ServiceError
from ..strings import t
from ..xui import PanelUnavailable, qr_png
from .messages import (
    back_home_kb,
    branded,
    format_key_message,
    format_usage_message,
    guide_detail_kb,
    guide_menu_kb,
    key_kb,
    main_menu_kb,
    support_kb,
)

GUIDE_KEYS = {
    "android": "guide_android",
    "ios": "guide_ios",
    "desktop": "guide_desktop",
}


async def send_key_card(
    bot: Bot, chat_id: int, kv: KeyView, now: datetime, *, intro: str | None = None
) -> None:
    caption = format_key_message(kv, now, intro=intro)
    photo = BufferedInputFile(qr_png(kv.link), filename="exabyte-key.png")
    await bot.send_photo(
        chat_id=chat_id, photo=photo, caption=caption, parse_mode="HTML", reply_markup=key_kb(kv)
    )


def build_user_router() -> Router:
    r = Router(name="user")

    @r.message(Command("start"))
    async def cmd_start(msg: Message, settings: Settings, state: FSMContext) -> None:
        await state.clear()
        await msg.answer(
            branded(t("welcome_body")), parse_mode="HTML", reply_markup=main_menu_kb(settings)
        )

    @r.message(Command("help"))
    async def cmd_help(msg: Message, settings: Settings) -> None:
        await msg.answer(
            branded(t("help_body")), parse_mode="HTML", reply_markup=main_menu_kb(settings)
        )

    @r.message(Command("myid"))
    async def cmd_myid(msg: Message) -> None:
        uid = msg.from_user.id if msg.from_user else 0
        await msg.answer(
            branded(t("myid_body", user_id=uid)), parse_mode="HTML", reply_markup=back_home_kb()
        )

    @r.callback_query(F.data == "nav:home")
    async def cb_home(cb: CallbackQuery, settings: Settings, state: FSMContext) -> None:
        await state.clear()
        await cb.answer()
        if cb.message:
            await cb.message.answer(
                branded(t("welcome_body")), parse_mode="HTML", reply_markup=main_menu_kb(settings)
            )

    @r.callback_query(F.data == "nav:trial")
    async def cb_trial(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        await cb.answer()
        uid = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else uid
        try:
            kv = await svc.claim_trial(uid)
        except ServiceError as e:
            await bot.send_message(
                chat_id, branded(e.message()), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        except PanelUnavailable:
            await bot.send_message(
                chat_id, branded(t("panel_down")), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        intro = t("trial_ok", gb=P.TRIAL_QUOTA_GB, days=P.TRIAL_DAYS)
        await send_key_card(bot, chat_id, kv, svc.now(), intro=intro)

    @r.callback_query(F.data == "nav:key")
    async def cb_my_key(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        await cb.answer()
        uid = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else uid
        kv = await svc.get_key(uid)
        if kv is None:
            await bot.send_message(
                chat_id, branded(t("no_key")), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        await send_key_card(bot, chat_id, kv, svc.now())

    @r.callback_query(F.data == "key:regen")
    async def cb_regen_key(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        await cb.answer()
        uid = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else uid
        try:
            kv = await svc.regenerate_key(uid)
        except ServiceError as e:
            await bot.send_message(
                chat_id, branded(e.message()), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        except PanelUnavailable:
            await bot.send_message(
                chat_id, branded(t("panel_down")), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        await send_key_card(bot, chat_id, kv, svc.now(), intro=t("regen_ok"))

    @r.callback_query(F.data == "nav:usage")
    async def cb_usage(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        await cb.answer()
        uid = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else uid
        kv = await svc.get_key(uid)
        if kv is None:
            await bot.send_message(
                chat_id, branded(t("no_key")), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        await bot.send_message(
            chat_id,
            format_usage_message(kv, svc.now()),
            parse_mode="HTML",
            reply_markup=back_home_kb(),
        )

    @r.callback_query(F.data == "nav:guide")
    async def cb_guide_menu(cb: CallbackQuery, bot: Bot) -> None:
        await cb.answer()
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await bot.send_message(
            chat_id, branded(t("guide_menu")), parse_mode="HTML", reply_markup=guide_menu_kb()
        )

    @r.callback_query(F.data.startswith("guide:"))
    async def cb_guide_platform(cb: CallbackQuery, bot: Bot) -> None:
        await cb.answer()
        platform = (cb.data or "").split(":", 1)[1]
        str_key = GUIDE_KEYS.get(platform)
        if not str_key:
            return
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await bot.send_message(
            chat_id, branded(t(str_key)), parse_mode="HTML", reply_markup=guide_detail_kb()
        )

    @r.callback_query(F.data == "nav:support")
    async def cb_support(cb: CallbackQuery, settings: Settings, bot: Bot) -> None:
        await cb.answer()
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        await bot.send_message(
            chat_id,
            branded(t("support_body")),
            parse_mode="HTML",
            reply_markup=support_kb(settings),
        )

    return r


def build_fallback_router() -> Router:
    """Registered last so unknown messages and stale callbacks never fail silently."""
    r = Router(name="fallback")

    @r.message(StateFilter(None))
    async def unknown_message(msg: Message, settings: Settings) -> None:
        await msg.answer(
            branded(t("unknown_message")), parse_mode="HTML", reply_markup=main_menu_kb(settings)
        )

    @r.callback_query()
    async def unknown_callback(cb: CallbackQuery) -> None:
        await cb.answer()

    return r
