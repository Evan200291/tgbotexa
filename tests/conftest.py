"""Shared fixtures: in-memory mock panel, temp SQLite DB, controllable clock.

Nothing here touches the network: httpx talks to the mock via ASGITransport.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from exabyte_bot.db import Database
from exabyte_bot.service import Service
from exabyte_bot.xui import XUIClient
from tests.mock_xui import FlakyTransport, MockPanel


class FakeClock:
    def __init__(self, start: datetime):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw: float) -> None:
        self.now += timedelta(**kw)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))


@pytest.fixture
def panel() -> MockPanel:
    return MockPanel()


@pytest.fixture
def transport(panel: MockPanel) -> FlakyTransport:
    return FlakyTransport(httpx.ASGITransport(app=panel.app))


@pytest.fixture
async def xui(panel: MockPanel, transport: FlakyTransport):
    client = XUIClient(f"http://mock/{panel.base_path}", panel.username, panel.password,
                       transport=transport, retries=3, backoff=0.001)
    yield client
    await client.aclose()


@pytest.fixture
async def db(tmp_path):
    d = Database(tmp_path / "test.sqlite3")
    await d.connect()
    yield d
    await d.close()


@pytest.fixture
async def svc(db: Database, xui: XUIClient, clock: FakeClock) -> Service:
    s = Service(db, xui, inbound_remark="exabytetgbot", server_host="vpn.example.test",
                clock=clock)
    await s.startup()
    return s


USER = 111222333
ADMIN = 1877867098


@pytest.fixture
async def user(svc: Service) -> int:
    await svc.ensure_user(USER, "alice", "Alice")
    return USER

