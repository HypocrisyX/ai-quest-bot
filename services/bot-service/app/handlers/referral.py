import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import client
from app.keyboards import back_to_main
from app.links import start_link

router = Router()
logger = logging.getLogger("bot-service")

BONUS = 100  # mirror of user-service REFERRAL_BONUS, for display


async def _show_referral(message: Message, user_id: int, edit: bool):
    stats = await client.get_referral_stats(user_id)
    link = await start_link(message.bot, f"ref_{user_id}")
    text = (
        "🤝 <b>Реферальная программа</b>\n\n"
        f"Приглашай друзей — вы <b>оба</b> получаете +{BONUS} 💎!\n\n"
        "Твоя ссылка:\n"
        f"🔗 {link}\n\n"
        f"👥 Приглашено: <b>{stats['invited']}</b> · "
        f"заработано: <b>{stats['earned']}</b> 💎"
    )
    if edit:
        await message.edit_text(text, reply_markup=back_to_main(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=back_to_main(), parse_mode="HTML")


@router.message(Command("ref"))
async def cmd_ref(message: Message):
    await _show_referral(message, message.from_user.id, edit=False)


@router.callback_query(lambda c: c.data == "menu:ref")
async def cb_ref(call: CallbackQuery):
    await _show_referral(call.message, call.from_user.id, edit=True)
    await call.answer()


async def handle_ref_deeplink(message: Message, referrer_raw: str, is_new: bool):
    """Called by the deep-link dispatcher for a `ref_<id>` payload.

    Only NEW users (just registered via the link) trigger a referral, to keep
    existing users from farming the bonus.
    """
    user = message.from_user

    try:
        referrer_id = int(referrer_raw)
    except ValueError:
        await message.answer("👋 Привет! Используй /start для главного меню.")
        return

    if not is_new or referrer_id == user.id:
        # Existing user, or self-link — no referral, just greet.
        await message.answer(
            "👋 С возвращением! Используй /start для главного меню."
        )
        return

    result = await client.complete_referral(referrer_id, user.id)
    if result.get("created"):
        bonus = result["bonus"]
        await message.answer(
            f"🎉 <b>Добро пожаловать!</b>\n\n"
            f"Ты пришёл по приглашению и получаешь <b>+{bonus} 💎</b>!\n"
            "Используй /start, чтобы начать.",
            reply_markup=back_to_main(),
            parse_mode="HTML",
        )
        # Notify the referrer (they're offline).
        try:
            await message.bot.send_message(
                referrer_id,
                f"🎉 По твоей ссылке присоединился друг! <b>+{bonus} 💎</b>",
                parse_mode="HTML",
            )
        except Exception:
            logger.info("Could not notify referrer %s", referrer_id)
    else:
        await message.answer(
            "👋 Привет! Используй /start для главного меню.",
            reply_markup=back_to_main(),
        )
