from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import client
from app.keyboards import back_to_main

router = Router()

# Full catalog (code → icon+title) so we can show locked ones too.
_CATALOG = [
    ("first_quest", "🎯 Первые шаги"),
    ("quests_5", "🖐 Разогрев"),
    ("quests_10", "🔟 Десятка"),
    ("quests_25", "📚 Эрудит"),
    ("level_2", "⭐️ Ученик"),
    ("level_3", "🌟 Практик"),
    ("streak_3", "🔥 Постоянство"),
    ("streak_7", "💫 Неделя в деле"),
]


def _render(earned: list[dict]) -> str:
    earned_codes = {a["code"] for a in earned}
    lines = [f"🏅 <b>Достижения</b> — {len(earned_codes)}/{len(_CATALOG)}\n"]
    for code, label in _CATALOG:
        if code in earned_codes:
            lines.append(f"✅ {label}")
        else:
            lines.append(f"🔒 <s>{label}</s>")
    return "\n".join(lines)


async def _show(message: Message, user_id: int, edit: bool):
    earned = await client.get_achievements(user_id)
    text = _render(earned)
    if edit:
        await message.edit_text(text, reply_markup=back_to_main(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=back_to_main(), parse_mode="HTML")


@router.message(Command("achievements"))
async def cmd_achievements(message: Message):
    await _show(message, message.from_user.id, edit=False)


@router.callback_query(lambda c: c.data == "menu:achievements")
async def cb_achievements(call: CallbackQuery):
    await _show(call.message, call.from_user.id, edit=True)
    await call.answer()
