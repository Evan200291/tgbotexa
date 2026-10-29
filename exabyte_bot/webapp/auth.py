"""Server-side validation of Telegram WebApp initData (HMAC-SHA256) and Web Admin tokens.

Never trust a user_id sent directly by the client: every identity comes from a verified
Telegram signature (or, in local DEV_MODE on localhost only, the dev user).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl

from ..util import utcnow

MAX_AUTH_AGE_SEC = 86_400  # 24 hours


class AuthError(ValueError):
    """Raised when initData or admin token is missing, forged, or expired."""


@dataclass(frozen=True)
class WebAppUser:
    id: int
    first_name: str = ""
    username: str | None = None
    language_code: str = "my"


def build_init_data(
    user: dict[str, object], bot_token: str, *, auth_date: int | None = None
) -> str:
    """Helper used by tests to sign valid Telegram WebApp initData."""
    from urllib.parse import urlencode

    ts = auth_date if auth_date is not None else int(utcnow().timestamp())
    fields = {
        "auth_date": str(ts),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user, separators=(",", ":")),
    }
    check_str = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    sig = hmac.new(secret_key, check_str.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": sig})


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    now: datetime | None = None,
    max_age_sec: int = MAX_AUTH_AGE_SEC,
) -> WebAppUser:
    if not init_data or not bot_token:
        raise AuthError("Missing Telegram initData")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        raise AuthError("Missing hash in initData")

    check_str = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret_key, check_str.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise AuthError("Invalid initData signature")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as err:
        raise AuthError("Invalid auth_date") from err

    now_ts = int((now or utcnow()).timestamp())
    age = now_ts - auth_date
    if age > max_age_sec or age < -300:
        raise AuthError("Expired initData")

    try:
        u = json.loads(pairs.get("user", "{}"))
        uid = int(u["id"])
    except (ValueError, KeyError, TypeError) as err:
        raise AuthError("Missing user in initData") from err

    return WebAppUser(
        id=uid,
        first_name=str(u.get("first_name") or ""),
        username=u.get("username"),
        language_code=str(u.get("language_code") or "my"),
    )


def create_admin_web_token(
    admin_id: int, bot_token: str, *, now: datetime | None = None
) -> str:
    ts = int((now or utcnow()).timestamp())
    payload = f"{admin_id}:{ts}"
    key = hmac.new(b"ExabyteWebAdmin", bot_token.encode("utf-8"), hashlib.sha256).digest()
    sig = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{payload}:{sig}"


def verify_admin_web_token(
    token: str,
    bot_token: str,
    *,
    now: datetime | None = None,
    max_age_sec: int = MAX_AUTH_AGE_SEC,
) -> WebAppUser:
    parts = (token or "").split(":")
    if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
        raise AuthError("Invalid admin token")
    admin_id, ts, sig = int(parts[0]), int(parts[1]), parts[2]
    now_ts = int((now or utcnow()).timestamp())
    if now_ts - ts > max_age_sec or now_ts - ts < -300:
        raise AuthError("Expired admin token")
    payload = f"{admin_id}:{ts}"
    key = hmac.new(b"ExabyteWebAdmin", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected, sig):
        raise AuthError("Bad admin token signature")
    return WebAppUser(id=admin_id, first_name="Admin", username="admin")
