"""FastAPI backend for the Telegram Mini App, Subscription endpoint, and Web Admin Panel."""

from __future__ import annotations

import contextlib
import hashlib
from pathlib import Path
from typing import Any

from aiogram import Bot
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import packages as P
from ..bot.messages import admin_order_review_kb, branded, status_label
from ..config import Settings, check_dev_mode
from ..service import Service, ServiceError
from ..strings import S, t
from ..util import fmt_date, fmt_mmk
from ..xui import PanelUnavailable, XUIError, qr_png
from .auth import AuthError, WebAppUser, validate_init_data, verify_admin_web_token

STATIC_DIR = Path(__file__).resolve().parent / "static"


class OrderCreateBody(BaseModel):
    plan_id: str


class ScreenshotUploadBody(BaseModel):
    image_data_url: str = ""
    note: str = ""


class RejectBody(BaseModel):
    reason: str | None = None


class UserActionBody(BaseModel):
    action: str
    plan_id: str = "vpn_1m"
    message: str = ""


class PanelCreateBody(BaseModel):
    name: str
    base_url: str
    username: str
    password: str
    server_host: str
    inbound_remark: str = "exabytetgbot"
    verify_tls: bool = True


class PanelToggleBody(BaseModel):
    enabled: bool


class CustomSettingsBody(BaseModel):
    kbz_number: str | None = None
    kbz_name: str | None = None
    support_url: str | None = None
    tagline: str | None = None
    maintenance: bool | None = None


class BroadcastBody(BaseModel):
    text: str


def create_webapp(
    svc: Service, settings: Settings, *, bot: Bot | None = None
) -> FastAPI:
    check_dev_mode(settings)
    app = FastAPI(title="Exabyte Digital Store", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    async def current_user(
        request: Request,
        x_telegram_init_data: str = Header(default=""),
        x_admin_token: str = Header(default=""),
    ) -> WebAppUser:
        token_val = settings.bot_token.get_secret_value()
        if x_telegram_init_data:
            try:
                u = validate_init_data(x_telegram_init_data, token_val, now=svc.now())
                await svc.ensure_user(u.id, u.username, u.first_name)
                return u
            except AuthError as e:
                if not settings.dev_mode:
                    raise HTTPException(status_code=401, detail=str(e)) from None

        if x_admin_token:
            try:
                u = verify_admin_web_token(x_admin_token, token_val, now=svc.now())
                if not settings.is_admin(u.id):
                    raise AuthError("Not an admin ID")
                await svc.ensure_user(u.id, u.username, u.first_name)
                return u
            except AuthError as e:
                raise HTTPException(status_code=401, detail=str(e)) from None

        if settings.dev_mode:
            dev_admin = request.headers.get("x-dev-admin") == "1"
            uid = settings.admin_ids[0] if (dev_admin and settings.admin_ids) else 111222333
            u = WebAppUser(
                id=uid,
                first_name="Exabyte Admin" if dev_admin else "Aung Aung",
                username="exabyte_admin" if dev_admin else "aung_dev",
            )
            await svc.ensure_user(u.id, u.username, u.first_name)
            return u

        raise HTTPException(status_code=401, detail="Unauthorized")

    async def require_admin(user: WebAppUser = Depends(current_user)) -> WebAppUser:
        if not settings.is_admin(user.id):
            raise HTTPException(status_code=403, detail="Admin access required")
        return user

    async def _effective_store_config() -> dict[str, Any]:
        kbz_num = await svc.db.get_setting("custom_kbz_number") or settings.kbz_number
        kbz_nm = await svc.db.get_setting("custom_kbz_name") or settings.kbz_name
        sup_url = await svc.db.get_setting("custom_support_url") or settings.support_url
        tagline = await svc.db.get_setting("custom_tagline") or t("tagline")
        return {
            "kbz_number": kbz_num,
            "kbz_name": kbz_nm,
            "support_url": sup_url,
            "tagline": tagline,
            "bot_domain": settings.bot_domain,
            "maintenance": await svc.is_maintenance(),
        }

    # ---------------- Health Check ----------------
    @app.get("/healthz")
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    # ---------------- HTML pages & Subscription URL ----------------
    @app.get("/", response_class=HTMLResponse)
    @app.get("/admin", response_class=HTMLResponse)
    async def index_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/dev/kit", response_class=HTMLResponse)
    async def dev_kit_page() -> FileResponse:
        if settings.environment == "production" and not settings.dev_mode:
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(STATIC_DIR / "kit.html")

    @app.get("/sub/{sub_id}", response_class=PlainTextResponse)
    async def subscription_endpoint(sub_id: str) -> Response:
        payload = await svc.subscription_payload_by_sub_id(sub_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return Response(
            content=payload,
            media_type="text/plain; charset=utf-8",
            headers={"Profile-Update-Interval": "6", "Subscription-Userinfo": "total=0"},
        )

    # ---------------- Customer Mini App API ----------------
    @app.get("/api/bootstrap")
    async def api_bootstrap(user: WebAppUser = Depends(current_user)) -> dict[str, Any]:
        if await svc.is_banned(user.id) and not settings.is_admin(user.id):
            raise HTTPException(status_code=403, detail=t("banned"))
        store = await _effective_store_config()
        if store["maintenance"] and not settings.is_admin(user.id):
            raise HTTPException(status_code=503, detail=t("maintenance"))

        st = await svc.get_status(user.id)
        if st.get("sub_id") and settings.bot_domain:
            st["sub_url"] = f"https://{settings.bot_domain}/sub/{st['sub_id']}"
        else:
            st["sub_url"] = None

        open_ord = await svc.open_order(user.id)
        plans = [
            {
                "id": p.id,
                "category": p.category,
                "name": p.name,
                "months": p.months,
                "days": p.days,
                "price_mmk": p.price_mmk,
                "price_text": fmt_mmk(p.price_mmk),
                "original_price_mmk": p.original_price_mmk,
                "original_price_text": fmt_mmk(p.original_price_mmk),
                "discount_mmk": p.discount_mmk,
                "discount_text": fmt_mmk(p.discount_mmk) if p.discount_mmk else "",
                "unlimited": p.unlimited,
                "devices": p.devices,
                "best_value": p.best_value,
                "badge_text": (
                    t("badge_best")
                    if p.best_value
                    else (t("badge_save", amount=fmt_mmk(p.discount_mmk)) if p.discount_mmk else "")
                ),
            }
            for p in P.plans_in("vpn")
        ]
        return {
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "username": user.username,
                "is_admin": settings.is_admin(user.id),
            },
            "status": st,
            "open_order": (
                {
                    "code": open_ord.code,
                    "plan_id": open_ord.plan_id,
                    "plan_name": open_ord.plan.name,
                    "days": open_ord.plan.days,
                    "amount": open_ord.amount,
                    "amount_text": open_ord.amount_text,
                    "state": open_ord.state,
                }
                if open_ord
                else None
            ),
            "plans": plans,
            "store": store,
            "strings": S,
        }

    @app.get("/api/key/qr")
    async def api_key_qr(
        server: int = 0, user: WebAppUser = Depends(current_user)
    ) -> Response:
        links = await svc.get_key_links(user.id)
        if not links:
            raise HTTPException(status_code=404, detail=t("no_key"))
        chosen = next((x for x in links if x["panel_id"] == server), links[0])
        return Response(content=qr_png(chosen["link"]), media_type="image/png")

    @app.post("/api/trial/claim")
    async def api_claim_trial(user: WebAppUser = Depends(current_user)) -> dict[str, Any]:
        try:
            await svc.claim_trial(user.id)
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None
        except PanelUnavailable:
            raise HTTPException(status_code=503, detail=t("panel_down")) from None
        return {
            "message": t("trial_ok", gb=P.TRIAL_QUOTA_GB, days=P.TRIAL_DAYS),
            "status": await svc.get_status(user.id),
        }

    @app.post("/api/key/regenerate")
    async def api_regenerate_key(user: WebAppUser = Depends(current_user)) -> dict[str, Any]:
        try:
            await svc.regenerate_key(user.id)
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None
        except PanelUnavailable:
            raise HTTPException(status_code=503, detail=t("panel_down")) from None
        return {"message": t("regen_ok"), "status": await svc.get_status(user.id)}

    @app.post("/api/orders")
    async def api_create_order(
        body: OrderCreateBody, user: WebAppUser = Depends(current_user)
    ) -> dict[str, Any]:
        try:
            order = await svc.create_order(user.id, body.plan_id)
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None
        return {
            "code": order.code,
            "plan_id": order.plan_id,
            "plan_name": order.plan.name,
            "days": order.plan.days,
            "amount": order.amount,
            "amount_text": order.amount_text,
            "state": order.state,
        }

    @app.post("/api/orders/{code}/cancel")
    async def api_cancel_order(
        code: str, user: WebAppUser = Depends(current_user)
    ) -> dict[str, Any]:
        try:
            await svc.cancel_order(user.id, code)
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None
        return {"message": t("order_cancelled", code=code)}

    @app.post("/api/orders/{code}/screenshot")
    async def api_upload_screenshot(
        code: str, body: ScreenshotUploadBody, user: WebAppUser = Depends(current_user)
    ) -> dict[str, Any]:
        raw = (body.image_data_url or "").strip()
        if not raw or len(raw) < 20:
            raise HTTPException(status_code=400, detail=t("order_send_photo_prompt", code=code))
        # Hash the image bytes so duplicate screenshot uploads are caught across WebApp & Bot.
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        unique_id = f"web-{digest}"
        try:
            order = await svc.attach_screenshot(user.id, code, raw[:200_000], unique_id)
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None

        kv = await svc.get_key(user.id)
        if bot is not None and settings.admin_ids:
            uname = f"@{user.username}" if user.username else "-"
            caption = branded(
                t(
                    "adm_new_order_caption",
                    code=order.code,
                    user_id=user.id,
                    username=uname,
                    plan_name=order.plan.name,
                    days=order.plan.days,
                    amount=order.amount_text,
                    key_email=kv.email if kv else "-",
                    key_status=status_label(kv.status) if kv else "-",
                )
            )
            with_kb = admin_order_review_kb(
                order.code, user.id, key_enabled=kv.enabled if kv else True
            )
            with contextlib.suppress(Exception):
                await bot.send_message(
                    settings.admin_ids[0], caption, parse_mode="HTML", reply_markup=with_kb
                )

        return {
            "message": t("order_instant_key_intro", code=order.code, plan_name=order.plan.name),
            "status": await svc.get_status(user.id),
            "order_state": order.state,
        }

    # ---------------- Web Admin Panel API ----------------
    @app.get("/api/admin/overview")
    async def api_admin_overview(
        _admin: WebAppUser = Depends(require_admin),
    ) -> dict[str, Any]:
        stats = await svc.stats()
        order_rows = await svc.db.fetchall(
            "SELECT o.*, u.username FROM orders o LEFT JOIN users u ON u.telegram_id=o.user_id "
            "ORDER BY o.created_at DESC LIMIT 40"
        )
        orders_out = []
        for r in order_rows:
            kv = await svc.get_key(int(r["user_id"]))
            orders_out.append({
                "code": r["code"],
                "user_id": int(r["user_id"]),
                "username": r["username"] or "-",
                "plan_id": r["plan_id"],
                "amount": int(r["amount"]),
                "amount_text": fmt_mmk(int(r["amount"])),
                "state": r["state"],
                "screenshot": r["screenshot_file_id"] or "",
                "created_at": fmt_date(int(r["created_at"])),
                "key_email": kv.email if kv else "-",
                "key_status": kv.status if kv else "none",
                "key_enabled": kv.enabled if kv else False,
            })

        user_rows = await svc.db.fetchall(
            "SELECT * FROM users ORDER BY last_seen_at DESC LIMIT 40"
        )
        users_out = []
        for u in user_rows:
            uid = int(u["telegram_id"])
            kv = await svc.get_key(uid)
            users_out.append({
                "user_id": uid,
                "username": u["username"] or "-",
                "first_name": u["first_name"] or "",
                "banned": bool(u["banned"]),
                "key": (
                    {
                        "email": kv.email,
                        "kind": kv.kind,
                        "status": kv.status,
                        "enabled": kv.enabled,
                        "used_bytes": kv.used_bytes,
                        "quota_bytes": kv.quota_bytes,
                        "unlimited": kv.unlimited,
                        "expiry_date": fmt_date(kv.expiry_ms),
                    }
                    if kv
                    else None
                ),
            })

        return {
            "stats": {
                **stats,
                "today_revenue_text": fmt_mmk(stats["today_revenue"]),
                "month_revenue_text": fmt_mmk(stats["month_revenue"]),
            },
            "orders": orders_out,
            "users": users_out,
            "panels": await svc.list_panels(),
            "store": await _effective_store_config(),
        }

    @app.post("/api/admin/orders/{code}/approve")
    async def api_admin_approve(
        code: str, admin: WebAppUser = Depends(require_admin)
    ) -> dict[str, Any]:
        try:
            res = await svc.approve_order(code, admin.id)
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None
        except PanelUnavailable:
            raise HTTPException(status_code=503, detail=t("panel_down")) from None
        return {"message": t("adm_action_done"), "state": res.order.state}

    @app.post("/api/admin/orders/{code}/reject")
    async def api_admin_reject(
        code: str, body: RejectBody, admin: WebAppUser = Depends(require_admin)
    ) -> dict[str, Any]:
        try:
            res = await svc.reject_order(code, admin.id, body.reason)
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None
        return {"message": t("adm_action_done"), "state": res.order.state}

    @app.post("/api/admin/users/{uid}/action")
    async def api_admin_user_action(
        uid: int, body: UserActionBody, admin: WebAppUser = Depends(require_admin)
    ) -> dict[str, Any]:
        act = body.action
        try:
            if act == "add7d":
                await svc.admin_adjust_key(admin.id, uid, add_days=7)
            elif act == "sub7d":
                await svc.admin_adjust_key(admin.id, uid, add_days=-7)
            elif act == "add30d":
                await svc.admin_adjust_key(admin.id, uid, add_days=30)
            elif act == "add5g":
                await svc.admin_adjust_key(admin.id, uid, add_gb=5)
            elif act == "suspend":
                await svc.admin_set_key_enabled(admin.id, uid, False)
            elif act == "resume":
                await svc.admin_set_key_enabled(admin.id, uid, True)
            elif act == "revoke":
                await svc.admin_revoke_key(admin.id, uid)
            elif act == "ban":
                await svc.admin_set_banned(admin.id, uid, True)
            elif act == "unban":
                await svc.admin_set_banned(admin.id, uid, False)
            elif act == "grant":
                await svc.grant_plan(admin.id, uid, body.plan_id)
            else:
                raise HTTPException(status_code=400, detail="Unknown action")
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None
        except PanelUnavailable:
            raise HTTPException(status_code=503, detail=t("panel_down")) from None
        return {"message": t("adm_action_done")}

    @app.post("/api/admin/panels")
    async def api_admin_add_panel(
        body: PanelCreateBody, admin: WebAppUser = Depends(require_admin)
    ) -> dict[str, Any]:
        try:
            panel_info = await svc.add_panel(
                admin.id,
                name=body.name,
                base_url=body.base_url,
                username=body.username,
                password=body.password,
                server_host=body.server_host,
                inbound_remark=body.inbound_remark,
                verify_tls=body.verify_tls,
            )
        except XUIError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        return {"message": t("adm_action_done"), "panel": panel_info}

    @app.post("/api/admin/panels/{pid}/toggle")
    async def api_admin_toggle_panel(
        pid: int, body: PanelToggleBody, admin: WebAppUser = Depends(require_admin)
    ) -> dict[str, Any]:
        await svc.toggle_panel(admin.id, pid, body.enabled)
        return {"message": t("adm_action_done")}

    @app.delete("/api/admin/panels/{pid}")
    async def api_admin_delete_panel(
        pid: int, admin: WebAppUser = Depends(require_admin)
    ) -> dict[str, Any]:
        await svc.delete_panel(admin.id, pid)
        return {"message": t("adm_action_done")}

    @app.post("/api/admin/settings")
    async def api_admin_update_settings(
        body: CustomSettingsBody, admin: WebAppUser = Depends(require_admin)
    ) -> dict[str, Any]:
        if body.kbz_number is not None:
            await svc.db.set_setting("custom_kbz_number", body.kbz_number.strip())
        if body.kbz_name is not None:
            await svc.db.set_setting("custom_kbz_name", body.kbz_name.strip())
        if body.support_url is not None:
            await svc.db.set_setting("custom_support_url", body.support_url.strip())
        if body.tagline is not None:
            await svc.db.set_setting("custom_tagline", body.tagline.strip())
        if body.maintenance is not None:
            await svc.db.set_setting("maintenance", "1" if body.maintenance else "0")
        await svc.db.audit(
            admin.id, "web_update_settings", None, body.model_dump(exclude_none=True),
            int(svc.now().timestamp() * 1000),
        )
        return {"message": t("adm_action_done"), "store": await _effective_store_config()}

    @app.post("/api/admin/broadcast")
    async def api_admin_broadcast(
        body: BroadcastBody, admin: WebAppUser = Depends(require_admin)
    ) -> dict[str, Any]:
        from html import escape

        txt = body.text.strip()
        if not txt:
            raise HTTPException(status_code=400, detail="Empty message")
        recipients = await svc.broadcast_recipients()
        ok_cnt, fail_cnt = 0, 0
        if bot is not None:
            for uid in recipients:
                try:
                    await bot.send_message(uid, branded(escape(txt)), parse_mode="HTML")
                    ok_cnt += 1
                except Exception:
                    fail_cnt += 1
        else:
            ok_cnt = len(recipients)
        await svc.db.audit(
            admin.id, "web_broadcast", None, {"ok": ok_cnt, "failed": fail_cnt},
            int(svc.now().timestamp() * 1000),
        )
        return {"message": t("adm_broadcast_done", ok=ok_cnt, failed=fail_cnt), "ok": ok_cnt}

    return app
