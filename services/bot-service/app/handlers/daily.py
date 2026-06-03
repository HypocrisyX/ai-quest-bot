from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import client
from app.keyboards import back_to_main, cancel

router = Router()


@router.message(Command("daily"))
async def cmd_daily(message: Message):
    await _show_daily(message, message.from_user.id)


@router.callback_query(lambda c: c.data == "menu:daily")
async def cb_daily(call: CallbackQuery):
    await _show_daily(call.message, call.from_user.id, edit=True)
    await call.answer()


async def _show_daily(message: Message, user_id: int, edit: bool = False):
    profile = await client.get_profile(user_id)
    level = profile["stats"]["level"]
    daily = await client.get_daily(level)

    if not daily:
        text = "📅 Сегодня ежедневного квеста нет. Загляни завтра!"
        kb = back_to_main()
    else:
        quest = daily.get("quest", {})
        bonus = daily.get("xp_bonus", 0)
        text = (
            f"📅 <b>Ежедневный квест</b>\n\n"
            f"⚔️ {quest.get('title', '—')}\n"
            f"⚡️ Бонус: +{bonus} XP к обычной награде\n\n"
            f"{quest.get('description', '')}"
        )
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text="▶️ Начать",
            callback_data=f"quest:start:{quest['id']}"
        )
        kb_builder.button(text="🏠 Главное меню", callback_data="menu:main")
        kb_builder.adjust(1)
        kb = kb_builder.as_markup()

    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
