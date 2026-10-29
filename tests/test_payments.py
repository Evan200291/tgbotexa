"""Order / manual payment approval rules."""

from __future__ import annotations

import asyncio

import pytest

from exabyte_bot.service import (
    DuplicateScreenshot,
    OpenOrderExists,
    OrderBadState,
    OrderNotFound,
    Service,
)
from exabyte_bot.util import MS_PER_DAY, to_ms
from tests.conftest import ADMIN

OTHER = 444555666


async def _submitted(svc: Service, uid: int, plan: str, shot: str = "uniq-1"):
    order = await svc.create_order(uid, plan)
    return await svc.attach_screenshot(uid, order.code, f"file-{shot}", shot)


@pytest.mark.parametrize("plan,amount,days", [
    ("vpn_1m", 5000, 30), ("vpn_3m", 14500, 90), ("vpn_6m", 29000, 180),
])
async def test_purchase_each_plan(svc: Service, user, panel, clock, plan, amount, days):
    order = await svc.create_order(user, plan)
    assert order.state == "pending_payment" and order.amount == amount
    assert order.code.startswith("EX") and len(order.code) == 8
    order = await svc.attach_screenshot(user, order.code, "fid", "uid-x")
    assert order.state == "awaiting_review"
    res = await svc.approve_order(order.code, ADMIN)
    assert res.order.state == "approved" and res.order.reviewed_by == ADMIN and not res.already
    assert res.key.kind == "paid" and res.key.unlimited
    c = panel.client(res.key.email)
    assert c["totalGB"] == 0 and c["limitIp"] == 1
    assert c["expiryTime"] == to_ms(clock()) + days * MS_PER_DAY


async def test_approve_is_idempotent(svc: Service, user, panel):
    order = await _submitted(svc, user, "vpn_1m")
    first = await svc.approve_order(order.code, ADMIN)
    second = await svc.approve_order(order.code, ADMIN)
    assert second.already and second.key.expiry_ms == first.key.expiry_ms
    assert panel.client(first.key.email)["expiryTime"] == first.key.expiry_ms


async def test_concurrent_double_tap_extends_once(svc: Service, user):
    order = await _submitted(svc, user, "vpn_3m")
    a, b = await asyncio.gather(svc.approve_order(order.code, ADMIN),
                                svc.approve_order(order.code, ADMIN))
    assert sorted([a.already, b.already]) == [False, True]
    assert a.key.expiry_ms == b.key.expiry_ms


async def test_duplicate_screenshot_on_other_order_rejected(svc: Service, user):
    await svc.ensure_user(OTHER, "bob", "Bob")
    await _submitted(svc, user, "vpn_1m", shot="same-shot")
    o2 = await svc.create_order(OTHER, "vpn_1m")
    with pytest.raises(DuplicateScreenshot):
        await svc.attach_screenshot(OTHER, o2.code, "f", "same-shot")


async def test_one_open_order_per_user(svc: Service, user):
    o = await svc.create_order(user, "vpn_1m")
    with pytest.raises(OpenOrderExists) as e:
        await svc.create_order(user, "vpn_3m")
    assert o.code in e.value.message()


async def test_reject_with_reason_then_new_order_allowed(svc: Service, user):
    o = await _submitted(svc, user, "vpn_1m")
    res = await svc.reject_order(o.code, ADMIN, "ငွေပမာဏ မကိုက်ညီပါ")
    assert res.order.state == "rejected" and res.order.reason
    assert (await svc.reject_order(o.code, ADMIN)).already
    with pytest.raises(OrderBadState):
        await svc.approve_order(o.code, ADMIN)
    assert await svc.create_order(user, "vpn_1m")


async def test_screenshot_for_someone_elses_order(svc: Service, user):
    await svc.ensure_user(OTHER, None, None)
    o = await svc.create_order(user, "vpn_1m")
    with pytest.raises(OrderNotFound):
        await svc.attach_screenshot(OTHER, o.code, "f", "u")


async def test_unpaid_orders_expire_after_24h(svc: Service, user, clock):
    o = await svc.create_order(user, "vpn_1m")
    clock.advance(hours=23)
    assert await svc.expire_stale_orders() == []
    clock.advance(hours=2)
    expired = await svc.expire_stale_orders()
    assert [x.code for x in expired] == [o.code]
    assert (await svc.get_order(o.code)).state == "expired"
    with pytest.raises(OrderBadState):
        await svc.attach_screenshot(user, o.code, "f", "u")


async def test_approve_when_panel_down_can_be_retried(svc: Service, user, transport):
    o = await _submitted(svc, user, "vpn_1m")
    transport.fail_next = 99
    from exabyte_bot.xui import PanelUnavailable

    with pytest.raises(PanelUnavailable):
        await svc.approve_order(o.code, ADMIN)
    assert (await svc.get_order(o.code)).state == "awaiting_review"
    transport.fail_next = 0
    res = await svc.approve_order(o.code, ADMIN)
    assert res.order.state == "approved" and not res.already


async def test_approve_upgrades_trial(svc: Service, user, panel):
    trial = await svc.claim_trial(user)
    o = await _submitted(svc, user, "vpn_6m")
    res = await svc.approve_order(o.code, ADMIN)
    assert res.key.email == trial.email and res.key.kind == "paid"
    assert len(panel.clients()) == 1

