"""Business rules: trials, orders/payments, renewals, key regeneration, status, usage sync.

Rules of thumb used throughout:
* One key (subscription row) per user. Renewals/upgrades update it, never add a second.
* Per-user asyncio locks serialise actions of one user, so double taps cannot race.
* The panel is called BEFORE the DB is changed where possible; if the panel is down
  we raise PanelUnavailable and nothing has changed, so the action can simply be retried.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import aiosqlite

from . import packages as P
from .db import Database
from .packages import Plan, get_plan
from .strings import t
from .util import (
    GB,
    MS_PER_DAY,
    Clock,
    days_left,
    fmt_duration_my,
    fmt_mmk,
    from_ms,
    iso,
    local_day_start_ms,
    local_month_start_ms,
    new_client_email,
    new_order_code,
    new_sub_id,
    to_ms,
    utcnow,
)
from .xui import (
    ClientSpec,
    Inbound,
    XUIClient,
    XUIError,
    build_ss_link,
    client_method_for,
    generate_password,
    traffic_from_stats,
)

log = logging.getLogger(__name__)

OPEN_STATES = ("pending_payment", "awaiting_review")


# ---------------------------------------------------------------- errors
class ServiceError(Exception):
    """Business-rule refusal. `key`/`params` map to a Burmese message in strings.py."""

    key = "generic_error"

    def __init__(self, **params: Any):
        self.params = params
        super().__init__(self.key)

    def message(self) -> str:
        return t(self.key, **self.params)


class TrialTooEarly(ServiceError):
    key = "trial_too_early"

    def __init__(self, next_at: datetime, now: datetime):
        self.next_at = next_at
        self.seconds_left = max(int((next_at - now).total_seconds()), 0)
        super().__init__(remaining=fmt_duration_my(next_at - now))


class TrialPaidActive(ServiceError):
    key = "trial_paid_active"


class OpenOrderExists(ServiceError):
    key = "order_open_exists"


class OrderNotFound(ServiceError):
    key = "order_not_found"


class OrderBadState(ServiceError):
    key = "order_bad_state"


class DuplicateScreenshot(ServiceError):
    key = "order_duplicate_screenshot"


class RegenNotAllowed(ServiceError):
    key = "regen_not_allowed"


class RegenTooEarly(ServiceError):
    key = "regen_too_early"


class NoKey(ServiceError):
    key = "no_key"


class UnknownPlan(ServiceError):
    key = "generic_error"


# ---------------------------------------------------------------- views
@dataclass
class KeyView:
    user_id: int
    kind: str
    email: str
    password: str
    link: str
    plan_id: str | None
    quota_bytes: int
    used_bytes: int
    expiry_ms: int
    enabled: bool
    status: str  # active | expired | disabled

    @property
    def unlimited(self) -> bool:
        return self.quota_bytes == 0

    @property
    def quota_exhausted(self) -> bool:
        return not self.unlimited and self.used_bytes >= self.quota_bytes


@dataclass
class Order:
    code: str
    user_id: int
    plan_id: str
    amount: int
    state: str
    screenshot_file_id: str | None
    screenshot_unique_id: str | None
    reviewed_by: int | None
    reason: str | None
    created_at: int

    @property
    def plan(self) -> Plan:
        plan = get_plan(self.plan_id)
        assert plan is not None
        return plan

    @property
    def amount_text(self) -> str:
        return fmt_mmk(self.amount)

    @classmethod
    def from_row(cls, r: aiosqlite.Row) -> Order:
        return cls(**{k: r[k] for k in cls.__dataclass_fields__})


@dataclass
class ReviewResult:
    order: Order
    key: KeyView | None
    already: bool  # True when this call was a duplicate (double tap) and changed nothing


# ---------------------------------------------------------------- service
class Service:
    def __init__(self, db: Database, xui: XUIClient, *, inbound_remark: str, server_host: str,
                 clock: Clock = utcnow):
        self.db = db
        self.xui = xui
        self.inbound_remark = inbound_remark
        self.server_host = server_host
        self.now = clock
        self._inbound: Inbound | None = None
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    # ----- startup / inbound
    async def startup(self) -> Inbound:
        ib = await self.xui.find_inbound(self.inbound_remark)
        ib.validate()
        self._inbound = ib
        log.info("using inbound id=%s port=%s method=%s", ib.id, ib.port, ib.method)
        return ib

    @property
    def inbound(self) -> Inbound:
        if self._inbound is None:
            raise RuntimeError("Service.startup() not called")
        return self._inbound

    def _lock(self, user_id: int) -> asyncio.Lock:
        return self._locks[user_id]

    def _now_ms(self) -> int:
        return to_ms(self.now())

    # ----- users
    async def ensure_user(self, tg_id: int, username: str | None = None,
                          first_name: str | None = None) -> None:
        now = self._now_ms()
        await self.db.execute(
            "INSERT INTO users(telegram_id, username, first_name, created_at, last_seen_at) "
            "VALUES (?,?,?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET "
            "username=excluded.username, first_name=excluded.first_name, "
            "last_seen_at=excluded.last_seen_at, blocked_bot=0",
            (tg_id, username, first_name, now, now),
        )

    async def is_banned(self, tg_id: int) -> bool:
        row = await self.db.fetchone("SELECT banned FROM users WHERE telegram_id=?", (tg_id,))
        return bool(row and row["banned"])

    # ----- key helpers
    def link_for(self, password: str, email: str) -> str:
        return build_ss_link(self.inbound, password, self.server_host, f"Exabyte-{email}")

    def _status(self, row: aiosqlite.Row) -> str:
        if not row["enabled"]:
            return "disabled"
        if row["expiry_ms"] <= self._now_ms():
            return "expired"
        if row["quota_bytes"] and row["used_bytes"] >= row["quota_bytes"]:
            return "expired"
        return "active"

    def _view(self, row: aiosqlite.Row) -> KeyView:
        return KeyView(
            user_id=row["user_id"], kind=row["kind"], email=row["xui_email"],
            password=row["password"], link=self.link_for(row["password"], row["xui_email"]),
            plan_id=row["plan_id"], quota_bytes=row["quota_bytes"], used_bytes=row["used_bytes"],
            expiry_ms=row["expiry_ms"], enabled=bool(row["enabled"]), status=self._status(row),
        )

    async def _sub_row(self, tg_id: int) -> aiosqlite.Row | None:
        return await self.db.fetchone("SELECT * FROM subscriptions WHERE user_id=?", (tg_id,))

    async def get_key(self, tg_id: int) -> KeyView | None:
        row = await self._sub_row(tg_id)
        return self._view(row) if row else None

    def _spec(self, tg_id: int, email: str, password: str, sub_id: str, quota: int,
              expiry_ms: int, limit_ip: int, enable: bool = True, comment: str = "") -> ClientSpec:
        return ClientSpec(
            email=email, password=password, method=client_method_for(self.inbound.method),
            total_bytes=quota, expiry_ms=expiry_ms, limit_ip=limit_ip, enable=enable,
            tg_id=tg_id, sub_id=sub_id, comment=comment,
        )

    # ----- status (bot + Mini App)
    async def trial_info(self, tg_id: int) -> dict[str, Any]:
        now = self.now()
        last = await self.db.fetchone(
            "SELECT MAX(claimed_at) AS c FROM trial_claims WHERE user_id=?", (tg_id,))
        sub = await self._sub_row(tg_id)
        paid_active = bool(sub and sub["kind"] == "paid" and self._status(sub) == "active")
        info: dict[str, Any] = {"available": True, "reason": None,
                                "next_trial_at": None, "seconds_until_next_trial": 0}
        if last and last["c"]:
            next_at = from_ms(last["c"]) + timedelta(days=P.TRIAL_COOLDOWN_DAYS)
            if now < next_at:
                info.update(available=False, reason="cooldown", next_trial_at=iso(next_at),
                            seconds_until_next_trial=int((next_at - now).total_seconds()))
        if paid_active:
            info.update(available=False, reason="paid_active")
        return info

    async def get_status(self, tg_id: int) -> dict[str, Any]:
        key = await self.get_key(tg_id)
        now = self.now()
        data: dict[str, Any] = {"has_key": key is not None, "trial": await self.trial_info(tg_id)}
        if key:
            data.update(
                kind=key.kind, status=key.status, plan_id=key.plan_id, link=key.link,
                unlimited=key.unlimited, quota_bytes=key.quota_bytes, used_bytes=key.used_bytes,
                expiry_at=iso(from_ms(key.expiry_ms)), days_left=days_left(key.expiry_ms, now),
                quota_exhausted=key.quota_exhausted,
            )
        else:
            data.update(status="none")
        return data

    # ----- trial
    async def claim_trial(self, tg_id: int) -> KeyView:
        async with self._lock(tg_id):
            info = await self.trial_info(tg_id)
            if info["reason"] == "paid_active":
                raise TrialPaidActive()
            now = self.now()
            if info["reason"] == "cooldown":
                raise TrialTooEarly(datetime.fromisoformat(info["next_trial_at"]), now)

            old = await self._sub_row(tg_id)
            if old is not None:
                # Revoke the previous key first (any kind: an expired paid key is replaced too,
                # because a user only ever holds one key). If the panel is down nothing changed.
                await self.xui.delete_client(self.inbound.id, old["xui_email"])
                async with self.db.transaction() as tx:
                    await tx.execute("DELETE FROM subscriptions WHERE user_id=?", (tg_id,))

            email, password, sub_id = new_client_email(tg_id), generate_password(
                self.inbound.method), new_sub_id()
            quota = P.TRIAL_QUOTA_GB * GB
            expiry = to_ms(now) + P.TRIAL_DAYS * MS_PER_DAY
            await self.xui.add_client(self.inbound.id, self._spec(
                tg_id, email, password, sub_id, quota, expiry, limit_ip=1, comment="trial"))
            async with self.db.transaction() as tx:
                await tx.execute(
                    "INSERT INTO subscriptions(user_id, kind, xui_email, password, sub_id, plan_id,"
                    " quota_bytes, used_bytes, expiry_ms, enabled, created_at)"
                    " VALUES (?,?,?,?,?,?,?,0,?,1,?)",
                    (tg_id, "trial", email, password, sub_id, "trial", quota, expiry, to_ms(now)),
                )
                # Claim is recorded only after the key exists, so a panel failure lets them retry.
                await tx.execute("INSERT INTO trial_claims(user_id, claimed_at) VALUES (?,?)",
                                 (tg_id, to_ms(now)))
            await self.db.audit(tg_id, "trial_claim", email, None, to_ms(now))
            key = await self.get_key(tg_id)
            assert key is not None
            return key

    # ----- plans (shared by approve + admin grant)
    async def _apply_plan(self, tg_id: int, plan: Plan) -> KeyView:
        """Create, extend or upgrade the user's single key. Caller holds the user lock."""
        now_ms = self._now_ms()
        add_ms = plan.days * MS_PER_DAY
        sub = await self._sub_row(tg_id)
        ib = self.inbound
        if sub is None:
            email, password, sub_id = new_client_email(tg_id), generate_password(ib.method), \
                new_sub_id()
            expiry = now_ms + add_ms
            await self.xui.add_client(ib.id, self._spec(
                tg_id, email, password, sub_id, plan.quota_bytes, expiry, plan.devices,
                comment=plan.id))
            async with self.db.transaction() as tx:
                await tx.execute(
                    "INSERT INTO subscriptions(user_id, kind, xui_email, password, sub_id, plan_id,"
                    " quota_bytes, used_bytes, expiry_ms, enabled, created_at)"
                    " VALUES (?,?,?,?,?,?,?,0,?,1,?)",
                    (tg_id, "paid", email, password, sub_id, plan.id, plan.quota_bytes, expiry,
                     now_ms),
                )
        else:
            was_trial = sub["kind"] == "trial"
            # Active paid keys extend from current expiry; trials and expired keys start now.
            base = sub["expiry_ms"] if (not was_trial and sub["expiry_ms"] > now_ms) else now_ms
            expiry = base + add_ms
            await self.xui.update_client(ib.id, self._spec(
                tg_id, sub["xui_email"], sub["password"], sub["sub_id"], plan.quota_bytes,
                expiry, plan.devices, comment=plan.id))
            if was_trial:
                # Trial usage must not count against the paid plan.
                await self.xui.reset_traffic(ib.id, sub["xui_email"])
            async with self.db.transaction() as tx:
                await tx.execute(
                    "UPDATE subscriptions SET kind='paid', plan_id=?, quota_bytes=?, expiry_ms=?,"
                    " enabled=1, notified_flags='',"
                    " used_bytes=CASE WHEN ? THEN 0 ELSE used_bytes END WHERE user_id=?",
                    (plan.id, plan.quota_bytes, expiry, int(was_trial), tg_id),
                )
        key = await self.get_key(tg_id)
        assert key is not None
        return key

    async def grant_plan(self, admin_id: int, tg_id: int, plan_id: str) -> KeyView:
        plan = get_plan(plan_id)
        if plan is None:
            raise UnknownPlan()
        async with self._lock(tg_id):
            key = await self._apply_plan(tg_id, plan)
        await self.db.audit(admin_id, "grant_plan", str(tg_id), {"plan": plan_id}, self._now_ms())
        return key

    # ----- orders
    async def _order(self, code: str) -> Order | None:
        row = await self.db.fetchone("SELECT * FROM orders WHERE code=?", (code,))
        return Order.from_row(row) if row else None

    async def get_order(self, code: str) -> Order | None:
        return await self._order(code)

    async def open_order(self, tg_id: int) -> Order | None:
        row = await self.db.fetchone(
            "SELECT * FROM orders WHERE user_id=? AND state IN (?,?)", (tg_id, *OPEN_STATES))
        return Order.from_row(row) if row else None

    async def create_order(self, tg_id: int, plan_id: str) -> Order:
        plan = get_plan(plan_id)
        if plan is None:
            raise UnknownPlan()
        async with self._lock(tg_id):
            await self.expire_stale_orders(user_id=tg_id)
            existing = await self.open_order(tg_id)
            if existing:
                raise OpenOrderExists(code=existing.code)
            now = self._now_ms()
            for _ in range(5):  # retry on the (astronomically rare) code collision
                code = new_order_code()
                try:
                    async with self.db.transaction() as tx:
                        await tx.execute(
                            "INSERT INTO orders(code, user_id, plan_id, amount, state, created_at,"
                            " updated_at) VALUES (?,?,?,?,'pending_payment',?,?)",
                            (code, tg_id, plan.id, plan.price_mmk, now, now),
                        )
                    break
                except aiosqlite.IntegrityError as e:
                    if "uq_orders_open_per_user" in str(e) or "orders.user_id" in str(e):
                        raise OpenOrderExists(code="?") from None
            order = await self._order(code)
            assert order is not None
            return order

    async def cancel_order(self, tg_id: int, code: str) -> None:
        async with self._lock(tg_id):
            n = await self.db.execute(
                "UPDATE orders SET state='cancelled', updated_at=? "
                "WHERE code=? AND user_id=? AND state IN (?,?)",
                (self._now_ms(), code, tg_id, *OPEN_STATES))
            if n == 0:
                raise OrderBadState()

    async def attach_screenshot(self, tg_id: int, code: str, file_id: str,
                                file_unique_id: str) -> Order:
        async with self._lock(tg_id):
            order = await self._order(code)
            if order is None or order.user_id != tg_id:
                raise OrderNotFound()
            if order.state not in OPEN_STATES:
                raise OrderBadState()
            dup = await self.db.fetchone(
                "SELECT code FROM orders WHERE screenshot_unique_id=? AND code<>?",
                (file_unique_id, code))
            if dup:
                raise DuplicateScreenshot()
            now = self._now_ms()
            try:
                await self.db.execute(
                    "UPDATE orders SET screenshot_file_id=?, screenshot_unique_id=?,"
                    " state='awaiting_review', submitted_at=?, updated_at=? WHERE code=?",
                    (file_id, file_unique_id, now, now, code))
            except aiosqlite.IntegrityError:
                raise DuplicateScreenshot() from None
            order = await self._order(code)
            assert order is not None
            return order

    async def approve_order(self, code: str, admin_id: int) -> ReviewResult:
        order = await self._order(code)
        if order is None:
            raise OrderNotFound()
        async with self._lock(order.user_id):
            now = self._now_ms()
            # Claim the order atomically FIRST. Only the caller that flips the state provisions,
            # so a double tap (or two admins) can never extend the key twice.
            claimed = await self.db.execute(
                "UPDATE orders SET state='approved', reviewed_by=?, reviewed_at=?, updated_at=?"
                " WHERE code=? AND state='awaiting_review'", (admin_id, now, now, code))
            if not claimed:
                current = await self._order(code)
                assert current is not None
                if current.state == "approved":
                    return ReviewResult(current, await self.get_key(order.user_id), already=True)
                raise OrderBadState()
            try:
                key = await self._apply_plan(order.user_id, order.plan)
            except XUIError:
                # Undo the claim so the admin can simply tap Approve again later.
                await self.db.execute(
                    "UPDATE orders SET state='awaiting_review', reviewed_by=NULL, reviewed_at=NULL"
                    " WHERE code=?", (code,))
                raise
        await self.db.audit(admin_id, "order_approve", code,
                            {"user": order.user_id, "plan": order.plan_id}, now)
        final = await self._order(code)
        assert final is not None
        return ReviewResult(final, key, already=False)

    async def reject_order(self, code: str, admin_id: int, reason: str | None = None) -> ReviewResult:
        order = await self._order(code)
        if order is None:
            raise OrderNotFound()
        now = self._now_ms()
        n = await self.db.execute(
            "UPDATE orders SET state='rejected', reviewed_by=?, reviewed_at=?, updated_at=?,"
            " reason=? WHERE code=? AND state IN (?,?)",
            (admin_id, now, now, reason, code, *OPEN_STATES))
        current = await self._order(code)
        assert current is not None
        if not n:
            if current.state == "rejected":
                return ReviewResult(current, None, already=True)
            raise OrderBadState()
        await self.db.audit(admin_id, "order_reject", code, {"reason": reason}, now)
        return ReviewResult(current, None, already=False)

    async def expire_stale_orders(self, user_id: int | None = None) -> list[Order]:
        cutoff = self._now_ms() - P.ORDER_EXPIRY_HOURS * 3_600_000
        # Only unpaid orders expire; ones with a screenshot wait for the admin.
        sql = "SELECT * FROM orders WHERE state='pending_payment' AND created_at < ?"
        params: tuple[Any, ...] = (cutoff,)
        if user_id is not None:
            sql += " AND user_id=?"
            params += (user_id,)
        rows = [Order.from_row(r) for r in await self.db.fetchall(sql, params)]
        for o in rows:
            await self.db.execute(
                "UPDATE orders SET state='expired', updated_at=? WHERE code=? AND"
                " state='pending_payment'", (self._now_ms(), o.code))
            o.state = "expired"
        return rows

    # ----- key regeneration
    async def regenerate_key(self, tg_id: int) -> KeyView:
        async with self._lock(tg_id):
            sub = await self._sub_row(tg_id)
            if sub is None:
                raise NoKey()
            if sub["kind"] != "paid" or self._status(sub) != "active":
                raise RegenNotAllowed()
            now = self.now()
            last = sub["last_regenerated_at"]
            if last:
                next_at = from_ms(last) + timedelta(hours=P.REGENERATE_COOLDOWN_HOURS)
                if now < next_at:
                    raise RegenTooEarly(remaining=fmt_duration_my(next_at - now))
            password = generate_password(self.inbound.method)
            await self.xui.update_client(self.inbound.id, self._spec(
                tg_id, sub["xui_email"], password, sub["sub_id"], sub["quota_bytes"],
                sub["expiry_ms"], P.PAID_DEVICES, comment=sub["plan_id"] or ""))
            async with self.db.transaction() as tx:
                await tx.execute(
                    "UPDATE subscriptions SET password=?, last_regenerated_at=? WHERE user_id=?",
                    (password, to_ms(now), tg_id))
            await self.db.audit(tg_id, "key_regenerate", sub["xui_email"], None, to_ms(now))
            key = await self.get_key(tg_id)
            assert key is not None
            return key

    # ----- background sync
    async def sync_usage(self) -> list[KeyView]:
        """Pull traffic for all clients in one call, store it, and disable expired clients.

        Returns the refreshed keys so the jobs module can decide on notifications.
        """
        ib = await self.xui.get_inbound(self.inbound.id)
        stats = traffic_from_stats(ib.client_stats)
        now_ms = self._now_ms()
        refreshed: list[KeyView] = []
        for sub in await self.db.fetchall("SELECT * FROM subscriptions"):
            tr = stats.get(sub["xui_email"])
            if tr is not None:
                async with self.db.transaction() as tx:
                    await tx.execute("UPDATE subscriptions SET used_bytes=? WHERE id=?",
                                     (tr.used, sub["id"]))
                    await tx.execute(
                        "INSERT INTO usage_snapshots(user_id, xui_email, up_bytes, down_bytes,"
                        " taken_at) VALUES (?,?,?,?,?)",
                        (sub["user_id"], sub["xui_email"], tr.up, tr.down, now_ms))
            row = await self._sub_row(sub["user_id"])
            assert row is not None
            # Belt and braces: make sure an expired client is really disabled on the panel.
            if row["expiry_ms"] <= now_ms and tr is not None and tr.enable:
                await self.xui.update_client(ib.id, self._spec(
                    row["user_id"], row["xui_email"], row["password"], row["sub_id"],
                    row["quota_bytes"], row["expiry_ms"], 1, enable=False,
                    comment=row["plan_id"] or ""))
            refreshed.append(self._view(row))
        return refreshed

    # ----- notifications (each event fires once per subscription lifecycle)
    async def collect_notifications(self) -> list[tuple[int, str, KeyView]]:
        """Return (user_id, event_name, key_view) for unsent alerts."""
        now_ms = self._now_ms()
        events: list[tuple[int, str, KeyView]] = []
        rows = await self.db.fetchall(
            "SELECT s.* FROM subscriptions s JOIN users u ON u.telegram_id=s.user_id "
            "WHERE u.blocked_bot=0 AND u.banned=0 AND s.enabled=1"
        )
        for row in rows:
            flags = {f for f in (row["notified_flags"] or "").split(",") if f}
            kv = self._view(row)
            rem_ms = row["expiry_ms"] - now_ms
            if rem_ms <= 0 and "expired" not in flags:
                events.append((row["user_id"], "expired", kv))
            elif 0 < rem_ms <= MS_PER_DAY and "expiring_1d" not in flags:
                events.append((row["user_id"], "expiring_1d", kv))
            if row["kind"] == "trial" and row["quota_bytes"] > 0:
                ratio = row["used_bytes"] / row["quota_bytes"]
                if ratio >= 1.0 and "quota_100" not in flags:
                    events.append((row["user_id"], "quota_100", kv))
                elif ratio >= 0.8 and "quota_80" not in flags:
                    events.append((row["user_id"], "quota_80", kv))
        return events

    async def mark_notified(self, tg_id: int, event: str) -> None:
        row = await self._sub_row(tg_id)
        if not row:
            return
        flags = {f for f in (row["notified_flags"] or "").split(",") if f}
        flags.add(event)
        await self.db.execute(
            "UPDATE subscriptions SET notified_flags=? WHERE user_id=?",
            (",".join(sorted(flags)), tg_id),
        )

    async def mark_blocked(self, tg_id: int) -> None:
        await self.db.execute("UPDATE users SET blocked_bot=1 WHERE telegram_id=?", (tg_id,))

    # ----- admin operations (all audited)
    async def pending_orders(self) -> list[Order]:
        rows = await self.db.fetchall(
            "SELECT * FROM orders WHERE state='awaiting_review' ORDER BY submitted_at ASC"
        )
        return [Order.from_row(r) for r in rows]

    async def stats(self) -> dict[str, int]:
        now = self.now()
        now_ms = to_ms(now)
        day_ms = local_day_start_ms(now)
        month_ms = local_month_start_ms(now)
        u = await self.db.fetchone("SELECT COUNT(*) AS c FROM users")
        paid = await self.db.fetchone(
            "SELECT COUNT(*) AS c FROM subscriptions WHERE kind='paid' AND enabled=1 AND expiry_ms>?",
            (now_ms,),
        )
        trial = await self.db.fetchone(
            "SELECT COUNT(*) AS c FROM subscriptions WHERE kind='trial' AND enabled=1 AND expiry_ms>?"
            " AND (quota_bytes=0 OR used_bytes<quota_bytes)",
            (now_ms,),
        )
        pend = await self.db.fetchone(
            "SELECT COUNT(*) AS c FROM orders WHERE state='awaiting_review'"
        )
        rev_day = await self.db.fetchone(
            "SELECT COALESCE(SUM(amount),0) AS s FROM orders WHERE state='approved' AND reviewed_at>=?",
            (day_ms,),
        )
        rev_month = await self.db.fetchone(
            "SELECT COALESCE(SUM(amount),0) AS s FROM orders WHERE state='approved' AND reviewed_at>=?",
            (month_ms,),
        )
        return {
            "total_users": int(u["c"]) if u else 0,
            "active_paid": int(paid["c"]) if paid else 0,
            "active_trials": int(trial["c"]) if trial else 0,
            "pending_orders": int(pend["c"]) if pend else 0,
            "today_revenue": int(rev_day["s"]) if rev_day else 0,
            "month_revenue": int(rev_month["s"]) if rev_month else 0,
        }

    async def find_user(self, query: str) -> dict[str, Any] | None:
        q = query.strip().lstrip("@")
        if q.isdigit():
            u = await self.db.fetchone("SELECT * FROM users WHERE telegram_id=?", (int(q),))
        else:
            u = await self.db.fetchone(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (q,)
            )
        if not u:
            return None
        uid = int(u["telegram_id"])
        oc = await self.db.fetchone("SELECT COUNT(*) AS c FROM orders WHERE user_id=?", (uid,))
        return {
            "user_id": uid,
            "username": u["username"] or "-",
            "banned": bool(u["banned"]),
            "key": await self.get_key(uid),
            "order_count": int(oc["c"]) if oc else 0,
        }

    async def admin_adjust_key(
        self, admin_id: int, tg_id: int, *, add_days: int = 0, add_gb: int = 0
    ) -> KeyView:
        async with self._lock(tg_id):
            sub = await self._sub_row(tg_id)
            if sub is None:
                raise NoKey()
            now_ms = self._now_ms()
            base_exp = max(int(sub["expiry_ms"]), now_ms) if add_days > 0 else int(sub["expiry_ms"])
            new_exp = base_exp + add_days * MS_PER_DAY
            cur_quota = int(sub["quota_bytes"])
            new_quota = cur_quota + add_gb * GB if (cur_quota > 0 and add_gb > 0) else cur_quota
            await self.xui.update_client(
                self.inbound.id,
                self._spec(
                    tg_id, sub["xui_email"], sub["password"], sub["sub_id"],
                    new_quota, new_exp, 1, enable=True, comment=sub["plan_id"] or "",
                ),
            )
            async with self.db.transaction() as tx:
                await tx.execute(
                    "UPDATE subscriptions SET expiry_ms=?, quota_bytes=?, enabled=1,"
                    " notified_flags='' WHERE user_id=?",
                    (new_exp, new_quota, tg_id),
                )
        await self.db.audit(
            admin_id, "admin_adjust_key", str(tg_id),
            {"add_days": add_days, "add_gb": add_gb}, self._now_ms(),
        )
        key = await self.get_key(tg_id)
        assert key is not None
        return key

    async def admin_revoke_key(self, admin_id: int, tg_id: int) -> None:
        async with self._lock(tg_id):
            sub = await self._sub_row(tg_id)
            if sub is None:
                raise NoKey()
            await self.xui.delete_client(self.inbound.id, sub["xui_email"])
            async with self.db.transaction() as tx:
                await tx.execute("DELETE FROM subscriptions WHERE user_id=?", (tg_id,))
        await self.db.audit(admin_id, "admin_revoke_key", str(tg_id), None, self._now_ms())

    async def admin_set_banned(self, admin_id: int, tg_id: int, banned: bool) -> None:
        await self.db.execute(
            "UPDATE users SET banned=? WHERE telegram_id=?", (int(banned), tg_id)
        )
        await self.db.audit(
            admin_id, "ban_user" if banned else "unban_user", str(tg_id), None, self._now_ms()
        )

    async def is_maintenance(self) -> bool:
        return (await self.db.get_setting("maintenance", "0")) == "1"

    async def toggle_maintenance(self, admin_id: int) -> bool:
        new_val = not (await self.is_maintenance())
        await self.db.set_setting("maintenance", "1" if new_val else "0")
        await self.db.audit(
            admin_id, "maintenance_toggle", None, {"enabled": new_val}, self._now_ms()
        )
        return new_val

    async def broadcast_recipients(self) -> list[int]:
        rows = await self.db.fetchall(
            "SELECT telegram_id FROM users WHERE blocked_bot=0 AND banned=0 ORDER BY telegram_id"
        )
        return [int(r["telegram_id"]) for r in rows]

    async def export_orders_csv(self, admin_id: int) -> bytes:
        rows = await self.db.fetchall("SELECT * FROM orders ORDER BY created_at DESC")
        buf = io.StringIO()
        writer = csv.writer(buf)
        cols = [
            "code", "user_id", "plan_id", "amount", "state",
            "reviewed_by", "reason", "created_at", "submitted_at", "reviewed_at",
        ]
        writer.writerow(cols)
        for r in rows:
            writer.writerow([r[c] for c in cols])
        await self.db.audit(
            admin_id, "export_orders_csv", None, {"rows": len(rows)}, self._now_ms()
        )
        return buf.getvalue().encode("utf-8")

