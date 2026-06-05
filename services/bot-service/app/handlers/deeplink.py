from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from app import client
from app.handlers import duels, referral

router = Router()


@router.message(CommandStart(deep_link=True))
async def deep_link_start(message: Message, command: CommandObject):
    """Single entry point for `/start <payload>` deep links.

    Registers the user, then dispatches by payload prefix:
      duel_<code> → duel invite, ref_<id> → referral.
    """
    payload = command.args or ""
    user = message.from_user

    existing = await client.get_user(user.id)
    await client.register_user(
        user.id, user.username, user.first_name, user.language_code or "ru"
    )
    is_new = existing is None

    if payload.startswith("duel_"):
        await duels.show_duel_invite(message, payload[len("duel_"):])
    elif payload.startswith("ref_"):
        await referral.handle_ref_deeplink(message, payload[len("ref_"):], is_new)
    else:
        await message.answer("👋 Привет! Используй /start для главного меню.")
