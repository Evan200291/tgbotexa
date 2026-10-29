"""Local development server for previewing the Mini App, /dev/kit, and Web Admin Panel.

Uses the in-memory MockPanel and DEV_MODE=true on 127.0.0.1:8080 (never touches real services).
Run:  .venv/Scripts/python.exe scripts/dev_server.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import uvicorn
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exabyte_bot.config import Settings  # noqa: E402
from exabyte_bot.db import Database  # noqa: E402
from exabyte_bot.service import Service  # noqa: E402
from exabyte_bot.webapp.api import create_webapp  # noqa: E402
from exabyte_bot.xui import XUIClient  # noqa: E402
from tests.mock_xui import MockPanel  # noqa: E402


async def main() -> None:
    panel = MockPanel()
    transport = httpx.ASGITransport(app=panel.app)
    xui = XUIClient(
        f"http://mock/{panel.base_path}",
        panel.username,
        panel.password,
        transport=transport,
    )
    db = Database(":memory:")
    await db.connect()
    svc = Service(
        db, xui, inbound_remark="exabytetgbot", server_host="tpone.lhpvpn.online"
    )
    await svc.startup()

    # Seed sample trial key & order for visual inspection
    await svc.ensure_user(111222333, "aung_dev", "Aung Aung")
    await svc.ensure_user(1877867098, "exabyte_admin", "Exabyte Admin")
    kv = await svc.claim_trial(111222333)
    panel.add_usage(kv.email, down=2 * 1024**3)
    await svc.sync_usage()

    settings = Settings(
        _env_file=None,
        bot_token=SecretStr("dev-local-token"),
        environment="development",
        dev_mode=True,
        web_host="127.0.0.1",
        web_port=8080,
        kbz_number="09000000000",  # secret-check: ignore
        kbz_name="Exabyte Digital Store",
    )
    app = create_webapp(svc, settings)
    cfg = uvicorn.Config(app, host="127.0.0.1", port=8080, log_level="warning")
    server = uvicorn.Server(cfg)
    print("Exabyte Dev Server listening on http://127.0.0.1:8080 (and /admin, /dev/kit)")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())

