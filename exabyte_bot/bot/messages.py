"""Branded Burmese message builders and inline keyboards (spec §7, §9.5).

Every main message starts with HEADER + DIVIDER. All Burmese text comes from strings.py.
"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime
from html import escape

from urllib.parse import quote

from aiogram.types import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from .. import packages as P
from ..config import Settings
from ..service import KeyView, Order
from ..strings import DIVIDER, t
from ..util import days_left, fmt_bytes, fmt_date, fmt_mmk

STORE_NAME: ContextVar[str] = ContextVar("store_name", default="Exabyte Digital Store")


def branded(body: str) -> str:
    """Wrap a message body with the §9.5 branded one-line header and divider."""
    return f"<b>✨ {escape(STORE_NAME.get())}</b>\n{DIVIDER}\n{body}"


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
        usage_line = (
            f"• <b>Data ပမာဏ</b> — <b>Unlimited</b> (သုံးပြီး: <b>{fmt_bytes(kv.used_bytes)}</b>)"
        )
    else:
        pct = min(int(round(kv.used_bytes * 100 / kv.quota_bytes)), 100) if kv.quota_bytes > 0 else 0
        usage_line = (
            f"• <b>သုံးပြီး Data</b> — <b>{fmt_bytes(kv.used_bytes)}</b> / "
            f"<b>{fmt_bytes(kv.quota_bytes)}</b> ({pct}%)\n"
            f"• <b>လက်ကျန် Data</b> — <b>{fmt_bytes(kv.remaining_bytes)}</b>"
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
    if kv.multi_server and extra_servers:
        extra_servers = [s for s in extra_servers if s["link"] != kv.link]
    if kv.multi_server and extra_servers:
        srv_lines = "\n".join(
            f"• <b>{escape(s['name'])}</b>:\n<code>{escape(s['link'])}</code>"
            for s in extra_servers
        )
        body += "\n" + t("extra_servers_section", servers=srv_lines)
    if intro:
        body = f"{intro}\n\n{body}"
    return branded(body)


def _plan_data_label(plan: P.Plan) -> str:
    return f"+{plan.quota_gb} GB (All Server Regions)" if plan.quota_gb else "Unlimited Data"


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


def _format_plan_line(p: P.Plan, *, is_reseller: bool = False) -> str:
    price_part = f"<b>{fmt_mmk(p.price_for(is_reseller=is_reseller))}</b>"
    return t("plan_card_line", name=p.name, days=p.days, price_part=price_part, badge_part="")


def format_plans_message(
    *, is_reseller: bool = False, balance_mmk: int = 0, exabyte_ui: bool = False
) -> str:
    unlim = P.plans_in("vpn", exabyte=exabyte_ui)
    gb = P.plans_in("vpn_gb", exabyte=exabyte_ui)
    lines: list[str] = []
    if is_reseller:
        lines.append(t("reseller_wallet_banner", balance=fmt_mmk(balance_mmk)).strip() + "\n")
    lines.append("🩵 <b>ပြထားသော packages များထဲမှ ဝယ်ယူနိုင်သည်။</b>\n")
    lines.append("🟢 <b>Unlimited traffic</b> <i>(Device 1 လုံးတည်းအတွက်သာ)</i>")
    for p in unlim:
        price = fmt_mmk(p.price_for(is_reseller=is_reseller))
        lines.append(f"• <b>{p.months} month</b> - <b>{price}</b>")
    lines.append("")
    lines.append("🟩 <b>GB Limit Plan</b> <i>(Device Limit မရှိ။)</i>")
    for p in gb:
        price = fmt_mmk(p.price_for(is_reseller=is_reseller))
        lines.append(f"• <b>{p.months} month</b> - <b>{p.quota_gb}GB</b> - <b>{price}</b>")
    return branded("\n".join(lines))


def format_order_message(
    order: Order,
    settings: Settings,
    *,
    is_reseller: bool = False,
    balance_mmk: int = 0,
) -> str:
    plan = order.plan
    body = t(
        "exabyte_order_created",
        plan_name=plan.name,
        days=plan.days,
        code=order.code,
        amount=fmt_mmk(order.amount),
        kbz_number=escape(settings.kbz_number or "-"),
        kbz_name=escape(settings.kbz_name or "-"),
    )
    if is_reseller or balance_mmk > 0:
        body += "\n" + t("reseller_wallet_banner", balance=fmt_mmk(balance_mmk))
    return branded(body)


# ---------------------------------------------------------------- keyboards
def reply_menu_kb(settings: Settings) -> ReplyKeyboardMarkup:
    """Persistent bottom reply keyboard (below the typing text bar), 2 buttons per row."""
    rows: list[list[KeyboardButton]] = [
        [
            KeyboardButton(text=t("btn_trial")),
            KeyboardButton(text=t("exabyte_btn_buy")),
        ],
    ]
    if settings.bot_domain:
        rows.append([
            KeyboardButton(text=t("btn_guide")),
            KeyboardButton(
                text=t("exabyte_btn_open_app"),
                web_app=WebAppInfo(url=f"https://{settings.bot_domain}"),
            ),
        ])
    else:
        rows.append([
            KeyboardButton(text=t("btn_guide")),
        ])
    rows.append([
        KeyboardButton(text=t("exabyte_btn_support")),
    ])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
        input_field_placeholder="အောက်ပါ မီနူးမှ ရွေးပါ",
    )


def main_menu_kb(settings: Settings) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text=t("btn_trial"), callback_data="nav:trial"),
            InlineKeyboardButton(text=t("exabyte_btn_buy"), callback_data="nav:plans"),
        ],
    ]
    if settings.bot_domain:
        rows.append([
            InlineKeyboardButton(text=t("btn_guide"), callback_data="nav:guide"),
            InlineKeyboardButton(
                text=t("exabyte_btn_open_app"),
                web_app=WebAppInfo(url=f"https://{settings.bot_domain}"),
            ),
        ])
    else:
        rows.append([
            InlineKeyboardButton(text=t("btn_guide"), callback_data="nav:guide"),
        ])
    rows.append([
        InlineKeyboardButton(text=t("exabyte_btn_support"), callback_data="nav:support"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _server_button_label(p: dict[str, object], *, exabyte_ui: bool = True) -> str:
    del exabyte_ui
    host = str(p.get("server_host") or "").lower()
    name = str(p.get("name") or "").lower()
    pid = int(p.get("id") or 0)  # type: ignore[arg-type]
    if "sgsep" in host or "singapore" in name or "sg" in name:
        return "🇸🇬 Singapore Server"
    if "tpone" in host or "thailand" in name or "bangkok" in name or pid == 0:
        return "🇹🇭 Thailand Server (Bangkok)"
    return f"🌐 {p['name']}"


def back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("back"), callback_data="nav:home")]]
    )


def key_kb(kv: KeyView, bot_domain: str = "") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if bot_domain and kv.status == "active":
        rows.append([InlineKeyboardButton(text="Add Key to Outline",
                    url=f"https://{bot_domain}/static/outline.html#{quote(kv.link, safe='')}")])
    if len(kv.link) <= 256:
        rows.append([InlineKeyboardButton(text="📋 Key ကူးယူမည်",
                                          copy_text=CopyTextButton(text=kv.link))])
    if kv.multi_server and kv.id:
        rows.append([
            InlineKeyboardButton(
                text=t("btn_switch_server"), callback_data=f"key:srvmenu:{kv.id}"
            )
        ])
    rows.append([
        InlineKeyboardButton(text=t("btn_guide"), callback_data="nav:guide"),
        InlineKeyboardButton(text=t("back"), callback_data="nav:home"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def key_server_switch_kb(
    key_id: int,
    panels: list[dict[str, object]],
    current_panel_id: int,
    *,
    exabyte_ui: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for p in panels:
        pid = int(p["id"])  # type: ignore[arg-type]
        if exabyte_ui:
            lbl = _server_button_label(p, exabyte_ui=True)
            txt = f"✅ {lbl}" if pid == current_panel_id else lbl
        else:
            mark = "✅ " if pid == current_panel_id else "🌐 "
            txt = f"{mark}{p['name']} ({p['server_host']})"
        rows.append([
            InlineKeyboardButton(
                text=txt,
                callback_data=f"key:srvset:{key_id}:{pid}",
            )
        ])
    rows.append([InlineKeyboardButton(text=t("back"), callback_data="nav:key")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plans_kb(*, is_reseller: bool = False, exabyte_ui: bool = False) -> InlineKeyboardMarkup:
    del is_reseller
    unlim = P.plans_in("vpn", exabyte=exabyte_ui)
    gb = P.plans_in("vpn_gb", exabyte=exabyte_ui)
    rows: list[list[InlineKeyboardButton]] = []
    if len(unlim) == len(gb) and gb:
        for u_plan, g_plan in zip(unlim, gb, strict=False):
            rows.append([
                InlineKeyboardButton(text=u_plan.name, callback_data=f"plan:{u_plan.id}"),
                InlineKeyboardButton(text=g_plan.name, callback_data=f"plan:{g_plan.id}"),
            ])
    else:
        for p in P.all_plans(exabyte=exabyte_ui):
            rows.append([
                InlineKeyboardButton(text=p.name, callback_data=f"plan:{p.id}")
            ])
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
    plan_id: str,
    target_sub_id: int,
    panels: list[dict[str, object]],
    *,
    exabyte_ui: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=_server_button_label(p, exabyte_ui=exabyte_ui),
                callback_data=f"psrv:{plan_id}:{target_sub_id}:{int(p['id'])}",  # type: ignore[arg-type]
            )
        ]
        for p in panels
    ]
    rows.append([InlineKeyboardButton(text=t("back"), callback_data="nav:plans")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_created_kb(
    code: str,
    *,
    is_admin: bool = False,
    can_pay_balance: bool = False,
    amount_text: str = "",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_pay_balance:
        rows.append([
            InlineKeyboardButton(
                text=t("btn_pay_with_balance", amount=amount_text or "2,400 ကျပ်"),
                callback_data=f"ord:bal_pay:{code}",
            )
        ])
    if is_admin:
        rows.append([
            InlineKeyboardButton(
                text="⚡ Admin Key တိုက်ရိုက်ထုတ်ယူမည် (Screenshot မလို)",
                callback_data=f"ord:adm_take:{code}",
            )
        ])
    rows.extend([
        [InlineKeyboardButton(text=t("cancel"), callback_data=f"ord:cancel:{code}")],
        [InlineKeyboardButton(text=t("back"), callback_data="nav:home")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def guide_menu_kb(settings: Settings | None = None) -> InlineKeyboardMarkup:
    del settings
    from ..downloads import APP_STORE_URL, MAC_URL, PLAY_STORE_URL, WINDOWS_URL
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬇️ Android Download", callback_data="download:apk")],
        [InlineKeyboardButton(text="Google Play", url=PLAY_STORE_URL),
         InlineKeyboardButton(text="App Store", url=APP_STORE_URL)],
        [InlineKeyboardButton(text="Windows Download", url=WINDOWS_URL),
         InlineKeyboardButton(text="Mac App Store", url=MAC_URL)],
        [InlineKeyboardButton(text=t("back"), callback_data="nav:home")],
    ])


def guide_detail_kb() -> InlineKeyboardMarkup:
    return guide_menu_kb()


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
