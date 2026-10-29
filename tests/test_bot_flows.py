"""End-to-end bot handler, payment, admin, and background job tests with a mocked Telegram Bot."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import (
    AnswerCallbackQuery,
    SendDocument,
    SendMessage,
    SendPhoto,
    TelegramMethod,
)
from aiogram.types import (
    Chat,
    Message,
    PhotoSize,
    Update,
    User,
)

from exabyte_bot.config import Settings
from exabyte_bot.jobs import run_backup_once, run_sync_and_notify_once
from exabyte_bot.main import build_dispatcher
from exabyte_bot.service import Service
from exabyte_bot.strings import HEADER, S
from exabyte_bot.util import GB
from tests.conftest import ADMIN, USER

# Fake token solely for aiogram's format check (never touches network).
FAKE_BOT_TOKEN = "123456789:AA" + "B" * 33  # secret-check: ignore


class RecordingSession(BaseSession):
    """Captures every Telegram API call in memory without network access."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod[Any]] = []
        self.forbidden_users: set[int] = set()
        self._msg_id = 100

    async def close(self) -> None:
        pass

    async def stream_content(self, *args: Any, **kwargs: Any):  # pragma: no cover
        yield b""

    async def make_request(
        self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None  # noqa: ASYNC109
    ) -> Any:
        self.calls.append(method)
        chat_id = getattr(method, "chat_id", None)
        if isinstance(chat_id, int) and chat_id in self.forbidden_users:
            raise TelegramForbiddenError(method=method, message="Forbidden: bot was blocked by the user")
        if isinstance(method, AnswerCallbackQuery):
            return True
        if isinstance(method, SendMessage | SendPhoto | SendDocument):
            self._msg_id += 1
            cid = int(chat_id) if isinstance(chat_id, int) else USER
            return Message(
                message_id=self._msg_id,
                date=datetime(2026, 1, 1),
                chat=Chat(id=cid, type="private"),
                text=getattr(method, "text", None),
                caption=getattr(method, "caption", None),
            )
        return True

    def sent_to(self, chat_id: int) -> list[TelegramMethod[Any]]:
        return [
            c for c in self.calls
            if getattr(c, "chat_id", None) == chat_id
        ]

    def last_text(self, chat_id: int) -> str:
        items = self.sent_to(chat_id)
        assert items, f"No messages sent to {chat_id}"
        last = items[-1]
        return getattr(last, "text", None) or getattr(last, "caption", None) or ""


def _make_harness(svc: Service, tmp_path, *, rate_limit_sec: float = 0.0):
    settings = Settings(
        _env_file=None,
        admin_ids=[ADMIN],
        kbz_number="09000000000",  # secret-check: ignore
        kbz_name="Test Owner",
        bot_domain="tgbot.lhpvpn.online",
        data_dir=tmp_path,
    )
    session = RecordingSession()
    bot = Bot(token=FAKE_BOT_TOKEN, session=session)
    dp = build_dispatcher(svc, settings, rate_limit_sec=rate_limit_sec)
    seq = 0

    def _u(uid: int) -> User:
        return User(
            id=uid,
            is_bot=False,
            first_name="Admin" if uid == ADMIN else "Alice",
            username="admin" if uid == ADMIN else "alice",
        )

    async def send_text(uid: int, text: str) -> None:
        nonlocal seq
        seq += 1
        upd = Update(
            update_id=seq,
            message=Message(
                message_id=seq,
                date=datetime(2026, 1, 1),
                chat=Chat(id=uid, type="private"),
                from_user=_u(uid),
                text=text,
            ),
        )
        await dp.feed_update(bot, upd)

    async def send_photo(uid: int, file_id: str = "fid-1", unique_id: str = "uid-1") -> None:
        nonlocal seq
        seq += 1
        upd = Update(
            update_id=seq,
            message=Message(
                message_id=seq,
                date=datetime(2026, 1, 1),
                chat=Chat(id=uid, type="private"),
                from_user=_u(uid),
                photo=[
                    PhotoSize(
                        file_id=file_id, file_unique_id=unique_id, width=800, height=600
                    )
                ],
            ),
        )
        await dp.feed_update(bot, upd)

    async def tap(uid: int, data: str) -> None:
        nonlocal seq
        seq += 1
        from aiogram.types import CallbackQuery

        msg = Message(
            message_id=seq,
            date=datetime(2026, 1, 1),
            chat=Chat(id=uid, type="private"),
            from_user=_u(uid),
            text="menu",
        )
        upd = Update(
            update_id=seq,
            callback_query=CallbackQuery(
                id=f"cb-{seq}",
                from_user=_u(uid),
                chat_instance="ci",
                message=msg,
                data=data,
            ),
        )
        await dp.feed_update(bot, upd)

    return bot, session, settings, send_text, send_photo, tap


async def test_start_help_myid_and_menus(svc: Service, tmp_path):
    _, session, _, send_text, _, tap = _make_harness(svc, tmp_path)

    await send_text(USER, "/start")
    assert HEADER in session.last_text(USER)
    assert "လုံခြုံ မြန်ဆန်" in session.last_text(USER)

    await send_text(USER, "/help")
    assert "အသုံးပြုပုံ" in session.last_text(USER)

    await send_text(USER, "/myid")
    assert str(USER) in session.last_text(USER)

    await tap(USER, "nav:guide")
    assert "ထည့်သွင်းနည်း" in session.last_text(USER)
    for plat, word in [("android", "Android"), ("ios", "iPhone"), ("desktop", "Windows")]:
        await tap(USER, f"guide:{plat}")
        assert word in session.last_text(USER)

    await tap(USER, "nav:support")
    assert "အကူအညီ" in session.last_text(USER)

    await send_text(USER, "random unknown text")
    assert S["unknown_message"] in session.last_text(USER)


async def test_trial_claim_key_and_usage_via_bot(svc: Service, tmp_path, panel):
    _, session, _, _, _, tap = _make_harness(svc, tmp_path)

    await tap(USER, "nav:key")
    assert S["no_key"] in session.last_text(USER)

    await tap(USER, "nav:trial")
    last = session.sent_to(USER)[-1]
    assert isinstance(last, SendPhoto)
    assert "ss://" in (last.caption or "")

    kv = await svc.get_key(USER)
    assert kv is not None
    panel.add_usage(kv.email, down=2 * GB)
    await svc.sync_usage()

    await tap(USER, "nav:usage")
    usage_txt = session.last_text(USER)
    assert "40%" in usage_txt and "▰" in usage_txt

    # Early reclaim shows Burmese countdown
    await tap(USER, "nav:trial")
    assert "ထပ်ယူနိုင်ပါမည်" in session.last_text(USER)


async def test_full_payment_and_admin_approval_flow(svc: Service, tmp_path):
    _, session, _, send_text, send_photo, tap = _make_harness(svc, tmp_path)

    await tap(USER, "nav:plans")
    plans_txt = session.last_text(USER)
    assert "14,500 ကျပ်" in plans_txt and "<s>15,000 ကျပ်</s>" in plans_txt

    await tap(USER, "plan:vpn_3m")
    ord_txt = session.last_text(USER)
    assert "KBZ Pay" in ord_txt and "09000000000" in ord_txt
    order = await svc.open_order(USER)
    assert order is not None

    # Sending text while waiting for screenshot prompts for a photo
    await send_text(USER, "here is text")
    assert "Screenshot ပုံ" in session.last_text(USER)

    # Upload screenshot -> user gets confirmation, admin gets photo + Approve/Reject
    await send_photo(USER, file_id="shot-fid", unique_id="shot-uid-1")
    assert order.code in session.last_text(USER)
    admin_msg = session.sent_to(ADMIN)[-1]
    assert isinstance(admin_msg, SendPhoto) and order.code in (admin_msg.caption or "")

    # Non-admin trying to forge approve callback is blocked by AdminOnly filter
    await tap(USER, f"adm:ap:{order.code}")
    assert (await svc.get_order(order.code)).state == "awaiting_review"

    # Admin approves -> user gets paid key + QR
    await tap(ADMIN, f"adm:ap:{order.code}")
    assert (await svc.get_order(order.code)).state == "approved"
    user_last = session.sent_to(USER)[-1]
    assert isinstance(user_last, SendPhoto)
    assert S["order_approved"] in (user_last.caption or "")

    # Paid user can view Unlimited usage and regenerate key
    await tap(USER, "nav:usage")
    assert "Unlimited" in session.last_text(USER)
    await tap(USER, "key:regen")
    assert S["regen_ok"] in session.last_text(USER)


async def test_reject_order_with_reason_and_panel_down_retry(svc: Service, tmp_path, transport):
    bot, session, _, send_text, send_photo, tap = _make_harness(svc, tmp_path)

    await tap(USER, "plan:vpn_1m")
    o1 = await svc.open_order(USER)
    await send_photo(USER, file_id="f1", unique_id="u1")

    # Admin rejects with a custom reason
    await tap(ADMIN, f"adm:rj:{o1.code}")
    await send_text(ADMIN, "ငွေပမာဏ မမှန်ပါ")
    assert "ငွေပမာဏ မမှန်ပါ" in session.last_text(USER)

    # New order -> panel goes down when admin taps Approve -> queued and auto-retried by jobs
    await tap(USER, "plan:vpn_1m")
    o2 = await svc.open_order(USER)
    await send_photo(USER, file_id="f2", unique_id="u2")

    transport.fail_next = 99
    await tap(ADMIN, f"adm:ap:{o2.code}")
    assert (await svc.get_order(o2.code)).state == "awaiting_review"
    assert o2.code in (await svc.db.get_setting("retry_approvals", "") or "")

    transport.fail_next = 0
    await run_sync_and_notify_once(svc, bot)
    assert (await svc.get_order(o2.code)).state == "approved"
    assert (await svc.db.get_setting("retry_approvals", "")) == ""


async def test_admin_panel_features_and_maintenance(svc: Service, tmp_path):
    _, session, _, send_text, _, tap = _make_harness(svc, tmp_path)

    await send_text(USER, "/start")
    await tap(USER, "nav:trial")

    await send_text(ADMIN, "/admin")
    assert "Admin Panel" in session.last_text(ADMIN)

    await tap(ADMIN, "adm:stats")
    assert "Exabyte စာရင်းချုပ်" in session.last_text(ADMIN)

    await tap(ADMIN, "adm:find")
    await send_text(ADMIN, "@alice")
    assert str(USER) in session.last_text(ADMIN)

    # Add 7 days and 5 GB
    await tap(ADMIN, f"adm:uact:add7d:{USER}")
    await tap(ADMIN, f"adm:uact:add5g:{USER}")
    kv = await svc.get_key(USER)
    assert kv.quota_bytes == 10 * GB

    # Ban and unban
    await tap(ADMIN, f"adm:uact:ban:{USER}")
    await send_text(USER, "/start")
    assert S["banned"] in session.last_text(USER)
    await tap(ADMIN, f"adm:uact:unban:{USER}")

    # Maintenance mode blocks regular users but not admin
    await tap(ADMIN, "adm:maint")
    await send_text(USER, "/start")
    assert S["maintenance"] in session.last_text(USER)
    await tap(ADMIN, "adm:maint")

    # CSV export
    await tap(ADMIN, "adm:csv")
    assert isinstance(session.sent_to(ADMIN)[-1], SendDocument)

    # Broadcast preview + confirm
    await tap(ADMIN, "adm:bcast")
    await send_text(ADMIN, "မင်္ဂလာပါ သတင်းအသစ်")
    assert "ပို့မည့်စာ နမူနာ" in session.last_text(ADMIN)
    await tap(ADMIN, "adm:bcast_go")
    assert "မင်္ဂလာပါ သတင်းအသစ်" in session.last_text(USER)


async def test_background_jobs_notifications_expiry_and_backup(
    svc: Service, tmp_path, panel, clock
):
    bot, session, settings, send_text, _, tap = _make_harness(svc, tmp_path)
    await send_text(USER, "/start")
    await tap(USER, "nav:trial")
    kv = await svc.get_key(USER)

    # 80% trial usage notification (sent once)
    panel.add_usage(kv.email, down=int(4.1 * GB))
    await run_sync_and_notify_once(svc, bot)
    assert "80%" in session.last_text(USER)
    count_before = len(session.sent_to(USER))
    await run_sync_and_notify_once(svc, bot)
    assert len(session.sent_to(USER)) == count_before  # not duplicated

    # 100% trial usage notification
    panel.add_usage(kv.email, down=1 * GB)
    await run_sync_and_notify_once(svc, bot)
    assert "ကုန်သွားပါပြီ" in session.last_text(USER)

    # 1 day before expiry notification
    clock.advance(days=6, hours=2)
    await run_sync_and_notify_once(svc, bot)
    assert "1 ရက်သာ" in session.last_text(USER)

    # On expiry notification + stale order auto-expiry
    await tap(USER, "plan:vpn_1m")
    stale = await svc.open_order(USER)
    clock.advance(days=2)
    await run_sync_and_notify_once(svc, bot)
    texts = [
        getattr(m, "text", "") or "" for m in session.sent_to(USER)
    ]
    assert any("သက်တမ်းကုန်သွားပါပြီ" in x for x in texts)
    assert any(stale.code in x for x in texts)

    # Nightly backup creates sqlite file and sends document to admin
    await run_backup_once(svc, bot, settings)
    assert isinstance(session.sent_to(ADMIN)[-1], SendDocument)
    assert list((tmp_path / "backups").glob("exabyte-*.sqlite3"))


def test_strings_are_myanmar_unicode_not_zawgyi():
    # Zawgyi-only codepoints like U+105A..U+1097 used in medial positions or U+1033/U+1034
    zawgyi_markers = {"\u1033", "\u1034", "\u1060", "\u1061", "\u1062", "\u1063", "\u1064"}
    for key, val in S.items():
        assert not (set(val) & zawgyi_markers), f"Possible Zawgyi in {key}"
