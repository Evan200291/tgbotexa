"""FastAPI backend for the Telegram Mini App, Subscription endpoint, and Web Admin Panel."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import logging
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import BufferedInputFile
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, SecretStr

from .. import packages as P
from ..bot.messages import (
    admin_order_review_kb,
    back_home_kb,
    branded,
    format_key_extended_message,
    format_order_approved_message,
    status_label,
)
from ..bot.user import send_key_card
from ..config import Settings, check_dev_mode
from ..service import Service, ServiceError
from ..strings import S, t
from ..util import days_left, fmt_date, fmt_mmk
from ..xui import PanelUnavailable, XUIError, qr_png
from .auth import (
    AuthError,
    WebAppUser,
    create_admin_web_token,
    validate_init_data,
    verify_admin_web_token,
)

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class OrderCreateBody(BaseModel):
    plan_id: str
    target_sub_id: int | None = None
    panel_id: int = 0


class KeySwitchServerBody(BaseModel):
    panel_id: int


class ScreenshotUploadBody(BaseModel):
    image_data_url: str = ""
    note: str = ""


class RejectBody(BaseModel):
    reason: str | None = None


class UserActionBody(BaseModel):
    action: str
    plan_id: str = "vpn_1m"
    target_sub_id: int | None = None
    panel_id: int = 0
    message: str = ""


class AdminLoginBody(BaseModel):
    username: str
    password: str


class AdminKeyEditBody(BaseModel):
    set_days: int | None = None
    add_days: int = 0
    set_quota_gb: float | None = None
    add_gb: int = 0
    reset_used: bool = False
    enabled: bool | None = None
    kind: str | None = None
    panel_id: int | None = None
    multi_server: bool | None = None


class PanelCreateBody(BaseModel):
    name: str
    base_url: str
    username: str
    password: str
    server_host: str
    inbound_remark: str = "exabytetgbot"
    verify_tls: bool = False


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

        effective_admin_token = (
            x_admin_token
            or request.query_params.get("token")
            or request.query_params.get("admin_token")
            or ""
        )
        if effective_admin_token:
            try:
                u = verify_admin_web_token(effective_admin_token, token_val, now=svc.now())
                if not settings.is_admin(u.id):
                    raise AuthError("Not an admin ID")
                await svc.ensure_user(u.id, u.username, u.first_name)
                return u
            except AuthError as e:
                if not settings.dev_mode:
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
    async def index_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/admin", response_class=HTMLResponse)
    @app.get("/superadmin", response_class=HTMLResponse)
    async def superadmin_page() -> FileResponse:
        sa_file = STATIC_DIR / "superadmin.html"
        if sa_file.is_file():
            return FileResponse(sa_file)
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
                "quota_gb": p.quota_gb,
                "multi_server": p.multi_server,
                "devices": p.devices,
                "best_value": p.best_value,
                "badge_text": (
                    t("badge_best")
                    if p.best_value
                    else (t("badge_save", amount=fmt_mmk(p.discount_mmk)) if p.discount_mmk else "")
                ),
            }
            for p in P.all_plans()
        ]
        avail_servers = [
            {"id": p["id"], "name": p["name"], "host": p["server_host"]}
            for p in await svc.list_panels()
            if p["enabled"]
        ]
        return {
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "username": user.username,
                "is_admin": settings.is_admin(user.id),
            },
            "status": st,
            "available_servers": avail_servers,
            "open_order": (
                {
                    "code": open_ord.code,
                    "plan_id": open_ord.plan_id,
                    "plan_name": open_ord.plan.name,
                    "days": open_ord.plan.days,
                    "amount": open_ord.amount,
                    "amount_text": open_ord.amount_text,
                    "state": open_ord.state,
                    "target_sub_id": open_ord.target_sub_id,
                    "panel_id": open_ord.panel_id,
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
        server: int = 0, key_id: int | None = None, user: WebAppUser = Depends(current_user)
    ) -> Response:
        links = await svc.get_key_links(user.id, key_id)
        if not links:
            raise HTTPException(status_code=404, detail=t("no_key"))
        chosen = next((x for x in links if x["panel_id"] == server), links[0])
        return Response(content=qr_png(chosen["link"]), media_type="image/png")

    @app.post("/api/keys/{key_id}/server")
    async def api_switch_key_server(
        key_id: int, body: KeySwitchServerBody, user: WebAppUser = Depends(current_user)
    ) -> dict[str, Any]:
        try:
            await svc.switch_key_server(user.id, key_id, body.panel_id)
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None
        panels = await svc.list_panels()
        srv_name = next((str(p["name"]) for p in panels if int(p["id"]) == body.panel_id), "Server")
        return {
            "message": t("server_switched_ok", server_name=srv_name),
            "status": await svc.get_status(user.id),
        }

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
            order = await svc.create_order(
                user.id,
                body.plan_id,
                target_sub_id=body.target_sub_id,
                panel_id=body.panel_id,
            )
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
            "target_sub_id": order.target_sub_id,
            "panel_id": order.panel_id,
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

        ext = "jpg"
        b64_part = raw
        if "," in raw:
            header, b64_part = raw.split(",", 1)
            hdr_lower = header.lower()
            if "png" in hdr_lower:
                ext = "png"
            elif "webp" in hdr_lower:
                ext = "webp"
            elif "gif" in hdr_lower:
                ext = "gif"

        b64_part = b64_part.strip().replace(" ", "+")
        b64_part += "=" * (-len(b64_part) % 4)
        try:
            img_bytes = base64.b64decode(b64_part)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image encoding") from None

        if not img_bytes:
            raise HTTPException(status_code=400, detail="Empty image data")

        # Save screenshot file to disk immediately
        shots_dir = settings.data_dir / "screenshots"
        shots_dir.mkdir(parents=True, exist_ok=True)
        img_path = shots_dir / f"{code}.{ext}"
        img_path.write_bytes(img_bytes)

        # Hash image bytes so duplicate screenshot uploads are caught across WebApp & Bot.
        digest = hashlib.sha256(img_bytes).hexdigest()[:24]
        unique_id = f"web-{digest}"
        had_key_before = (await svc.get_key(user.id)) is not None
        try:
            order = await svc.attach_screenshot(user.id, code, unique_id, unique_id)
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None

        is_extension = (
            order.target_sub_id is not None and order.target_sub_id > 0
        ) or (order.target_sub_id is None and had_key_before)
        target_kid = (
            order.target_sub_id
            if (order.target_sub_id is not None and order.target_sub_id > 0)
            else None
        )
        kv = await svc.get_key(user.id, target_kid)
        if bot is not None and kv is not None:
            with contextlib.suppress(Exception):
                if is_extension:
                    await bot.send_message(
                        user.id,
                        format_key_extended_message(order, kv, svc.now()),
                        parse_mode="HTML",
                        reply_markup=back_home_kb(),
                    )
                else:
                    intro = t("order_instant_key_intro", code=order.code, plan_name=order.plan.name)
                    await send_key_card(
                        bot, user.id, kv, svc.now(), intro=intro, svc=svc, settings=settings
                    )
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
            sent_msg = None
            try:
                photo_file = BufferedInputFile(img_bytes, filename=f"slip-{order.code}.{ext}")
                sent_msg = await bot.send_photo(
                    chat_id=settings.admin_ids[0],
                    photo=photo_file,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=with_kb,
                )
            except Exception:
                log.exception("failed to send photo to admin; falling back to text message")
                with contextlib.suppress(Exception):
                    sent_msg = await bot.send_message(
                        settings.admin_ids[0], caption, parse_mode="HTML", reply_markup=with_kb
                    )

            if sent_msg is not None and getattr(sent_msg, "photo", None):
                # Update orders table with real Telegram photo file_id for future retrieval
                tg_file_id = sent_msg.photo[-1].file_id
                await svc.db.execute(
                    "UPDATE orders SET screenshot_file_id=? WHERE code=?",
                    (tg_file_id, order.code),
                )

        return {
            "message": t("order_instant_key_intro", code=order.code, plan_name=order.plan.name),
            "status": await svc.get_status(user.id),
            "order_state": order.state,
        }

    # ---------------- Web Admin Panel API ----------------
    @app.post("/api/admin/login")
    async def api_admin_login(body: AdminLoginBody) -> dict[str, Any]:
        import hmac

        p_user = (
            settings.panel_user.get_secret_value()
            if isinstance(settings.panel_user, SecretStr)
            else str(settings.panel_user)
        )
        p_pass = (
            settings.panel_pass.get_secret_value()
            if isinstance(settings.panel_pass, SecretStr)
            else str(settings.panel_pass)
        )
        expected_user = (await svc.db.get_setting("admin_web_user")) or p_user or "exabyte"
        expected_pass = (await svc.db.get_setting("admin_web_pass")) or p_pass or "exabyte"
        u_ok = hmac.compare_digest(body.username.strip(), expected_user)
        p_ok = hmac.compare_digest(body.password, expected_pass)
        if not (u_ok and p_ok):
            raise HTTPException(status_code=401, detail="Username သို့မဟုတ် Password မှားနေပါသည်")
        admin_id = settings.admin_ids[0] if settings.admin_ids else 1877867098
        await svc.ensure_user(admin_id, "superadmin", "Super Admin")
        tok = create_admin_web_token(
            admin_id, settings.bot_token.get_secret_value(), now=svc.now()
        )
        return {"token": tok, "admin_id": admin_id}

    @app.get("/api/admin/orders/{code}/screenshot")
    async def api_admin_order_screenshot(
        code: str,
        _admin: WebAppUser = Depends(require_admin),
    ) -> Response:
        shots_dir = settings.data_dir / "screenshots"
        for ext, mime in [
            ("jpg", "image/jpeg"),
            ("jpeg", "image/jpeg"),
            ("png", "image/png"),
            ("webp", "image/webp"),
        ]:
            p = shots_dir / f"{code}.{ext}"
            if p.is_file():
                return Response(content=p.read_bytes(), media_type=mime)

        row = await svc.db.fetchone("SELECT screenshot_file_id FROM orders WHERE code=?", (code,))
        if (
            row
            and row["screenshot_file_id"]
            and bot is not None
            and not str(row["screenshot_file_id"]).startswith("web-")
        ):
            with contextlib.suppress(Exception):
                f_info = await bot.get_file(row["screenshot_file_id"])
                if f_info.file_path:
                    dest = shots_dir / f"{code}.jpg"
                    shots_dir.mkdir(parents=True, exist_ok=True)
                    await bot.download_file(f_info.file_path, destination=dest)
                    return Response(content=dest.read_bytes(), media_type="image/jpeg")

        raise HTTPException(status_code=404, detail="Screenshot not found")

    @app.get("/api/admin/overview")
    async def api_admin_overview(
        _admin: WebAppUser = Depends(require_admin),
    ) -> dict[str, Any]:
        now = svc.now()
        stats = await svc.stats()
        order_rows = await svc.db.fetchall(
            "SELECT o.*, u.username FROM orders o LEFT JOIN users u ON u.telegram_id=o.user_id "
            "ORDER BY o.created_at DESC LIMIT 100"
        )
        orders_out = []
        shots_dir = settings.data_dir / "screenshots"
        for r in order_rows:
            r_keys = set(r.keys())
            tsub = int(r["target_sub_id"]) if ("target_sub_id" in r_keys and r["target_sub_id"]) else None
            kv = await svc.get_key(int(r["user_id"]), tsub)
            code = r["code"]
            has_shot = bool(
                r["screenshot_file_id"]
                or r["screenshot_unique_id"]
                or any((shots_dir / f"{code}.{ext}").is_file() for ext in ("jpg", "png", "webp", "jpeg"))
            )
            orders_out.append({
                "code": r["code"],
                "user_id": int(r["user_id"]),
                "username": r["username"] or "-",
                "plan_id": r["plan_id"],
                "amount": int(r["amount"]),
                "amount_text": fmt_mmk(int(r["amount"])),
                "state": r["state"],
                "screenshot": f"/api/admin/orders/{r['code']}/screenshot" if has_shot else "",
                "created_at": fmt_date(int(r["created_at"])),
                "key_email": kv.email if kv else "-",
                "key_status": kv.status if kv else "none",
                "key_enabled": kv.enabled if kv else False,
            })

        user_rows = await svc.db.fetchall(
            "SELECT * FROM users ORDER BY last_seen_at DESC LIMIT 200"
        )
        users_out = []
        for u in user_rows:
            uid = int(u["telegram_id"])
            keys_list = await svc.list_keys(uid)
            kv = keys_list[0] if keys_list else None
            oc = await svc.db.fetchone("SELECT COUNT(*) AS c FROM orders WHERE user_id=?", (uid,))
            keys_serialized = [
                {
                    "id": k.id,
                    "email": k.email,
                    "kind": k.kind,
                    "plan_id": k.plan_id,
                    "status": k.status,
                    "enabled": k.enabled,
                    "panel_id": k.panel_id,
                    "multi_server": k.multi_server,
                    "used_bytes": k.used_bytes,
                    "quota_bytes": k.quota_bytes,
                    "remaining_bytes": k.remaining_bytes,
                    "unlimited": k.unlimited,
                    "expiry_ms": k.expiry_ms,
                    "expiry_date": fmt_date(k.expiry_ms),
                    "days_left": days_left(k.expiry_ms, now),
                    "link": k.link,
                }
                for k in keys_list
            ]
            users_out.append({
                "user_id": uid,
                "username": u["username"] or "-",
                "first_name": u["first_name"] or "",
                "banned": bool(u["banned"]),
                "created_at": fmt_date(int(u["created_at"])) if u["created_at"] else "-",
                "last_seen_at": fmt_date(int(u["last_seen_at"])) if u["last_seen_at"] else "-",
                "order_count": int(oc["c"]) if oc else 0,
                "keys": keys_serialized,
                "key": keys_serialized[0] if keys_serialized else None,
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
            "plans": [
                {"id": p.id, "name": p.name, "days": p.days, "price_text": fmt_mmk(p.price_mmk)}
                for p in P.all_plans()
            ],
            "store": await _effective_store_config(),
        }

    @app.post("/api/admin/keys/{key_id}/edit")
    async def api_admin_edit_key(
        key_id: int, body: AdminKeyEditBody, admin: WebAppUser = Depends(require_admin)
    ) -> dict[str, Any]:
        try:
            await svc.admin_edit_key_by_id(
                admin.id,
                key_id,
                set_days=body.set_days,
                add_days=body.add_days,
                set_quota_gb=body.set_quota_gb,
                add_gb=body.add_gb,
                reset_used=body.reset_used,
                enabled=body.enabled,
                kind=body.kind,
                panel_id=body.panel_id,
                multi_server=body.multi_server,
            )
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None
        except PanelUnavailable:
            raise HTTPException(status_code=503, detail=t("panel_down")) from None
        return {"message": t("adm_action_done")}

    @app.delete("/api/admin/keys/{key_id}")
    async def api_admin_delete_key(
        key_id: int, admin: WebAppUser = Depends(require_admin)
    ) -> dict[str, Any]:
        try:
            await svc.admin_delete_key_by_id(admin.id, key_id)
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=e.message()) from None
        except PanelUnavailable:
            raise HTTPException(status_code=503, detail=t("panel_down")) from None
        return {"message": t("adm_action_done")}

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
        if bot is not None and not res.already and res.key is not None:
            with contextlib.suppress(Exception):
                await bot.send_message(
                    res.order.user_id,
                    format_order_approved_message(res.order, res.key, svc.now()),
                    parse_mode="HTML",
                    reply_markup=back_home_kb(),
                )
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
                await svc.grant_plan(
                    admin.id,
                    uid,
                    body.plan_id,
                    target_sub_id=body.target_sub_id,
                    panel_id=body.panel_id,
                )
            elif act == "message":
                from html import escape

                msg_txt = body.message.strip()
                if not msg_txt:
                    raise HTTPException(status_code=400, detail="Empty message")
                if bot is not None:
                    await bot.send_message(uid, branded(escape(msg_txt)), parse_mode="HTML")
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
