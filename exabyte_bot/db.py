"""SQLite storage (WAL) with simple versioned migrations.

One shared aiosqlite connection in autocommit mode; we issue BEGIN IMMEDIATE ourselves
inside `transaction()`. An asyncio.Lock serialises transactions because a single
connection cannot interleave two of them (and SQLite has one writer anyway).
All timestamps are UTC epoch milliseconds (ints) to match 3X-UI's expiryTime.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

MIGRATIONS: list[str] = [
    # v1: initial schema
    """
    CREATE TABLE users (
        telegram_id   INTEGER PRIMARY KEY,
        username      TEXT,
        first_name    TEXT,
        language      TEXT NOT NULL DEFAULT 'my',
        banned        INTEGER NOT NULL DEFAULT 0,
        blocked_bot   INTEGER NOT NULL DEFAULT 0,
        created_at    INTEGER NOT NULL,
        last_seen_at  INTEGER
    );
    CREATE INDEX idx_users_username ON users(username COLLATE NOCASE);

    -- Exactly one key per user (UNIQUE user_id): trial upgrades / renewals reuse the row.
    CREATE TABLE subscriptions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id             INTEGER NOT NULL UNIQUE REFERENCES users(telegram_id),
        kind                TEXT NOT NULL CHECK (kind IN ('trial','paid')),
        xui_email           TEXT NOT NULL UNIQUE,
        password            TEXT NOT NULL,
        sub_id              TEXT NOT NULL,
        plan_id             TEXT,
        quota_bytes         INTEGER NOT NULL DEFAULT 0,
        used_bytes          INTEGER NOT NULL DEFAULT 0,
        expiry_ms           INTEGER NOT NULL,
        enabled             INTEGER NOT NULL DEFAULT 1,
        created_at          INTEGER NOT NULL,
        last_regenerated_at INTEGER,
        notified_flags      TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE trial_claims (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(telegram_id),
        claimed_at INTEGER NOT NULL
    );
    CREATE INDEX idx_trial_user ON trial_claims(user_id, claimed_at);

    CREATE TABLE orders (
        code                  TEXT PRIMARY KEY,
        user_id               INTEGER NOT NULL REFERENCES users(telegram_id),
        plan_id               TEXT NOT NULL,
        amount                INTEGER NOT NULL,
        state                 TEXT NOT NULL CHECK (state IN
                                ('pending_payment','awaiting_review','approved','rejected','expired','cancelled')),
        screenshot_file_id    TEXT,
        screenshot_unique_id  TEXT,
        reviewed_by           INTEGER,
        reason                TEXT,
        created_at            INTEGER NOT NULL,
        updated_at            INTEGER NOT NULL,
        submitted_at          INTEGER,
        reviewed_at           INTEGER
    );
    -- DB-level guarantees, so even racing requests cannot break the rules:
    CREATE UNIQUE INDEX uq_orders_open_per_user ON orders(user_id)
        WHERE state IN ('pending_payment','awaiting_review');
    CREATE UNIQUE INDEX uq_orders_screenshot ON orders(screenshot_unique_id)
        WHERE screenshot_unique_id IS NOT NULL;
    CREATE INDEX idx_orders_state ON orders(state, created_at);

    CREATE TABLE usage_snapshots (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        xui_email  TEXT NOT NULL,
        up_bytes   INTEGER NOT NULL,
        down_bytes INTEGER NOT NULL,
        taken_at   INTEGER NOT NULL
    );
    CREATE INDEX idx_usage_user ON usage_snapshots(user_id, taken_at);

    CREATE TABLE audit_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_id   INTEGER,
        action     TEXT NOT NULL,
        target     TEXT,
        details    TEXT,
        created_at INTEGER NOT NULL
    );

    CREATE TABLE settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
]


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._conn: aiosqlite.Connection | None = None
        # NOTE: never call db.execute()/audit() while holding transaction(): same lock.
        self._tx_lock = asyncio.Lock()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected")
        return self._conn

    async def connect(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path, isolation_level=None)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._migrate()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _migrate(self) -> None:
        await self.conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        row = await self.fetchone("SELECT MAX(version) AS v FROM schema_version")
        current = (row["v"] if row else None) or 0
        for version, sql in enumerate(MIGRATIONS, start=1):
            if version <= current:
                continue
            async with self.transaction() as tx:
                # executescript would COMMIT implicitly, so split statements ourselves.
                for stmt in _split_sql(sql):
                    await tx.execute(stmt)
                await tx.execute("INSERT INTO schema_version(version) VALUES (?)", (version,))

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        async with self._tx_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                await self.conn.execute("ROLLBACK")
                raise
            else:
                await self.conn.execute("COMMIT")

    # --- convenience (autocommit, outside explicit transactions) ---
    async def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Row | None:
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchone()

    async def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
        async with self.conn.execute(sql, params) as cur:
            return list(await cur.fetchall())

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        async with self._tx_lock:
            cur = await self.conn.execute(sql, params)
            return cur.rowcount

    async def audit(self, actor_id: int | None, action: str, target: str | None,
                    details: dict[str, Any] | None, now_ms: int) -> None:
        await self.execute(
            "INSERT INTO audit_log(actor_id, action, target, details, created_at) VALUES (?,?,?,?,?)",
            (actor_id, action, target, json.dumps(details or {}, ensure_ascii=False), now_ms),
        )

    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = await self.fetchone("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    async def backup_to(self, dest: Path) -> Path:
        """Consistent online backup (safe while the bot is writing)."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(dest)) as target:
            await self.conn.backup(target)
        return dest


def _split_sql(script: str) -> list[str]:
    stmts, buf = [], []
    for line in script.splitlines():
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";")
            if stmt:
                stmts.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts
