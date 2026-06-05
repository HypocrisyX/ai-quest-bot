from typing import Optional

from aiogram import Bot

_bot_username: Optional[str] = None


async def start_link(bot: Bot, payload: str) -> str:
    """Build a deep link like https://t.me/<bot>?start=<payload> (username cached)."""
    global _bot_username
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = me.username
    return f"https://t.me/{_bot_username}?start={payload}"
