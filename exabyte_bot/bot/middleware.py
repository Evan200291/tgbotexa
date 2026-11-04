"""Outer middleware: user upsert, anti-spam rate limiting, ban check, maintenance gate."""

from __future__ import annotations

import asyncio
import html
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)

from ..config import Settings
from ..service import Service
from ..strings import t
from .messages import branded

log = logging.getLogger(__name__)


async def notify_admins_new_user(
    bot: Bot,
    svc: Service,
    settings: Settings,
    tg_id: int,
    full_name: str | None,
    username: str | None,
) -> None:
    if not settings.admin_ids or settings.is_admin(tg_id):
        return
    try:
        total_row = await svc.db.fetchone("SELECT COUNT(*) AS c FROM users")
        total = int(total_row["c"]) if total_row else 1
        uname = f"@{username}" if username else "မရှိပါ (None)"
        name = html.escape(full_name or "အမည်မသိ")
        now_str = svc.now().strftime("%Y-%m-%d %I:%M %p")
        text = branded(
            f"🔔 <b>အသုံးပြုသူအသစ် စတင်အသုံးပြုပါသည်!</b> (New User Alert)\n\n"
            f"👤 <b>အမည်:</b> {name}\n"
            f"🆔 <b>User ID:</b> <code>{tg_id}</code>\n"
            f"📱 <b>Username:</b> {uname}\n"
            f"👥 <b>စုစုပေါင်းအသုံးပြုသူ:</b> {total} ယောက်\n"
            f"⏰ <b>အချိန်:</b> {now_str}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👤 Profile ကြည့်ရန်",
                        url=f"tg://user?id={tg_id}",
                    )
                ]
            ]
        )
        for aid in settings.admin_ids:
            try:
                await bot.send_message(
                    chat_id=aid,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
            except Exception as ex:
                log.warning("Failed to alert admin %s about new user %s: %s", aid, tg_id, ex)
    except Exception as err:
        log.warning("Error in notify_admins_new_user: %s", err)


class GuardMiddleware(BaseMiddleware):
    """Applies to Message and CallbackQuery updates."""

    def __init__(self, svc: Service, settings: Settings, *, min_interval_sec: float = 0.35):
        self.svc = svc
        self.settings = settings
        self.min_interval_sec = min_interval_sec
        self._last_ts: defaultdict[int, float] = defaultdict(float)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        uid = user.id
        is_admin = self.settings.is_admin(uid)

        # Rate-limit rapid taps from non-admins.
        if not is_admin and self.min_interval_sec > 0:
            now = time.monotonic()
            if now - self._last_ts[uid] < self.min_interval_sec:
                await _reply(event, branded(t("rate_limited")))
                return None
            self._last_ts[uid] = now

        is_new = await self.svc.ensure_user(uid, user.username, user.first_name)
        if is_new and not is_admin and self.settings.admin_ids:
            b: Bot | None = data.get("bot") or getattr(event, "bot", None)
            if b is not None:
                asyncio.create_task(
                    notify_admins_new_user(
                        b,
                        self.svc,
                        self.settings,
                        uid,
                        user.full_name,
                        user.username,
                    )
                )

        if not is_admin:
            if await self.svc.is_banned(uid):
                await _reply(event, branded(t("banned")))
                return None
            if await self.svc.is_maintenance():
                await _reply(event, branded(t("maintenance")))
                return None

        data["svc"] = self.svc
        data["settings"] = self.settings
        return await handler(event, data)


async def _reply(event: TelegramObject, text: str) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer(t("rate_limited") if "ခဏစောင့်" in text else text[:180], show_alert=False)
        if event.message:
            await event.message.answer(text, parse_mode="HTML")
    elif isinstance(event, Message):
        await event.answer(text, parse_mode="HTML")

