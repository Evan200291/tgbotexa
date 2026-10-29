"""Small pure helpers: time, money formatting, identifiers."""

from __future__ import annotations

import secrets
import string
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

MS_PER_DAY = 86_400_000
GB = 1024**3

# Unambiguous alphabet for codes customers type into a payment note (no 0/O/1/I/L).
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def from_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def days_left(expiry_ms: int, now: datetime) -> int:
    """Whole days remaining, rounded up so '3 hours left' shows as 1 day."""
    remaining = expiry_ms - to_ms(now)
    if remaining <= 0:
        return 0
    return -(-remaining // MS_PER_DAY)


def fmt_mmk(amount: int) -> str:
    return f"{amount:,} ကျပ်"


def fmt_bytes(n: int) -> str:
    if n >= GB:
        return f"{n / GB:.2f} GB"
    return f"{n / 1024**2:.0f} MB"


def fmt_duration_my(td: timedelta) -> str:
    """Burmese 'X ရက် Y နာရီ Z မိနစ်' for countdown messages."""
    total = max(int(td.total_seconds()), 0)
    d, rem = divmod(total, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    parts = []
    if d:
        parts.append(f"{d} ရက်")
    if h:
        parts.append(f"{h} နာရီ")
    if m or not parts:
        # Never show "0 minutes" alone: under a minute left still reads as 1 minute.
        parts.append(f"{m if parts else max(m, 1)} မိနစ်")
    return " ".join(parts)


def new_order_code() -> str:
    return "EX" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


def new_client_email(telegram_id: int) -> str:
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"tg{telegram_id}-{suffix}"


def new_sub_id() -> str:
    return secrets.token_hex(8)


# Myanmar Standard Time (UTC+6:30, no DST) for local dates and 'today'/'this month' stats.
MMT = timedelta(hours=6, minutes=30)


def fmt_date(ms: int) -> str:
    return (from_ms(ms) + MMT).strftime("%Y-%m-%d %H:%M")


def local_day_start_ms(now: datetime) -> int:
    local = now.astimezone(UTC) + MMT
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return to_ms(start - MMT)


def local_month_start_ms(now: datetime) -> int:
    local = now.astimezone(UTC) + MMT
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return to_ms(start - MMT)

