"""Fake 3X-UI panel for offline tests and local dev.

Serves the API under a secret base path exactly like the real panel, keeps clients and
traffic in memory, and supports fault injection (panel down, expired sessions).
Run standalone for dev mode:  python -m tests.mock_xui  (listens on 127.0.0.1:2053)
"""

from __future__ import annotations

import json
import secrets
from typing import Any
from urllib.parse import parse_qs

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

COOKIE = "3x-ui"


def ok(obj: Any = None, msg: str = "") -> JSONResponse:
    return JSONResponse({"success": True, "msg": msg, "obj": obj})


def fail(msg: str) -> JSONResponse:
    return JSONResponse({"success": False, "msg": msg, "obj": None})


class MockPanel:
    def __init__(self, *, base_path: str = "mockSecretPath8f3k2", username: str = "admin",
                 password: str = "admin-pass", method: str = "chacha20-ietf-poly1305",
                 port: int = 34567, remark: str = "exabytetgbot", server_key: str | None = None):
        self.base_path = base_path
        self.username, self.password = username, password
        self.sessions: set[str] = set()
        self.down = False  # True -> every request answers 503
        self.login_count = 0
        settings: dict[str, Any] = {"method": method, "network": "tcp,udp", "clients": []}
        if method.startswith("2022-"):
            settings["password"] = server_key or "c2VydmVyLWtleS0xNmJ5dGU="  # 16 bytes b64
        self.inbounds: dict[int, dict[str, Any]] = {
            1: {"id": 1, "remark": "other-vmess", "port": 10000, "protocol": "vmess",
                "settings": {"clients": []}},
            7: {"id": 7, "remark": remark, "port": port, "protocol": "shadowsocks",
                "settings": settings},
        }
        self.traffic: dict[str, dict[str, Any]] = {}

    # ---------- test helpers ----------
    def clients(self, inbound_id: int = 7) -> list[dict[str, Any]]:
        return self.inbounds[inbound_id]["settings"]["clients"]

    def client(self, email: str, inbound_id: int = 7) -> dict[str, Any] | None:
        return next((c for c in self.clients(inbound_id) if c["email"] == email), None)

    def add_usage(self, email: str, up: int = 0, down: int = 0) -> None:
        self.traffic[email]["up"] += up
        self.traffic[email]["down"] += down

    def expire_sessions(self) -> None:
        self.sessions.clear()

    # ---------- ASGI app ----------
    @property
    def app(self) -> Starlette:
        api = "/panel/api/inbounds"
        routes = [
            Route("/login", self._login, methods=["POST"]),
            Route(f"{api}/list", self._list, methods=["GET"]),
            Route(api + "/get/{id:int}", self._get, methods=["GET"]),
            Route(f"{api}/addClient", self._add_client, methods=["POST"]),
            Route(api + "/updateClient/{cid}", self._update_client, methods=["POST"]),
            Route(api + "/{id:int}/delClient/{cid}", self._del_client, methods=["POST"]),
            Route(api + "/{id:int}/resetClientTraffic/{email}", self._reset, methods=["POST"]),
            Route(api + "/getClientTraffics/{email}", self._traffics, methods=["GET"]),
        ]
        return Starlette(routes=[Mount(f"/{self.base_path}", routes=routes)])

    async def _form(self, request: Request) -> dict[str, str]:
        body = (await request.body()).decode()
        return {k: v[0] for k, v in parse_qs(body).items()}

    def _guard(self, request: Request) -> Response | None:
        if self.down:
            return Response("unavailable", status_code=503)
        if request.cookies.get(COOKIE) not in self.sessions:
            # Newer 3X-UI hides the API from anonymous callers with a 404.
            return Response("404 page not found", status_code=404)
        return None

    def _public(self, ib: dict[str, Any]) -> dict[str, Any]:
        stats = [{**t, "email": e} for e, t in self.traffic.items()
                 if t["inboundId"] == ib["id"]]
        return {**ib, "settings": json.dumps(ib["settings"]), "clientStats": stats}

    async def _login(self, request: Request) -> Response:
        if self.down:
            return Response("unavailable", status_code=503)
        f = await self._form(request)
        if f.get("username") != self.username or f.get("password") != self.password:
            return fail("Invalid username or password")
        self.login_count += 1
        token = secrets.token_hex(8)
        self.sessions.add(token)
        resp = ok()
        resp.set_cookie(COOKIE, token)
        return resp

    async def _list(self, request: Request) -> Response:
        return self._guard(request) or ok([self._public(i) for i in self.inbounds.values()])

    async def _get(self, request: Request) -> Response:
        if g := self._guard(request):
            return g
        ib = self.inbounds.get(request.path_params["id"])
        return ok(self._public(ib)) if ib else fail("not found")

    async def _add_client(self, request: Request) -> Response:
        if g := self._guard(request):
            return g
        f = await self._form(request)
        ib = self.inbounds.get(int(f["id"]))
        if not ib:
            return fail("inbound not found")
        for c in json.loads(f["settings"])["clients"]:
            if any(x["email"] == c["email"] for x in ib["settings"]["clients"]):
                return fail(f"Duplicate email: {c['email']}")
            ib["settings"]["clients"].append(c)
            self.traffic[c["email"]] = {"inboundId": ib["id"], "up": 0, "down": 0,
                                        "total": c["totalGB"], "expiryTime": c["expiryTime"],
                                        "enable": c["enable"]}
        return ok()

    async def _update_client(self, request: Request) -> Response:
        if g := self._guard(request):
            return g
        f = await self._form(request)
        ib = self.inbounds.get(int(f["id"]))
        cid = request.path_params["cid"]
        if not ib:
            return fail("inbound not found")
        new = json.loads(f["settings"])["clients"][0]
        clients = ib["settings"]["clients"]
        for i, c in enumerate(clients):
            if c["email"] == cid:
                clients[i] = new
                t = self.traffic.pop(cid)
                t.update(total=new["totalGB"], expiryTime=new["expiryTime"], enable=new["enable"])
                self.traffic[new["email"]] = t
                return ok()
        return fail("client not found")

    async def _del_client(self, request: Request) -> Response:
        if g := self._guard(request):
            return g
        ib = self.inbounds.get(request.path_params["id"])
        cid = request.path_params["cid"]
        if not ib or not any(c["email"] == cid for c in ib["settings"]["clients"]):
            return fail("client not found")
        ib["settings"]["clients"] = [c for c in ib["settings"]["clients"] if c["email"] != cid]
        self.traffic.pop(cid, None)
        return ok()

    async def _reset(self, request: Request) -> Response:
        if g := self._guard(request):
            return g
        t = self.traffic.get(request.path_params["email"])
        if t is None:
            return fail("client not found")
        t.update(up=0, down=0)
        return ok()

    async def _traffics(self, request: Request) -> Response:
        if g := self._guard(request):
            return g
        email = request.path_params["email"]
        t = self.traffic.get(email)
        return ok(dict(email=email, **t) if t else None)


class FlakyTransport(httpx.AsyncBaseTransport):
    """Wraps the ASGI transport; `fail_next` simulates connection errors (panel down)."""

    def __init__(self, inner: httpx.AsyncBaseTransport):
        self.inner = inner
        self.fail_next = 0
        self.attempts = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.attempts += 1
        if self.fail_next > 0:
            self.fail_next -= 1
            raise httpx.ConnectError("simulated: connection refused", request=request)
        return await self.inner.handle_async_request(request)


if __name__ == "__main__":  # pragma: no cover - manual dev helper
    import uvicorn

    panel = MockPanel()
    print(f"Mock 3X-UI on http://127.0.0.1:2053/{panel.base_path}  user=admin pass=admin-pass")
    uvicorn.run(panel.app, host="127.0.0.1", port=2053)
