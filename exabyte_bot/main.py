"""Application wiring and entrypoint: Dispatcher, routers, background jobs, startup/shutdown."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .bot.admin import build_admin_router
from .bot.middleware import GuardMiddleware
from .bot.payments import build_payments_router
from .bot.user import build_fallback_router, build_user_router
from .config import Settings, require_runtime_secrets
from .db import Database
from .jobs import BackgroundRunner
from .service import Service
from .xui import XUIClient

log = logging.getLogger(__name__)


def build_dispatcher(
    svc: Service, settings: Settings, *, rate_limit_sec: float = 0.35
) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    guard = GuardMiddleware(svc, settings, min_interval_sec=rate_limit_sec)
    dp.message.outer_middleware(guard)
    dp.callback_query.outer_middleware(guard)

    dp.include_router(build_admin_router())
    dp.include_router(build_payments_router())
    dp.include_router(build_user_router())
    dp.include_router(build_fallback_router())
    return dp


async def run() -> None:  # pragma: no cover - production entrypoint
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings()
    require_runtime_secrets(settings)

    db = Database(settings.db_path)
    await db.connect()

    xui = XUIClient(
        settings.panel_base_url.get_secret_value(),
        settings.panel_user.get_secret_value(),
        settings.panel_pass.get_secret_value(),
        verify_tls=settings.panel_verify_tls,
    )
    svc = Service(
        db,
        xui,
        inbound_remark=settings.inbound_remark,
        server_host=settings.server_host,
    )
    await svc.startup()

    bot = Bot(token=settings.bot_token.get_secret_value())
    me = await bot.get_me()
    log.info("started bot @%s (id=%s)", me.username, me.id)

    dp = build_dispatcher(svc, settings)
    jobs = BackgroundRunner(svc, bot, settings)
    jobs.start()
    try:
        await dp.start_polling(bot)
    finally:
        await jobs.stop()
        await bot.session.close()
        await xui.aclose()
        await db.close()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(run())
