"""Branded Burmese message builders and inline keyboards (spec §7, §9.5).

Every main message starts with HEADER + DIVIDER. All Burmese text comes from strings.py.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from .. import packages as P
from ..config import Settings
from ..service import KeyView, Order
from ..strings import DIVIDER, HEADER, t
from ..util import days_left, fmt_bytes, fmt_date, fmt_mmk


def branded(body: str) -> str:
    """Wrap a message body with the §9.5 branded one-line header and divider."""
    return f"<b>{HEADER}</b>\n{DIVIDER}\n{body}"


def progress_bar(used: int, quota: int, width: int = 10) -> tuple[str, int]:
    if quota <= 0:
        return "▰" * width, 0
    pct = min(int(round(used * 100 / quota)), 100)
    filled = min(int(round(used * width / quota)), width)
    return "▰" * filled + "▱" * (width - filled), pct


def status_label(status: str) -> str:
    key = f"status_{status}"
    return t(key) if key in ("status_active", "status_expired", "status_disabled") else t("status_none")


def format_key_message(
    kv: KeyView,
    now: datetime,
    *,
    intro: str | None = None,
    extra_servers: list[dict[str, str]] | None = None,
    sub_url: str | None = None,
) -> str:
    void_sub = sub_url
    del void_sub
    if kv.unlimited:
        usage_line = f"<b>Unlimited</b> (သုံးပြီး: <b>{fmt_bytes(kv.used_bytes)}</b>)"
    else:
        bar, pct = progress_bar(kv.used_bytes, kv.quota_bytes)
        usage_line = (
            f"{bar} <b>{pct}%</b> (<b>{fmt_bytes(kv.used_bytes)}</b> / "
            f"<b>{fmt_bytes(kv.quota_bytes)}</b> • ကျန် <b>{fmt_bytes(kv.remaining_bytes)}</b>)"
        )
    body = t(
        "key_card",
        kind=t("kind_paid" if kv.kind == "paid" else "kind_trial"),
        status=status_label(kv.status),
        usage_line=usage_line,
        expiry_date=fmt_date(kv.expiry_ms),
        days_left=days_left(kv.expiry_ms, now),
        link=escape(kv.link),
    )
    if extra_servers and len(extra_servers) > 1:
        srv_lines = "\n".join(
            f"• <b>{escape(s['name'])}</b>:\n<code>{escape(s['link'])}</code>"
            for s in extra_servers[1:]
        )
        body += "\n" + t("extra_servers_section", servers=srv_lines)
    if intro:
        body = f"{intro}\n{body}"
    return branded(body)


def _plan_data_label(plan: P.Plan) -> str:
    return f"+{plan.quota_gb} GB (Shared Data)" if plan.quota_gb else "Unlimited Data"


def format_key_extended_message(order: Order, kv: KeyView, now: datetime) -> str:
    return branded(
        t(
            "order_key_extended",
            code=order.code,
            plan_name=order.plan.name,
            days=order.plan.days,
            data_label=_plan_data_label(order.plan),
            expiry_date=fmt_date(kv.expiry_ms),
            days_left=days_left(kv.expiry_ms, now),
        )
    )


def format_order_approved_message(order: Order, kv: KeyView, now: datetime) -> str:
    return branded(
        t(
            "order_approved_card",
            plan_name=order.plan.name,
            days=order.plan.days,
            data_label=_plan_data_label(order.plan),
            expiry_date=fmt_date(kv.expiry_ms),
            days_left=days_left(kv.expiry_ms, now),
        )
    )


def format_usage_message(kv: KeyView, now: datetime) -> str:
    st = status_label(kv.status)
    d_left = days_left(kv.expiry_ms, now)
    exp = fmt_date(kv.expiry_ms)
    if kv.kind == "trial" and not kv.unlimited:
        bar, pct = progress_bar(kv.used_bytes, kv.quota_bytes)
        body = t(
            "usage_card_trial",
            bar=bar,
            percent=pct,
            used=fmt_bytes(kv.used_bytes),
            quota=fmt_bytes(kv.quota_bytes),
            days_left=d_left,
            expiry_date=exp,
            status=st,
        )
    elif not kv.unlimited:
        bar, pct = progress_bar(kv.used_bytes, kv.quota_bytes)
        body = t(
            "usage_card_paid_gb",
            bar=bar,
            percent=pct,
            used=fmt_bytes(kv.used_bytes),
            quota=fmt_bytes(kv.quota_bytes),
            remaining=fmt_bytes(kv.remaining_bytes),
            days_left=d_left,
            expiry_date=exp,
            status=st,
        )
    else:
        body = t(
            "usage_card_paid",
            used=fmt_bytes(kv.used_bytes),
            days_left=d_left,
            expiry_date=exp,
            status=st,
        )
    return branded(body)


def _format_plan_line(p: P.Plan) -> str:
    if p.discount_mmk > 0:
        price_part = f"<s>{fmt_mmk(p.original_price_mmk)}</s> <b>{fmt_mmk(p.price_mmk)}</b>"
        save_txt = t("badge_save", amount=fmt_mmk(p.discount_mmk))
        badge_part = f" • 🏷️ <b>{save_txt}</b>"
        if p.best_value:
            badge_part += f" ({t('badge_best')})"
    else:
        price_part = f"<b>{fmt_mmk(p.price_mmk)}</b>"
        badge_part = ""
    return t("plan_card_line", name=p.name, days=p.days, price_part=price_part, badge_part=badge_part)


def format_plans_message() -> str:
    lines = [t("plans_header")]
    for p in P.plans_in("vpn"):
        lines.append(_format_plan_line(p))
    gb_plans = P.plans_in("vpn_gb")
    if gb_plans:
        lines.append("")
        lines.append(t("plans_gb_header"))
        for p in gb_plans:
            lines.append(_format_plan_line(p))
    return branded("\n".join(lines))


def format_order_message(order: Order, settings: Settings) -> str:
    plan = order.plan
    return branded(
        t(
            "order_created",
            plan_name=plan.name,
            days=plan.days,
            code=order.code,
            amount=fmt_mmk(order.amount),
            kbz_number=escape(settings.kbz_number or "-"),
            kbz_name=escape(settings.kbz_name or "-"),
        )
    )


# ---------------------------------------------------------------- keyboards
def reply_menu_kb(settings: Settings) -> ReplyKeyboardMarkup:
    """Persistent bottom reply keyboard (below the typing text bar), 2 buttons per row."""
    rows: list[list[KeyboardButton]] = [
        [
            KeyboardButton(text=t("btn_trial")),
            KeyboardButton(text=t("btn_buy")),
        ],
        [
            KeyboardButton(text=t("btn_my_key")),
            KeyboardButton(text=t("btn_guide")),
        ],
    ]
    if settings.bot_domain:
        rows.append([
            KeyboardButton(
                text=t("btn_open_app"),
                web_app=WebAppInfo(url=f"https://{settings.bot_domain}"),
            ),
            KeyboardButton(text=t("btn_support")),
        ])
    else:
        rows.append([
            KeyboardButton(text=t("btn_support")),
            KeyboardButton(text=t("btn_home")),
        ])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


def main_menu_kb(settings: Settings) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text=t("btn_trial"), callback_data="nav:trial"),
            InlineKeyboardButton(text=t("btn_buy"), callback_data="nav:plans"),
        ],
        [
            InlineKeyboardButton(text=t("btn_my_key"), callback_data="nav:key"),
            InlineKeyboardButton(text=t("btn_guide"), callback_data="nav:guide"),
        ],
    ]
    if settings.bot_domain:
        rows.append([
            InlineKeyboardButton(
                text=t("btn_open_app"),
                web_app=WebAppInfo(url=f"https://{settings.bot_domain}"),
            ),
            InlineKeyboardButton(text=t("btn_support"), callback_data="nav:support"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(text=t("btn_support"), callback_data="nav:support"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("back"), callback_data="nav:home")]]
    )


def key_kb(kv: KeyView) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if kv.multi_server and kv.id:
        rows.append([
            InlineKeyboardButton(
                text=t("btn_switch_server"), callback_data=f"key:srvmenu:{kv.id}"
            )
        ])
    rows.extend([
        [InlineKeyboardButton(text=t("btn_guide"), callback_data="nav:guide")],
        [InlineKeyboardButton(text=t("back"), callback_data="nav:home")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def key_server_switch_kb(
    key_id: int, panels: list[dict[str, object]], current_panel_id: int
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for p in panels:
        pid = int(p["id"])  # type: ignore[arg-type]
        mark = "✅ " if pid == current_panel_id else "🌐 "
        rows.append([
            InlineKeyboardButton(
                text=f"{mark}{p['name']} ({p['server_host']})",
                callback_data=f"key:srvset:{key_id}:{pid}",
            )
        ])
    rows.append([InlineKeyboardButton(text=t("back"), callback_data="nav:key")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plans_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=t("btn_select_plan", name=p.name, price=fmt_mmk(p.price_mmk)),
                callback_data=f"plan:{p.id}",
            )
        ]
        for p in P.all_plans()
    ]
    rows.append([InlineKeyboardButton(text=t("back"), callback_data="nav:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plan_mode_kb(plan_id: str, keys: list[KeyView]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=t("btn_buy_new_key"), callback_data=f"pmode:{plan_id}:0"
            )
        ]
    ]
    for k in keys:
        rows.append([
            InlineKeyboardButton(
                text=t("btn_extend_key", email=k.email),
                callback_data=f"pmode:{plan_id}:{k.id}",
            )
        ])
    rows.append([InlineKeyboardButton(text=t("back"), callback_data="nav:plans")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plan_server_kb(
    plan_id: str, target_sub_id: int, panels: list[dict[str, object]]
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=f"🌐 {p['name']} ({p['server_host']})",
                callback_data=f"psrv:{plan_id}:{target_sub_id}:{int(p['id'])}",  # type: ignore[arg-type]
            )
        ]
        for p in panels
    ]
    rows.append([InlineKeyboardButton(text=t("back"), callback_data="nav:plans")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_created_kb(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("cancel"), callback_data=f"ord:cancel:{code}")],
            [InlineKeyboardButton(text=t("back"), callback_data="nav:home")],
        ]
    )


def guide_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("btn_guide_android"), callback_data="guide:android"),
                InlineKeyboardButton(text=t("btn_guide_ios"), callback_data="guide:ios"),
            ],
            [
                InlineKeyboardButton(text=t("btn_guide_desktop"), callback_data="guide:desktop"),
                InlineKeyboardButton(text=t("back"), callback_data="nav:home"),
            ],
        ]
    )


def guide_detail_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("back"), callback_data="nav:guide")]]
    )


def support_kb(settings: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_contact_support"), url=settings.support_url)],
            [InlineKeyboardButton(text=t("back"), callback_data="nav:home")],
        ]
    )


def admin_order_review_kb(code: str, user_id: int = 0, *, key_enabled: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text=t("btn_approve"), callback_data=f"adm:ap:{code}"),
            InlineKeyboardButton(text=t("btn_reject"), callback_data=f"adm:rj:{code}"),
        ]
    ]
    if user_id:
        toggle_btn = (
            InlineKeyboardButton(
                text=t("btn_suspend_key"), callback_data=f"adm:uact:suspend:{user_id}"
            )
            if key_enabled
            else InlineKeyboardButton(
                text=t("btn_resume_key"), callback_data=f"adm:uact:resume:{user_id}"
            )
        )
        rows.append([
            toggle_btn,
            InlineKeyboardButton(text=t("btn_edit_key"), callback_data=f"adm:editkey:{user_id}"),
        ])
        rows.append([
            InlineKeyboardButton(text=t("btn_msg_user"), callback_data=f"adm:msg:{user_id}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
