"""Customer-facing bot handlers: /start, /help, /myid, trial, key, usage, guides, support."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from .. import packages as P
from ..config import Settings
from ..service import KeyView, Service, ServiceError
from ..strings import t
from ..util import fmt_bytes
from ..xui import PanelUnavailable
from .messages import (
    back_home_kb,
    branded,
    format_key_message,
    format_plans_message,
    format_usage_message,
    guide_menu_kb,
    key_kb,
    key_server_switch_kb,
    main_menu_kb,
    plans_kb,
    reply_menu_kb,
    support_kb,
)

GUIDE_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "guides"
WELCOME_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "welcome"
_GUIDE_FILE_IDS: dict[int, str] = {}


async def send_welcome(bot: Bot, chat_id: int, svc: Service, settings: Settings,
                       user_id: int) -> None:
    res = await svc.get_reseller_info(user_id)
    body = t("welcome_body", store=escape(settings.store_name))
    if res["is_reseller"]:
        body += "\n" + t("reseller_wallet_banner", balance=res["balance_text"])
    animation = WELCOME_ASSETS_DIR / ("outlineplus.gif" if settings.required_channel else "exabyte.gif")
    await bot.send_animation(chat_id, FSInputFile(animation), caption=branded(body),
                             parse_mode="HTML", reply_markup=main_menu_kb(settings))
    await bot.send_message(chat_id, "⬇️ အောက်ပါ မီနူးကိုလည်း အသုံးပြုနိုင်ပါသည်။",
                           reply_markup=reply_menu_kb(settings))


async def send_outline_guide(bot: Bot, chat_id: int, settings: Settings, svc: Service) -> None:
    image = GUIDE_ASSETS_DIR / "outline-quickstart.jpg"
    if image.is_file():
        cached = _GUIDE_FILE_IDS.get(bot.id) or await svc.db.get_setting(f"guide_quickstart_{bot.id}")
        try:
            sent = await bot.send_photo(chat_id, cached or FSInputFile(image),
                caption=t("guide_simple"), parse_mode="HTML", reply_markup=guide_menu_kb(settings))
        except TelegramBadRequest:
            sent = await bot.send_photo(chat_id, FSInputFile(image),
                caption=t("guide_simple"), parse_mode="HTML", reply_markup=guide_menu_kb(settings))
        if sent.photo:
            file_id = sent.photo[-1].file_id
            _GUIDE_FILE_IDS[bot.id] = file_id
            await svc.db.set_setting(f"guide_quickstart_{bot.id}", file_id)
    else:
        await bot.send_message(chat_id, t("guide_simple"), parse_mode="HTML",
            reply_markup=guide_menu_kb(settings))


async def send_key_card(
    bot: Bot,
    chat_id: int,
    kv: KeyView,
    now: datetime,
    *,
    intro: str | None = None,
    svc: Service | None = None,
    settings: Settings | None = None,
) -> None:
    servers = await svc.get_key_links(kv.user_id, kv.id) if svc is not None else None
    sub_url = (
        f"https://{settings.bot_domain}/sub/{kv.sub_id}"
        if (settings and settings.bot_domain and kv.sub_id)
        else None
    )
    caption = format_key_message(
        kv, now, intro=intro, extra_servers=servers, sub_url=sub_url
    )
    await bot.send_message(
        chat_id=chat_id, text=caption, parse_mode="HTML", reply_markup=key_kb(kv)
    )


def build_user_router() -> Router:
    r = Router(name="user")

    @r.message(Command("start"))
    async def cmd_start(
        msg: Message, svc: Service, settings: Settings, state: FSMContext, bot: Bot
    ) -> None:
        await state.clear()
        uid = msg.from_user.id if msg.from_user else msg.chat.id
        await send_welcome(bot, msg.chat.id, svc, settings, uid)

    @r.message(F.text.in_({"start", "Start", "START", t("btn_home")}))
    async def msg_home(
        msg: Message, svc: Service, settings: Settings, state: FSMContext, bot: Bot
    ) -> None:
        await state.clear()
        uid = msg.from_user.id if msg.from_user else msg.chat.id
        await send_welcome(bot, msg.chat.id, svc, settings, uid)

    @r.message(Command("trial"))
    @r.message(F.text == t("btn_trial"))
    async def msg_trial(msg: Message, svc: Service, settings: Settings, bot: Bot) -> None:
        uid = msg.from_user.id if msg.from_user else msg.chat.id
        try:
            kv = await svc.claim_trial(uid, is_admin=settings.is_admin(uid))
        except ServiceError as e:
            await msg.answer(
                branded(e.message()), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        except PanelUnavailable:
            await msg.answer(
                branded(t("panel_down")), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        intro = t("trial_ok", gb=P.TRIAL_QUOTA_GB, days=P.TRIAL_DAYS)
        await send_key_card(bot, msg.chat.id, kv, svc.now(), intro=intro, svc=svc, settings=settings)

    @r.message(F.text == t("btn_buy"))
    async def msg_plans(msg: Message, svc: Service) -> None:
        uid = msg.from_user.id if msg.from_user else msg.chat.id
        res = await svc.get_reseller_info(uid)
        await msg.answer(
            format_plans_message(is_reseller=res["is_reseller"], balance_mmk=res["balance_mmk"]),
            parse_mode="HTML",
            reply_markup=plans_kb(is_reseller=res["is_reseller"]),
        )

    @r.message(Command("key"))
    @r.message(F.text == t("btn_my_key"))
    async def msg_my_key(msg: Message, svc: Service, settings: Settings, bot: Bot) -> None:
        uid = msg.from_user.id if msg.from_user else msg.chat.id
        keys = await svc.list_keys(uid)
        if not keys:
            await msg.answer(
                branded(t("no_key")), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        for kv in keys:
            await send_key_card(bot, msg.chat.id, kv, svc.now(), svc=svc, settings=settings)

    @r.message(Command("guide"))
    @r.message(F.text == t("btn_guide"))
    async def msg_guide(msg: Message, bot: Bot, settings: Settings, svc: Service) -> None:
        await send_outline_guide(bot, msg.chat.id, settings, svc)

    @r.message(F.text == t("btn_support"))
    async def msg_support(msg: Message, settings: Settings) -> None:
        await msg.answer(
            branded(t("support_body")), parse_mode="HTML", reply_markup=support_kb(settings)
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
    async def cb_home(
        cb: CallbackQuery, svc: Service, settings: Settings, state: FSMContext
    ) -> None:
        await state.clear()
        await cb.answer()
        if cb.message:
            res = await svc.get_reseller_info(cb.from_user.id)
            body = t("welcome_body", store=escape(settings.store_name))
            if res["is_reseller"]:
                body += "\n" + t("reseller_wallet_banner", balance=res["balance_text"])
            await cb.message.answer(
                branded(body), parse_mode="HTML", reply_markup=main_menu_kb(settings)
            )

    @r.callback_query(F.data == "nav:trial")
    async def cb_trial(cb: CallbackQuery, svc: Service, settings: Settings, bot: Bot) -> None:
        await cb.answer()
        uid = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else uid
        try:
            kv = await svc.claim_trial(uid, is_admin=settings.is_admin(uid))
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
        await send_key_card(bot, chat_id, kv, svc.now(), intro=intro, svc=svc, settings=settings)

    @r.callback_query(F.data == "nav:key")
    async def cb_my_key(cb: CallbackQuery, svc: Service, settings: Settings, bot: Bot) -> None:
        await cb.answer()
        uid = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else uid
        keys = await svc.list_keys(uid)
        if not keys:
            await bot.send_message(
                chat_id, branded(t("no_key")), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        for kv in keys:
            await send_key_card(bot, chat_id, kv, svc.now(), svc=svc, settings=settings)

    @r.callback_query(F.data.startswith("key:srvmenu:"))
    async def cb_key_server_menu(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        await cb.answer()
        uid = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else uid
        try:
            key_id = int((cb.data or "").split(":", 2)[2])
        except (IndexError, ValueError):
            return
        kv = await svc.get_key(uid, key_id)
        if kv is None:
            return
        if not kv.multi_server:
            await bot.send_message(
                chat_id,
                branded(t("server_switch_not_allowed")),
                parse_mode="HTML",
                reply_markup=back_home_kb(),
            )
            return
        panels = [p for p in await svc.list_panels() if p["enabled"]]
        await bot.send_message(
            chat_id,
            branded(
                t(
                    "server_switch_menu",
                    email=kv.email,
                    remaining=fmt_bytes(kv.remaining_bytes),
                )
            ),
            parse_mode="HTML",
            reply_markup=key_server_switch_kb(kv.id, panels, kv.panel_id),
        )

    @r.callback_query(F.data.startswith("key:srvset:"))
    async def cb_key_server_set(
        cb: CallbackQuery, svc: Service, settings: Settings, bot: Bot
    ) -> None:
        await cb.answer()
        uid = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else uid
        parts = (cb.data or "").split(":")
        if len(parts) != 4:
            return
        try:
            key_id = int(parts[2])
            panel_id = int(parts[3])
        except ValueError:
            return
        try:
            kv = await svc.switch_key_server(uid, key_id, panel_id)
        except ServiceError as e:
            await bot.send_message(
                chat_id, branded(e.message()), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        panels = await svc.list_panels()
        srv_name = next((str(p["name"]) for p in panels if int(p["id"]) == panel_id), "Server")  # type: ignore[arg-type]
        intro = t(
            "server_switched_ok",
            server_name=srv_name,
            remaining=fmt_bytes(kv.remaining_bytes),
        )
        await send_key_card(bot, chat_id, kv, svc.now(), intro=intro, svc=svc, settings=settings)

    @r.callback_query(F.data == "key:regen")
    async def cb_regen_key(cb: CallbackQuery, svc: Service, settings: Settings, bot: Bot) -> None:
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
        await send_key_card(
            bot, chat_id, kv, svc.now(), intro=t("regen_ok"), svc=svc, settings=settings
        )

    @r.callback_query(F.data == "nav:usage")
    async def cb_usage(cb: CallbackQuery, svc: Service, bot: Bot) -> None:
        await cb.answer()
        uid = cb.from_user.id
        chat_id = cb.message.chat.id if cb.message else uid
        keys = await svc.list_keys(uid)
        if not keys:
            await bot.send_message(
                chat_id, branded(t("no_key")), parse_mode="HTML", reply_markup=back_home_kb()
            )
            return
        for kv in keys:
            await bot.send_message(
                chat_id,
                format_usage_message(kv, svc.now()),
                parse_mode="HTML",
                reply_markup=back_home_kb(),
            )

    @r.callback_query(F.data == "nav:guide")
    @r.callback_query(F.data.startswith("guide:"))
    async def cb_guide_menu(cb: CallbackQuery, bot: Bot, settings: Settings, svc: Service) -> None:
        await cb.answer()
        await send_outline_guide(bot, cb.message.chat.id if cb.message else cb.from_user.id, settings, svc)

    @r.callback_query(F.data == "download:apk")
    async def cb_apk(cb: CallbackQuery, bot: Bot) -> None:
        await cb.answer()
        from ..downloads import APK_PATH, APK_URL
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        if APK_PATH.is_file():
            await bot.send_document(chat_id, FSInputFile(APK_PATH), caption=t("apk_caption"))
        else:
            await bot.send_message(chat_id, t("apk_caption") + "\n" + APK_URL)

    @r.callback_query(F.data == "membership:check")
    async def cb_joined(cb: CallbackQuery, settings: Settings, state: FSMContext) -> None:
        await state.clear()
        await cb.answer(t("join_ok"))
        if cb.message:
            await cb.message.answer(t("welcome_body", store=escape(settings.store_name)),
                parse_mode="HTML", reply_markup=reply_menu_kb(settings))

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
            branded(t("unknown_message")), parse_mode="HTML", reply_markup=reply_menu_kb(settings)
        )

    @r.callback_query()
    async def unknown_callback(cb: CallbackQuery) -> None:
        await cb.answer()

    return r

