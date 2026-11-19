"""Shared, fail-closed channel membership policy for Telegram and Mini App."""

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from .config import Settings


async def is_channel_member(bot: Bot | None, settings: Settings, user_id: int) -> bool:
    if not settings.required_channel:
        return True
    if bot is None:
        return False
    try:
        member = await bot.get_chat_member(settings.required_channel, user_id)
    except TelegramAPIError:
        return False
    return member.status in {"creator", "administrator", "member"} or (
        member.status == "restricted" and bool(getattr(member, "is_member", False))
    )
