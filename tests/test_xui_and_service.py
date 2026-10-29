"""XUIClient behaviour against the mock panel + trial/renewal business rules."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import pytest

from exabyte_bot import packages as P
from exabyte_bot.service import (
    RegenNotAllowed,
    RegenTooEarly,
    Service,
    TrialPaidActive,
    TrialTooEarly,
)
from exabyte_bot.util import (
    GB,
    MMT,
    MS_PER_DAY,
    fmt_date,
    fmt_mmk,
    from_ms,
    local_day_start_ms,
    to_ms,
)
from exabyte_bot.xui import (
    Inbound,
    InboundNotFound,
    PanelAuthError,
    PanelUnavailable,
    XUIClient,
    build_ss_link,
    generate_password,
    qr_png,
)
from tests.conftest import ADMIN, USER
from tests.mock_xui import MockPanel


def _decode_userinfo(link: str) -> str:
    b64 = link.removeprefix("ss://").split("@")[0]
    return base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)).decode()


# ------------------------------------------------------------------ XUI client
async def test_finds_inbound_by_remark_and_reads_port_and_method(xui: XUIClient):
    ib = await xui.find_inbound("exabytetgbot")
    assert (ib.id, ib.port, ib.method) == (7, 34567, "chacha20-ietf-poly1305")


async def test_missing_inbound_fails_clearly(xui: XUIClient):
    with pytest.raises(InboundNotFound, match="nope"):
        await xui.find_inbound("nope")


async def test_wrong_password_raises_auth_error(panel: MockPanel, transport):
    c = XUIClient(f"http://mock/{panel.base_path}", "admin", "wrong", transport=transport)
    with pytest.raises(PanelAuthError):
        await c.list_inbounds()
    await c.aclose()


async def test_relogin_after_session_expiry(xui: XUIClient, panel: MockPanel):
    await xui.list_inbounds()
    panel.expire_sessions()
    await xui.list_inbounds()
    assert panel.login_count == 2


async def test_retry_then_success(xui: XUIClient, transport):
    transport.fail_next = 2  # two connection errors, third attempt works
    assert await xui.find_inbound("exabytetgbot")


async def test_panel_down_raises_unavailable_without_leaking_url(xui, transport, panel):
    transport.fail_next = 99
    with pytest.raises(PanelUnavailable) as e:
        await xui.list_inbounds()
    assert panel.base_path not in str(e.value)
    assert transport.attempts == 3


@pytest.mark.parametrize("method,nbytes", [
    ("2022-blake3-aes-128-gcm", 16), ("2022-blake3-aes-256-gcm", 32),
    ("2022-blake3-chacha20-poly1305", 32),
])
def test_ss2022_password_length(method, nbytes):
    assert len(base64.b64decode(generate_password(method))) == nbytes


def test_legacy_password_and_link():
    ib = Inbound(id=1, remark="r", port=8388, method="aes-256-gcm", server_key=None)
    pw = generate_password(ib.method)
    assert len(pw) == 16
    link = build_ss_link(ib, pw, "h.example", "Exabyte tg1")
    assert link.endswith("@h.example:8388#Exabyte%20tg1")
    assert _decode_userinfo(link) == f"aes-256-gcm:{pw}"


def test_ss2022_link_uses_server_and_client_key():
    ib = Inbound(id=1, remark="r", port=443, method="2022-blake3-aes-128-gcm", server_key="SK==")
    assert _decode_userinfo(build_ss_link(ib, "CK==", "h", "x")) == \
        "2022-blake3-aes-128-gcm:SK==:CK=="


def test_qr_png_is_png():
    assert qr_png("ss://abc").startswith(b"\x89PNG")


# ------------------------------------------------------------------ plans
def test_plan_prices_from_data():
    prices = {p.id: (p.price_mmk, p.original_price_mmk, p.discount_mmk) for p in P.PLANS}
    assert prices == {"vpn_1m": (5000, 5000, 0), "vpn_3m": (14500, 15000, 500),
                      "vpn_6m": (29000, 30000, 1000)}
    assert all(p.unlimited and p.devices == 1 and p.category == "vpn" for p in P.PLANS)
    assert [p.days for p in P.PLANS] == [30, 90, 180]
    assert fmt_mmk(14500) == "14,500 ကျပ်"


# ------------------------------------------------------------------ trial
async def test_trial_claim_creates_panel_client(svc: Service, user, panel: MockPanel, clock):
    key = await svc.claim_trial(user)
    c = panel.client(key.email)
    assert c is not None
    assert c["totalGB"] == 5 * GB and c["limitIp"] == 1 and c["tgId"] == USER
    assert c["expiryTime"] == to_ms(clock()) + 7 * MS_PER_DAY
    assert key.email.startswith(f"tg{USER}-") and key.status == "active"
    assert key.link.startswith("ss://") and "vpn.example.test:34567" in key.link


async def test_early_reclaim_rejected_with_countdown(svc: Service, user, clock):
    await svc.claim_trial(user)
    clock.advance(days=6, hours=20)
    with pytest.raises(TrialTooEarly) as e:
        await svc.claim_trial(user)
    assert e.value.seconds_left == 4 * 3600
    assert "4 နာရီ" in e.value.message()


async def test_status_has_next_trial_at_while_trial_active(svc: Service, user, clock):
    await svc.claim_trial(user)
    clock.advance(days=1)
    st = await svc.get_status(user)
    assert st["kind"] == "trial" and st["status"] == "active"
    assert st["trial"]["available"] is False
    assert st["trial"]["next_trial_at"] == "2026-01-08T12:00:00Z"
    assert st["trial"]["seconds_until_next_trial"] == 6 * 86400


async def test_reclaim_after_7_days_issues_new_key_and_resets_usage(svc, user, panel, clock):
    old = await svc.claim_trial(user)
    panel.add_usage(old.email, down=3 * GB)
    await svc.sync_usage()
    assert (await svc.get_key(user)).used_bytes == 3 * GB
    clock.advance(days=7)
    new = await svc.claim_trial(user)
    assert new.email != old.email and new.password != old.password
    assert panel.client(old.email) is None  # old key revoked on the panel
    assert new.used_bytes == 0
    assert new.expiry_ms == to_ms(clock()) + 7 * MS_PER_DAY
    assert len(panel.clients()) == 1


async def test_trial_refused_while_paid_active(svc: Service, user):
    await svc.grant_plan(ADMIN, user, "vpn_1m")
    with pytest.raises(TrialPaidActive):
        await svc.claim_trial(user)


async def test_trial_panel_down_records_nothing(svc: Service, user, transport):
    transport.fail_next = 99
    with pytest.raises(PanelUnavailable):
        await svc.claim_trial(user)
    transport.fail_next = 0
    assert (await svc.get_status(user))["trial"]["available"] is True
    assert await svc.claim_trial(user)  # retry works


# ------------------------------------------------------------------ renewals
async def test_trial_upgrades_to_paid_same_key(svc: Service, user, panel, clock):
    trial = await svc.claim_trial(user)
    panel.add_usage(trial.email, down=2 * GB)
    paid = await svc.grant_plan(ADMIN, user, "vpn_1m")
    assert paid.email == trial.email and paid.kind == "paid"
    c = panel.client(paid.email)
    assert c["totalGB"] == 0 and c["limitIp"] == 1
    assert c["expiryTime"] == to_ms(clock()) + 30 * MS_PER_DAY
    assert panel.traffic[paid.email]["down"] == 0
    assert len(panel.clients()) == 1


async def test_renewal_extends_from_current_expiry_when_active(svc: Service, user, clock):
    first = await svc.grant_plan(ADMIN, user, "vpn_1m")
    clock.advance(days=10)
    second = await svc.grant_plan(ADMIN, user, "vpn_3m")
    assert second.expiry_ms == first.expiry_ms + 90 * MS_PER_DAY
    assert second.email == first.email


async def test_renewal_starts_from_now_when_expired(svc: Service, user, clock, panel):
    await svc.grant_plan(ADMIN, user, "vpn_1m")
    clock.advance(days=45)
    await svc.sync_usage()  # disables the expired client on the panel
    key = await svc.get_key(user)
    assert key.status == "expired" and panel.client(key.email)["enable"] is False
    renewed = await svc.grant_plan(ADMIN, user, "vpn_6m")
    assert renewed.expiry_ms == to_ms(clock()) + 180 * MS_PER_DAY
    assert panel.client(renewed.email)["enable"] is True


# ------------------------------------------------------------------ regenerate
async def test_regenerate_paid_once_per_24h(svc: Service, user, clock, panel):
    before = await svc.grant_plan(ADMIN, user, "vpn_1m")
    after = await svc.regenerate_key(user)
    assert after.password != before.password and after.email == before.email
    assert panel.client(after.email)["password"] == after.password
    with pytest.raises(RegenTooEarly):
        await svc.regenerate_key(user)
    clock.advance(hours=24)
    assert await svc.regenerate_key(user)


async def test_trial_cannot_regenerate(svc: Service, user):
    await svc.claim_trial(user)
    with pytest.raises(RegenNotAllowed):
        await svc.regenerate_key(user)


async def test_concurrent_trial_taps_create_one_key(svc: Service, user, panel):
    import asyncio

    results = await asyncio.gather(svc.claim_trial(user), svc.claim_trial(user),
                                   return_exceptions=True)
    assert sum(not isinstance(r, Exception) for r in results) == 1
    assert isinstance([r for r in results if isinstance(r, Exception)][0], TrialTooEarly)
    assert len(panel.clients()) == 1


async def test_ss2022_inbound_end_to_end(db, clock):
    import httpx

    from tests.mock_xui import FlakyTransport

    panel = MockPanel(method="2022-blake3-aes-128-gcm")
    t = FlakyTransport(httpx.ASGITransport(app=panel.app))
    x = XUIClient(f"http://mock/{panel.base_path}", "admin", "admin-pass", transport=t)
    s = Service(db, x, inbound_remark="exabytetgbot", server_host="h", clock=clock)
    await s.startup()
    await s.ensure_user(5, None, None)
    key = await s.claim_trial(5)
    assert panel.client(key.email)["method"] == ""
    assert len(base64.b64decode(key.password)) == 16
    assert _decode_userinfo(key.link).count(":") == 2
    await x.aclose()


def test_mmt_timezone_and_date_formatting():
    # 2026-10-29 12:00:00 UTC = 2026-10-29 18:30:00 MMT (+6:30)
    utc_dt = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)
    ms = to_ms(utc_dt)
    formatted = fmt_date(ms)
    assert formatted == "2026-10-29 18:30 MMT"

    # local_day_start_ms should equal 2026-10-29 00:00:00 MMT
    start_day_ms = local_day_start_ms(utc_dt)
    start_dt = from_ms(start_day_ms) + MMT
    expected = (2026, 10, 29, 0, 0)
    assert (start_dt.year, start_dt.month, start_dt.day, start_dt.hour, start_dt.minute) == expected
