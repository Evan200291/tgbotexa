"""Channel isolation and real first-use lifecycle regressions."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetChatMember
from aiogram.types import ReplyKeyboardMarkup
from pydantic import SecretStr

from exabyte_bot.config import Settings
from exabyte_bot.membership import is_channel_member
from exabyte_bot.service import Service
from exabyte_bot.strings import S
from exabyte_bot.util import MS_PER_DAY, to_ms
from exabyte_bot.webapp.api import create_webapp
from exabyte_bot.webapp.auth import build_init_data
from exabyte_bot.xui import XUIClient
from tests.conftest import ADMIN, USER
from tests.mock_xui import MockPanel
from tests.test_bot_flows import _make_harness
from tests.test_webapp_auth import FAKE_TOKEN


async def test_startup_repairs_existing_sg_panel_http_url(db, xui, clock):
    await db.execute(
        "INSERT INTO panels(name, base_url, username, password, server_host, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("Singapore (SG)", "https://sgsep.lhpvpn.online:8080/secret-path", "user", "pass",
         "sgsep.lhpvpn.online", 0),
    )
    svc = Service(db, xui, inbound_remark="exabytetgbot", server_host="vpn.example.test",
                  clock=clock)
    await svc.startup()
    row = await db.fetchone("SELECT base_url, verify_tls FROM panels WHERE id=1")
    assert row["base_url"] == "http://sgsep.lhpvpn.online:8080/secret-path"
    assert row["verify_tls"] == 0
    await svc.startup()
    assert (await db.fetchone("SELECT base_url FROM panels WHERE id=1"))["base_url"] == row["base_url"]


@pytest.mark.parametrize("status,member,allowed", [
    ("member", False, True), ("administrator", False, True), ("creator", False, True),
    ("restricted", True, True), ("restricted", False, False),
    ("left", False, False), ("kicked", False, False),
])
async def test_membership_statuses(status, member, allowed):
    bot = SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(
        status=status, is_member=member)))
    settings = Settings(_env_file=None, required_channel="@outlineplusmm")
    assert await is_channel_member(bot, settings, ADMIN) is allowed
    bot.get_chat_member.assert_awaited_once_with("@outlineplusmm", ADMIN)


async def test_membership_api_failure_does_not_grant_access():
    bot = SimpleNamespace(get_chat_member=AsyncMock(side_effect=TelegramBadRequest(
        method=GetChatMember(chat_id="@outlineplusmm", user_id=USER), message="Unavailable")))
    assert not await is_channel_member(bot, Settings(_env_file=None,
        required_channel="@outlineplusmm"), USER)
    assert await is_channel_member(bot, Settings(_env_file=None), USER)
    assert bot.get_chat_member.await_count == 1


@pytest.mark.parametrize("uid", [USER, ADMIN])
async def test_second_bot_requires_join_for_every_user(svc, tmp_path, uid):
    _, session, settings, send, _, tap = _make_harness(svc, tmp_path)
    settings.required_channel = "@outlineplusmm"
    settings.required_channel_url = "https://t.me/outlineplusmm"
    settings.store_name = "Outline Plus MM"
    original = session.make_request
    joined = False

    async def request(bot, method, **kwargs):
        if isinstance(method, GetChatMember):
            return SimpleNamespace(status="member" if joined else "left")
        return await original(bot, method, **kwargs)
    session.make_request = request
    await send(uid, "/start")
    assert session.last_text(uid) == S["join_required"]
    await tap(uid, "nav:trial")
    assert await svc.get_key(uid) is None
    joined = True
    await tap(uid, "membership:check")
    assert "Outline Plus MM" in session.last_text(uid)
    assert isinstance(session.sent_to(uid)[-1].reply_markup, ReplyKeyboardMarkup)
    await send(uid, S["btn_trial"])
    assert await svc.get_key(uid) is not None
    joined = False
    await send(uid, S["btn_my_key"])
    assert session.last_text(uid) == S["join_required"]


async def test_first_bot_keeps_persistent_keyboard_without_join(svc, tmp_path):
    _, session, _, send, _, _ = _make_harness(svc, tmp_path)
    await send(USER, "/start")
    keyboard = session.sent_to(USER)[-1].reply_markup
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    assert keyboard.is_persistent and not keyboard.one_time_keyboard
    await send(USER, S["btn_trial"])
    assert await svc.get_key(USER)
    assert not any(isinstance(call, GetChatMember) for call in session.calls)


async def test_miniapp_channel_gate_cannot_be_bypassed(svc, clock):
    settings = Settings(_env_file=None, bot_token=SecretStr(FAKE_TOKEN),
        required_channel="@outlineplusmm", required_channel_url="https://t.me/outlineplusmm")
    bot = SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(status="left")))
    raw = build_init_data({"id": USER, "first_name": "Alice"}, FAKE_TOKEN,
                          auth_date=int(clock().timestamp()))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_webapp(
        svc, settings, bot=bot)), base_url="http://test",
        headers={"X-Telegram-Init-Data": raw}) as client:
        assert (await client.get("/api/bootstrap")).status_code == 403
        assert (await client.post("/api/trial/claim")).status_code == 403
        assert (await client.post("/api/orders", json={"plan_id": "vpn_1m"})).status_code == 403
        assert await svc.get_key(USER) is None
        bot.get_chat_member.return_value = SimpleNamespace(status="member")
        assert (await client.get("/api/bootstrap")).status_code == 200
        assert (await client.post("/api/trial/claim")).status_code == 200


async def test_unused_key_never_counts_down_and_pending_renewal_adds_duration(svc, user, panel, clock):
    key = await svc.grant_plan(ADMIN, user, "vpn_1m")
    clock.advance(days=80)
    await svc.sync_usage()
    assert (await svc.get_key(user)).expiry_ms == -30 * MS_PER_DAY
    assert panel.client(key.email)["enable"]
    assert not await svc.collect_notifications()
    status = await svc.get_status(user)
    assert status["pending_activation"] and status["expiry_at"] is None
    assert status["days_left"] == 30
    renewed = await svc.grant_plan(ADMIN, user, "vpn_3m")
    assert renewed.expiry_ms == -120 * MS_PER_DAY
    panel.add_usage(key.email, down=100)
    await svc.sync_usage()
    assert (await svc.get_key(user)).expiry_ms == to_ms(clock()) + 120 * MS_PER_DAY


async def test_renewal_before_sync_preserves_actual_activation(svc, user, panel, clock):
    key = await svc.grant_plan(ADMIN, user, "vpn_1m")
    panel.add_usage(key.email, down=100)
    original_deadline = panel.traffic[key.email]["expiryTime"]
    clock.advance(days=4)
    renewed = await svc.grant_plan(ADMIN, user, "vpn_1m")
    assert renewed.expiry_ms == original_deadline + 30 * MS_PER_DAY


async def test_secondary_panel_starts_shared_clock_and_retries_sync(svc, user, panel, clock):
    other = MockPanel()
    client = XUIClient(f"http://mock/{other.base_path}", other.username, other.password,
                      transport=httpx.ASGITransport(app=other.app), retries=1)
    try:
        await svc.add_panel(ADMIN, name="Other", base_url="http://mock", username="test",
            password="test", server_host="other.example.test", client_override=client)
        key = await svc.grant_plan(ADMIN, user, "vpn_1m")
        deadline = other.activate(key.email, to_ms(clock()))
        await svc.sync_usage()
        assert (await svc.get_key(user)).expiry_ms == deadline
        assert panel.client(key.email)["expiryTime"] == deadline
        assert other.client(key.email)["expiryTime"] == deadline
        await svc.sync_usage()
        assert (await svc.get_key(user)).expiry_ms == deadline
    finally:
        await client.aclose()


async def test_primary_key_edit_works_with_unreachable_extra_panel(svc, user, panel, clock):
    other = MockPanel()
    client = XUIClient(f"http://mock/{other.base_path}", other.username, other.password,
                      transport=httpx.ASGITransport(app=other.app), retries=1)
    try:
        await svc.add_panel(ADMIN, name="Offline extra", base_url="http://mock", username="test",
            password="test", server_host="other.example.test", client_override=client)
        key = await svc.grant_plan(ADMIN, user, "vpn_1m", panel_id=0)
        other.down = True
        updated = await svc.admin_adjust_key(ADMIN, user, add_days=7)
        assert updated.expiry_ms == -37 * MS_PER_DAY
        assert panel.client(key.email)["expiryTime"] == -37 * MS_PER_DAY
    finally:
        await client.aclose()
