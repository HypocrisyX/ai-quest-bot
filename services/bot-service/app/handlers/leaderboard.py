from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import client
from app.keyboards import back_to_main

router = Router()

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _render(lb: dict) -> str:
    entries = lb.get("entries", [])
    if not entries:
        return "🏆 Таблица лидеров пуста."

    lines = ["🏆 <b>Топ игроков (неделя)</b>\n"]
    for e in entries[:10]:
        medal = MEDALS.get(e["rank"], f"{e['rank']}.")
        lines.append(
            f"{medal} <b>{e['rank']}</b>  ID:{e['user_id']}  "
            f"⚡️{e['xp_gained']} XP · ✅{e['quests_done']} квестов"
        )
    return "\n".join(lines)


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    lb = await client.get_leaderboard()
    await message.answer(_render(lb), reply_markup=back_to_main(), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "menu:leaderboard")
async def cb_leaderboard(call: CallbackQuery):
    lb = await client.get_leaderboard()
    await call.message.edit_text(
        _render(lb), reply_markup=back_to_main(), parse_mode="HTML"
    )
    await call.answer()
