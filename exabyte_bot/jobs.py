"""Background jobs: usage sync (~5 min), notifications, stale order expiry, nightly backup, retry queue."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from .bot.messages import back_home_kb, branded, format_order_approved_message
from .config import Settings
from .service import KeyView, Service, ServiceError
from .strings import t
from .util import fmt_bytes, fmt_date, to_ms
from .xui import PanelUnavailable

log = logging.getLogger(__name__)


def _renew_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_buy"), callback_data="nav:plans")],
            [InlineKeyboardButton(text=t("back"), callback_data="nav:home")],
        ]
    )


def _notification_text(event: str, kv: KeyView) -> str:
    if event == "expiring_1d":
        return t("notify_expiring_1d", expiry_date=fmt_date(kv.expiry_ms))
    if event == "expired":
        return t("notify_expired")
    if event == "quota_80":
        return t(
            "notify_quota_80",
            used=fmt_bytes(kv.used_bytes),
            quota=fmt_bytes(kv.quota_bytes),
        )
    if event == "quota_100":
        return t("notify_quota_100")
    raise ValueError(f"Unknown notification event: {event}")


async def retry_queued_approvals(svc: Service, bot: Bot) -> int:
    raw = await svc.db.get_setting("retry_approvals", "") or ""
    items = [x for x in raw.split(",") if ":" in x]
    if not items:
        return 0
    remaining: list[str] = []
    done = 0
    for item in items:
        code, adm_str = item.split(":", 1)
        admin_id = int(adm_str)
        try:
            res = await svc.approve_order(code, admin_id)
        except PanelUnavailable:
            remaining.append(item)
            continue
        except ServiceError:
            continue
        done += 1
        if not res.already and res.key is not None:
            with contextlib.suppress(TelegramForbiddenError):
                await bot.send_message(
                    res.order.user_id,
                    format_order_approved_message(res.order, res.key, svc.now()),
                    parse_mode="HTML",
                    reply_markup=back_home_kb(),
                )
            with contextlib.suppress(Exception):
                await bot.send_message(
                    admin_id,
                    branded(f"{t('adm_action_done')} (<code>{code}</code>)"),
                    parse_mode="HTML",
                )
    await svc.db.set_setting("retry_approvals", ",".join(remaining))
    return done


async def check_and_alert_panels(
    svc: Service,
    bot: Bot,
    settings: Settings | None,
    *,
    state: dict[str, int] | None = None,
    repeat_sec: int = 1800,
) -> list[dict[str, object]]:
    """Probe all configured 3X-UI panels and alert admins on Telegram if any panel is unreachable."""
    results = await svc.check_panels_health()
    if settings is None or not settings.admin_ids:
        return results
    alert_state = state if state is not None else {}
    now_s = int(svc.now().timestamp())
    now_str = fmt_date(to_ms(svc.now()))
    for item in results:
        key = str(item["key"])
        name = escape(str(item["name"]))
        host = escape(str(item["host"]))
        if not item["ok"]:
            last_sent = alert_state.get(key)
            if last_sent is None or (now_s - last_sent) >= repeat_sec:
                err_txt = escape(str(item.get("error") or "unreachable"))
                msg = branded(
                    f"🚨 <b>3X-UI Panel ချိတ်ဆက်၍ မရပါ!</b>\n"
                    f"• Server: <b>{name}</b> (<code>{host}</code>)\n"
                    f"• Error: <code>{err_txt}</code>\n"
                    f"• အချိန်: <b>{now_str}</b>"
                )
                for aid in settings.admin_ids:
                    with contextlib.suppress(Exception):
                        await bot.send_message(aid, msg, parse_mode="HTML")
                alert_state[key] = now_s
        elif key in alert_state:
            alert_state.pop(key, None)
            msg = branded(
                f"✅ <b>3X-UI Panel ပြန်လည် ချိတ်ဆက်မိပါပြီ!</b>\n"
                f"• Server: <b>{name}</b> (<code>{host}</code>)\n"
                f"• အချိန်: <b>{now_str}</b>"
            )
            for aid in settings.admin_ids:
                with contextlib.suppress(Exception):
                    await bot.send_message(aid, msg, parse_mode="HTML")
    return results


async def run_sync_and_notify_once(
    svc: Service,
    bot: Bot,
    settings: Settings | None = None,
    *,
    panel_alert_state: dict[str, int] | None = None,
) -> None:
    """Single pass of the ~5 minute maintenance loop (called directly in tests)."""
    await retry_queued_approvals(svc, bot)
    if settings is not None:
        await check_and_alert_panels(svc, bot, settings, state=panel_alert_state)

    try:
        await svc.sync_usage()
    except PanelUnavailable:
        log.warning("sync_usage skipped: panel unavailable")

    for uid, event, kv in await svc.collect_notifications():
        msg_txt = branded(_notification_text(event, kv))
        try:
            await bot.send_message(uid, msg_txt, parse_mode="HTML", reply_markup=_renew_kb())
            await svc.mark_notified(uid, event)
        except TelegramForbiddenError:
            await svc.mark_blocked(uid)
        except Exception:
            log.exception("failed sending %s notification to %s", event, uid)

    for order in await svc.expire_stale_orders():
        try:
            await bot.send_message(
                order.user_id,
                branded(t("order_expired", code=order.code)),
                parse_mode="HTML",
                reply_markup=back_home_kb(),
            )
        except TelegramForbiddenError:
            await svc.mark_blocked(order.user_id)
        except Exception:
            log.exception("failed sending order_expired to %s", order.user_id)


async def run_backup_once(svc: Service, bot: Bot, settings: Settings, *, keep: int = 7) -> None:
    stamp = svc.now().strftime("%Y%m%d-%H%M%S")
    bdir = settings.data_dir / "backups"
    dest = await svc.db.backup_to(bdir / f"exabyte-{stamp}.sqlite3")

    backups = sorted(bdir.glob("exabyte-*.sqlite3"))
    for old in backups[:-keep]:
        with contextlib.suppress(OSError):
            old.unlink()

    if settings.admin_ids:
        doc = BufferedInputFile(dest.read_bytes(), filename=dest.name)
        with contextlib.suppress(Exception):
            await bot.send_document(
                settings.admin_ids[0],
                document=doc,
                caption=branded(f"🛡️ SQLite Backup: <code>{dest.name}</code>"),
                parse_mode="HTML",
            )


class BackgroundRunner:
    def __init__(
        self,
        svc: Service,
        bot: Bot,
        settings: Settings,
        *,
        sync_interval_sec: float = 300.0,
        backup_interval_sec: float = 86_400.0,
    ):
        self.svc = svc
        self.bot = bot
        self.settings = settings
        self.sync_interval_sec = sync_interval_sec
        self.backup_interval_sec = backup_interval_sec
        self._tasks: list[asyncio.Task[None]] = []
        self._panel_alert_state: dict[str, int] = {}

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._sync_loop(), name="exabyte-sync"),
            asyncio.create_task(self._backup_loop(), name="exabyte-backup"),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    async def _sync_loop(self) -> None:
        while True:
            try:
                await run_sync_and_notify_once(
                    self.svc,
                    self.bot,
                    self.settings,
                    panel_alert_state=self._panel_alert_state,
                )
            except Exception:
                log.exception("unexpected error in sync loop")
            await asyncio.sleep(self.sync_interval_sec)

    async def _backup_loop(self) -> None:
        while True:
            await asyncio.sleep(self.backup_interval_sec)
            try:
                await run_backup_once(self.svc, self.bot, self.settings)
            except Exception:
                log.exception("unexpected error in backup loop")

