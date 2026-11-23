"""Application wiring and entrypoint: Dispatcher, routers, background jobs, startup/shutdown."""

from __future__ import annotations

import asyncio
import logging
import os

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, MenuButtonCommands

from .bot.admin import build_admin_router
from .bot.messages import STORE_NAME
from .bot.middleware import GuardMiddleware
from .bot.payments import build_payments_router
from .bot.user import build_fallback_router, build_user_router
from .config import Settings, require_runtime_secrets
from .db import Database
from .jobs import BackgroundRunner
from .service import Service
from .webapp.api import create_webapp
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
    dp.include_router(build_user_router())
    dp.include_router(build_payments_router())
    dp.include_router(build_fallback_router())
    return dp


async def run() -> None:  # pragma: no cover - production entrypoint
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    env_file = os.environ.get("ENV_FILE", ".env")
    settings = Settings(_env_file=env_file)
    STORE_NAME.set(settings.store_name)
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
        exabyte_plans=settings.is_exabyte_bot,
    )
    await svc.startup()

    bot = Bot(token=settings.bot_token.get_secret_value())
    me = await bot.get_me()
    log.info("started bot @%s (id=%s)", me.username, me.id)
    await bot.set_my_commands([
        BotCommand(command="start", description="ဆိုင်ဖွင့်ရန်"),
        BotCommand(command="trial", description="အခမဲ့ စမ်းသုံးရန်"),
        BotCommand(command="key", description="ကျွန်ုပ်၏ VPN Key"),
        BotCommand(command="guide", description="Outline ချိတ်ဆက်နည်း"),
        BotCommand(command="help", description="အကူအညီ"),
    ])
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    await bot.set_my_description(
        description=f"{settings.store_name} မှ ကြိုဆိုပါတယ်။ Outline VPN အခမဲ့ စမ်းသုံးရန် Start ကို နှိပ်ပါ။"
    )
    await bot.set_my_short_description(
        short_description=f"{settings.store_name} · Outline VPN Key နှင့် အခမဲ့ စမ်းသပ်မှု"
    )

    dp = build_dispatcher(svc, settings)
    webapp = create_webapp(svc, settings, bot=bot)
    uv_cfg = uvicorn.Config(
        webapp, host=settings.web_host, port=settings.web_port, log_level="info"
    )
    uv_server = uvicorn.Server(uv_cfg)

    jobs = BackgroundRunner(svc, bot, settings)
    jobs.start()
    web_task = asyncio.create_task(uv_server.serve(), name="exabyte-webapp")
    try:
        await dp.start_polling(bot)
    finally:
        uv_server.should_exit = True
        await web_task
        await jobs.stop()
        await bot.session.close()
        await xui.aclose()
        await db.close()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(run())

