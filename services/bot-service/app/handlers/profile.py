from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import client
from app.keyboards import back_to_main

router = Router()

_PROFILE_TPL = (
    "👤 <b>{name}</b> (@{username})\n"
    "🎖 <b>{class_title}</b> · Уровень {level}\n\n"
    "⚡️ XP: <b>{xp}</b> / {xp_to_next}\n"
    "💎 Кристаллы: <b>{crystals}</b>\n"
    "📊 Рейтинг (ELO): <b>{elo}</b>\n\n"
    "🔥 Серия: <b>{streak}</b> дн.\n"
    "✅ Квестов пройдено: <b>{total}</b>"
)


def _render(profile: dict) -> str:
    u = profile["user"]
    s = profile["stats"]
    text = _PROFILE_TPL.format(
        name=u["first_name"],
        username=u.get("username") or "—",
        class_title=s["class_title"],
        level=s["level"],
        xp=s["xp"],
        xp_to_next=s["xp_to_next"],
        crystals=s["crystals"],
        elo=s["elo_rating"],
        streak=s["streak_days"],
        total=s["total_quests"],
    )
    boost = s.get("xp_boost_quests", 0)
    if boost > 0:
        text += f"\n⚡️ Буст ×2 XP: ещё <b>{boost}</b> квест(а)"
    return text


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    profile = await client.get_profile(message.from_user.id)
    await message.answer(_render(profile), reply_markup=back_to_main(), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "menu:profile")
async def cb_profile(call: CallbackQuery):
    profile = await client.get_profile(call.from_user.id)
    await call.message.edit_text(
        _render(profile), reply_markup=back_to_main(), parse_mode="HTML"
    )
    await call.answer()
