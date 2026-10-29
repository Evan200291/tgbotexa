"""Outer middleware: user upsert, anti-spam rate limiting, ban check, maintenance gate."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from ..config import Settings
from ..service import Service
from ..strings import t
from .messages import branded


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

        await self.svc.ensure_user(uid, user.username, user.first_name)

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
