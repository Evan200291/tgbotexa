"""Async client for the 3X-UI panel API + Shadowsocks key/link helpers.

Security: the base URL contains the panel's secret path and the credentials are secret,
so this module never logs or puts full URLs, cookies or credentials into exceptions.
Endpoints match 3X-UI 2.x (verify against the installed version):
  POST /login
  GET  /panel/api/inbounds/list, /panel/api/inbounds/get/{id}
  POST /panel/api/inbounds/addClient, /updateClient/{email}, /{id}/delClient/{email}
  POST /panel/api/inbounds/{id}/resetClientTraffic/{email}
  GET  /panel/api/inbounds/getClientTraffics/{email}
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import secrets
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx
import qrcode

log = logging.getLogger(__name__)

API = "/panel/api/inbounds"

# Shadowsocks-2022 ciphers need a base64 key of an exact byte length.
SS2022_KEY_BYTES = {
    "2022-blake3-aes-128-gcm": 16,
    "2022-blake3-aes-256-gcm": 32,
    "2022-blake3-chacha20-poly1305": 32,
}
# Xray supports per-user keys for 2022 only with the AES variants.
SS2022_MULTIUSER = {"2022-blake3-aes-128-gcm", "2022-blake3-aes-256-gcm"}
LEGACY_CIPHERS = {
    "aes-128-gcm", "aes-256-gcm", "chacha20-poly1305", "chacha20-ietf-poly1305",
    "xchacha20-poly1305", "xchacha20-ietf-poly1305",
}


class XUIError(Exception):
    """Base error for panel problems."""


class PanelUnavailable(XUIError):
    """Network error / timeout / 5xx after all retries. Callers should tell the user to wait."""


class PanelAuthError(XUIError):
    """Login rejected (wrong credentials or base path)."""


class PanelAPIError(XUIError):
    """Panel answered but reported failure (success=false)."""


class InboundNotFound(XUIError):
    pass


def is_ss2022(method: str) -> bool:
    return method.startswith("2022-")


def generate_password(method: str) -> str:
    if is_ss2022(method):
        return base64.b64encode(secrets.token_bytes(SS2022_KEY_BYTES[method])).decode()
    # Legacy AEAD ciphers accept any string; 16 url-safe chars = 96 bits of entropy.
    return secrets.token_urlsafe(12)


def client_method_for(inbound_method: str) -> str:
    """3X-UI stores an empty client method for 2022 inbounds (the inbound holds it)."""
    return "" if is_ss2022(inbound_method) else inbound_method


@dataclass(frozen=True)
class Inbound:
    id: int
    remark: str
    port: int
    method: str
    server_key: str | None
    clients: list[dict[str, Any]] = field(default_factory=list, compare=False)
    client_stats: list[dict[str, Any]] = field(default_factory=list, compare=False)

    def validate(self) -> None:
        m = self.method
        if is_ss2022(m):
            if m not in SS2022_MULTIUSER:
                raise XUIError(f"Cipher {m} does not support per-user keys; use an AES-2022 cipher.")
            if not self.server_key:
                raise XUIError("2022 inbound has no server key in its settings.")
        elif m not in LEGACY_CIPHERS:
            raise XUIError(f"Unsupported Shadowsocks method: {m}")


@dataclass
class ClientSpec:
    email: str
    password: str
    method: str
    total_bytes: int  # 0 = unlimited
    expiry_ms: int  # epoch MILLISECONDS, 0 = never
    limit_ip: int
    enable: bool
    tg_id: int
    sub_id: str
    comment: str = ""

    def to_panel(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "password": self.password,
            "method": self.method,
            "totalGB": self.total_bytes,  # despite the name, 3X-UI expects BYTES
            "expiryTime": self.expiry_ms,
            "limitIp": self.limit_ip,
            "enable": self.enable,
            "tgId": self.tg_id,
            "subId": self.sub_id,
            "comment": self.comment,
            "reset": 0,
        }


@dataclass(frozen=True)
class Traffic:
    email: str
    up: int
    down: int
    total: int
    expiry_ms: int
    enable: bool

    @property
    def used(self) -> int:
        return self.up + self.down


def parse_inbound(obj: dict[str, Any]) -> Inbound:
    settings = obj.get("settings") or "{}"
    if isinstance(settings, str):
        settings = json.loads(settings)
    method = settings.get("method", "")
    return Inbound(
        id=int(obj["id"]),
        remark=obj.get("remark", ""),
        port=int(obj["port"]),
        method=method,
        server_key=settings.get("password") if is_ss2022(method) else None,
        clients=list(settings.get("clients") or []),
        client_stats=list(obj.get("clientStats") or []),
    )


def build_ss_link(inbound: Inbound, password: str, host: str, remark: str) -> str:
    if is_ss2022(inbound.method):
        userinfo = f"{inbound.method}:{inbound.server_key}:{password}"
    else:
        userinfo = f"{inbound.method}:{password}"
    b64 = base64.urlsafe_b64encode(userinfo.encode()).decode().rstrip("=")
    return f"ss://{b64}@{host}:{inbound.port}#{quote(remark, safe='')}"


def qr_png(data: str) -> bytes:
    img = qrcode.make(data, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class XUIClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        verify_tls: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
        retries: int = 3,
        backoff: float = 0.5,
    ):
        self._username = username
        self._password = password
        self._retries = retries
        self._backoff = backoff
        self._login_lock = asyncio.Lock()
        self._logged_in = False
        # follow_redirects=False: a redirect to the login page means "session expired".
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            verify=verify_tls,
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---------------- low level ----------------
    async def _send(self, method: str, path: str, data: dict[str, Any] | None) -> httpx.Response:
        """One HTTP call with retry/backoff on network errors and 5xx."""
        last: Exception | None = None
        for attempt in range(self._retries):
            try:
                resp = await self._http.request(method, path, data=data)
                if resp.status_code < 500:
                    return resp
                last = XUIError(f"panel HTTP {resp.status_code}")
            except httpx.TransportError as e:  # connect/read timeouts, DNS, refused...
                last = e
            if attempt < self._retries - 1:
                await asyncio.sleep(self._backoff * (2**attempt))
        # Only the exception type is logged: messages may contain the secret URL.
        log.warning("panel unreachable on %s %s (%s)", method, _safe_path(path), type(last).__name__)
        raise PanelUnavailable("3X-UI panel is unreachable") from None

    async def login(self) -> None:
        async with self._login_lock:
            resp = await self._send("POST", "/login",
                                    {"username": self._username, "password": self._password})
            ok = resp.status_code == 200 and _json(resp).get("success") is True
            if not ok:
                self._logged_in = False
                raise PanelAuthError("3X-UI login failed (check PANEL_USER/PANEL_PASS/PANEL_BASE_URL)")
            self._logged_in = True

    async def _api(self, method: str, path: str, data: dict[str, Any] | None = None) -> Any:
        if not self._logged_in:
            await self.login()
        resp = await self._send(method, path, data)
        # Expired session: 401/403, redirect to login, or 404 (newer 3X-UI hides the API).
        if resp.status_code in (401, 403, 404) or resp.is_redirect:
            await self.login()
            resp = await self._send(method, path, data)
        if resp.status_code != 200:
            raise PanelAPIError(f"panel HTTP {resp.status_code} on {_safe_path(path)}")
        body = _json(resp)
        if not body.get("success"):
            raise PanelAPIError(f"panel error on {_safe_path(path)}: {body.get('msg', '')}")
        return body.get("obj")

    # ---------------- inbounds ----------------
    async def list_inbounds(self) -> list[Inbound]:
        return [parse_inbound(o) for o in (await self._api("GET", f"{API}/list") or [])]

    async def get_inbound(self, inbound_id: int) -> Inbound:
        return parse_inbound(await self._api("GET", f"{API}/get/{inbound_id}"))

    async def find_inbound(self, remark: str) -> Inbound:
        for ib in await self.list_inbounds():
            if ib.remark == remark:
                return ib
        raise InboundNotFound(f"No inbound with remark '{remark}' on the panel")

    # ---------------- clients ----------------
    async def add_client(self, inbound_id: int, spec: ClientSpec) -> None:
        await self._api("POST", f"{API}/addClient", _client_form(inbound_id, spec))

    async def update_client(self, inbound_id: int, spec: ClientSpec) -> None:
        # For Shadowsocks the client identifier in the URL is the email.
        await self._api("POST", f"{API}/updateClient/{quote(spec.email)}",
                        _client_form(inbound_id, spec))

    async def delete_client(self, inbound_id: int, email: str, *, missing_ok: bool = True) -> None:
        try:
            await self._api("POST", f"{API}/{inbound_id}/delClient/{quote(email)}")
        except PanelAPIError:
            if not missing_ok:
                raise

    async def reset_traffic(self, inbound_id: int, email: str) -> None:
        await self._api("POST", f"{API}/{inbound_id}/resetClientTraffic/{quote(email)}")

    async def get_traffic(self, email: str) -> Traffic | None:
        obj = await self._api("GET", f"{API}/getClientTraffics/{quote(email)}")
        return _traffic(obj) if obj else None


def _client_form(inbound_id: int, spec: ClientSpec) -> dict[str, str]:
    return {"id": str(inbound_id), "settings": json.dumps({"clients": [spec.to_panel()]})}


def _traffic(o: dict[str, Any]) -> Traffic:
    return Traffic(
        email=o["email"], up=int(o.get("up", 0)), down=int(o.get("down", 0)),
        total=int(o.get("total", 0)), expiry_ms=int(o.get("expiryTime", 0)),
        enable=bool(o.get("enable", True)),
    )


def traffic_from_stats(stats: list[dict[str, Any]]) -> dict[str, Traffic]:
    return {s["email"]: _traffic(s) for s in stats if "email" in s}


def _json(resp: httpx.Response) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_path(path: str) -> str:
    # Paths are relative to the secret base, so they are safe; strip emails' query noise.
    return path.split("?")[0]
