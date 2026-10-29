"""Config safety, Telegram initData HMAC-SHA256 validation, Mini App API, Web Admin, and Multi-Panel tests."""

from __future__ import annotations

import base64
from datetime import timedelta

import httpx
import pytest
from pydantic import SecretStr

from exabyte_bot.config import ConfigError, Settings
from exabyte_bot.service import Service
from exabyte_bot.webapp.api import create_webapp
from exabyte_bot.webapp.auth import (
    AuthError,
    build_init_data,
    create_admin_web_token,
    validate_init_data,
    verify_admin_web_token,
)
from exabyte_bot.xui import XUIClient
from tests.conftest import ADMIN, USER
from tests.mock_xui import FlakyTransport, MockPanel

FAKE_TOKEN = "123456789:AA" + "B" * 33  # secret-check: ignore


def test_dev_mode_refuses_production():
    with pytest.raises(ConfigError, match="forbidden"):
        Settings(_env_file=None, environment="production", dev_mode=True)


def test_dev_mode_requires_localhost():
    with pytest.raises(ConfigError, match="localhost"):
        Settings(_env_file=None, environment="development", dev_mode=True, web_host="0.0.0.0")


def test_dev_mode_ok_in_development_on_localhost():
    s = Settings(_env_file=None, environment="development", dev_mode=True)
    assert s.dev_mode


def test_admin_ids_parsing_and_secret_repr(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "1877867098, 42")
    monkeypatch.setenv("PANEL_PASS", "super-secret-value")  # secret-check: ignore
    s = Settings(_env_file=None)
    assert s.admin_ids == [1877867098, 42] and s.is_admin(42)
    assert "super-secret-value" not in repr(s)


def test_init_data_validation_and_expiry(clock):
    now = clock()
    raw = build_init_data(
        {"id": USER, "first_name": "Alice", "username": "alice"},
        FAKE_TOKEN,
        auth_date=int(now.timestamp()),
    )
    user = validate_init_data(raw, FAKE_TOKEN, now=now)
    assert user.id == USER and user.username == "alice"

    # Tampered user ID must fail signature check
    forged = raw.replace(str(USER), "999999999")
    with pytest.raises(AuthError, match="Invalid initData signature"):
        validate_init_data(forged, FAKE_TOKEN, now=now)

    # Older than 24h must fail
    with pytest.raises(AuthError, match="Expired initData"):
        validate_init_data(raw, FAKE_TOKEN, now=now + timedelta(hours=25))

    # Missing initData
    with pytest.raises(AuthError):
        validate_init_data("", FAKE_TOKEN, now=now)


def test_admin_web_token_roundtrip(clock):
    now = clock()
    tok = create_admin_web_token(ADMIN, FAKE_TOKEN, now=now)
    u = verify_admin_web_token(tok, FAKE_TOKEN, now=now)
    assert u.id == ADMIN
    with pytest.raises(AuthError):
        verify_admin_web_token(tok + "x", FAKE_TOKEN, now=now)


async def test_miniapp_customer_and_admin_web_flows(svc: Service, clock, tmp_path):
    settings = Settings(
        _env_file=None,
        bot_token=SecretStr(FAKE_TOKEN),
        admin_ids=[ADMIN],
        kbz_number="09000000000",  # secret-check: ignore
        kbz_name="Exabyte Owner",
        bot_domain="tgbot.lhpvpn.online",
        data_dir=tmp_path,
    )
    app = create_webapp(svc, settings)
    user_init = build_init_data(
        {"id": USER, "first_name": "Alice", "username": "alice"},
        FAKE_TOKEN,
        auth_date=int(clock().timestamp()),
    )
    admin_init = build_init_data(
        {"id": ADMIN, "first_name": "Boss", "username": "admin"},
        FAKE_TOKEN,
        auth_date=int(clock().timestamp()),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Unauthenticated request rejected
        assert (await client.get("/api/bootstrap")).status_code == 401

        # Customer bootstrap
        r = await client.get("/api/bootstrap", headers={"X-Telegram-Init-Data": user_init})
        assert r.status_code == 200
        boot = r.json()
        assert boot["user"]["id"] == USER and boot["status"]["has_key"] is False
        assert len(boot["plans"]) == 6

        # Claim trial via Mini App
        r = await client.post("/api/trial/claim", headers={"X-Telegram-Init-Data": user_init})
        assert r.status_code == 200
        st = r.json()["status"]
        assert st["has_key"] is True and st["kind"] == "trial"

        # Fetch QR PNG & Subscription URL
        qr = await client.get("/api/key/qr", headers={"X-Telegram-Init-Data": user_init})
        assert qr.status_code == 200 and qr.content.startswith(b"\x89PNG")
        sub_res = await client.get(f"/sub/{st['sub_id']}")
        assert sub_res.status_code == 200
        assert base64.b64decode(sub_res.text).decode().startswith("ss://")

        # Create order & upload screenshot in Mini App -> instant paid key upgrade!
        ord_res = await client.post(
            "/api/orders",
            json={"plan_id": "vpn_3m"},
            headers={"X-Telegram-Init-Data": user_init},
        )
        assert ord_res.status_code == 200
        code = ord_res.json()["code"]

        shot_res = await client.post(
            f"/api/orders/{code}/screenshot",
            json={"image_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"},
            headers={"X-Telegram-Init-Data": user_init},
        )
        assert shot_res.status_code == 200
        assert shot_res.json()["status"]["kind"] == "paid"

        # Non-admin cannot access Web Admin API
        assert (
            await client.get("/api/admin/overview", headers={"X-Telegram-Init-Data": user_init})
        ).status_code == 403

        # Admin views overview and marks order Unpaid -> rolls back to trial key!
        ov = await client.get(
            "/api/admin/overview", headers={"X-Telegram-Init-Data": admin_init}
        )
        assert ov.status_code == 200
        assert ov.json()["orders"][0]["code"] == code
        assert f"/api/admin/orders/{code}/screenshot" in ov.json()["orders"][0]["screenshot"]

        # Admin can view the uploaded screenshot binary via the endpoint
        shot_img = await client.get(
            f"/api/admin/orders/{code}/screenshot", headers={"X-Telegram-Init-Data": admin_init}
        )
        assert shot_img.status_code == 200
        assert shot_img.headers["content-type"] == "image/png"
        assert len(shot_img.content) > 0

        # Query param token also allows image loading in standard <img> tags
        admin_tok = create_admin_web_token(ADMIN, FAKE_TOKEN, now=clock())
        shot_img_q = await client.get(f"/api/admin/orders/{code}/screenshot?token={admin_tok}")
        assert shot_img_q.status_code == 200
        assert shot_img_q.headers["content-type"] == "image/png"
        assert len(shot_img_q.content) > 0

        rj = await client.post(
            f"/api/admin/orders/{code}/reject",
            json={"reason": "Unpaid test"},
            headers={"X-Telegram-Init-Data": admin_init},
        )
        assert rj.status_code == 200
        assert (await svc.get_key(USER)).kind == "trial"

        # Admin suspends and resumes user key from Web Admin
        await client.post(
            f"/api/admin/users/{USER}/action",
            json={"action": "suspend"},
            headers={"X-Telegram-Init-Data": admin_init},
        )
        assert (await svc.get_key(USER)).status == "disabled"

        await client.post(
            f"/api/admin/users/{USER}/action",
            json={"action": "resume"},
            headers={"X-Telegram-Init-Data": admin_init},
        )
        assert (await svc.get_key(USER)).status == "active"

        # Admin updates customizations from Web Admin
        cfg_res = await client.post(
            "/api/admin/settings",
            json={"tagline": "မြန်မာ့အကောင်းဆုံး VPN ဆိုင်"},
            headers={"X-Telegram-Init-Data": admin_init},
        )
        assert cfg_res.status_code == 200
        assert cfg_res.json()["store"]["tagline"] == "မြန်မာ့အကောင်းဆုံး VPN ဆိုင်"


async def test_multi_panel_key_combinations(svc: Service, user: int):
    # First claim a key on the primary panel
    kv = await svc.claim_trial(user)

    # Spin up a second MockPanel (Server 2 SG) and add it to the service
    panel2 = MockPanel(base_path="secPath2", port=45678, method="aes-256-gcm")
    t2 = FlakyTransport(httpx.ASGITransport(app=panel2.app))
    xui2 = XUIClient(f"http://mock2/{panel2.base_path}", panel2.username, panel2.password, transport=t2)

    await svc.add_panel(
        ADMIN,
        name="Server 2 SG",
        base_url=f"http://mock2/{panel2.base_path}",
        username=panel2.username,
        password=panel2.password,
        server_host="sg2.lhpvpn.online",
        client_override=xui2,
    )

    # Existing key was automatically synced onto panel2!
    assert panel2.client(kv.email) is not None
    links = await svc.get_key_links(user)
    assert len(links) == 2
    assert "sg2.lhpvpn.online:45678" in links[1]["link"]

    # Subscription payload includes both servers' ss:// links
    sub_b64 = await svc.subscription_payload_by_sub_id(kv.sub_id)
    decoded = base64.b64decode(sub_b64).decode().splitlines()
    assert len(decoded) == 2

    # Traffic across both panels is aggregated on sync_usage()
    panel2.add_usage(kv.email, down=1024 * 1024 * 500)
    await svc.sync_usage()
    assert (await svc.get_key(user)).used_bytes == 1024 * 1024 * 500

    # Suspending key suspends on both panels
    await svc.admin_set_key_enabled(ADMIN, user, False)
    assert panel2.client(kv.email)["enable"] is False

    await svc.delete_panel(ADMIN, 1)


async def test_healthcheck_endpoint(svc: Service):
    settings = Settings(
        _env_file=None, bot_token=SecretStr(FAKE_TOKEN), environment="development", dev_mode=True
    )
    app = create_webapp(svc, settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
