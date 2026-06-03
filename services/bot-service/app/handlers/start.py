from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from app import client
from app.keyboards import main_menu

router = Router()

WELCOME = (
    "👋 Привет, <b>{name}</b>!\n\n"
    "Добро пожаловать в <b>AI Quest Bot</b> — тренажёр по работе с ИИ.\n\n"
    "Выполняй квесты, зарабатывай XP и кристаллы, поднимайся в таблице лидеров!\n\n"
    "Выбери действие:"
)


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await client.register_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        language_code=user.language_code or "ru",
    )
    await message.answer(
        WELCOME.format(name=user.first_name),
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "menu:main")
async def menu_main(call: CallbackQuery):
    await call.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыбери действие:",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )
    await call.answer()
