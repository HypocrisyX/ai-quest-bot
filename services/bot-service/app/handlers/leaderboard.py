from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import client

router = Router()

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _toggle_kb(metric: str):
    kb = InlineKeyboardBuilder()
    xp_label = "🏆 По XP" + (" ✓" if metric == "xp" else "")
    elo_label = "⚔️ По ELO" + (" ✓" if metric == "elo" else "")
    kb.button(text=xp_label, callback_data="lb:xp")
    kb.button(text=elo_label, callback_data="lb:elo")
    kb.button(text="🏠 Главное меню", callback_data="menu:main")
    kb.adjust(2, 1)
    return kb.as_markup()


def _render(data: dict) -> str:
    metric = data["metric"]
    entries = data.get("entries", [])
    if not entries:
        return "🏆 Таблица лидеров пуста. Будь первым — проходи квесты!"

    title = "🏆 <b>Топ по XP</b>" if metric == "xp" else "⚔️ <b>Топ по ELO</b>"
    lines = [title, ""]
    for e in entries:
        medal = MEDALS.get(e["rank"], f"<b>{e['rank']}.</b>")
        if metric == "xp":
            value = f"ур.{e['level']} · {e['xp']}xp"
        else:
            value = f"{e['elo_rating']} ELO"
        lines.append(f"{medal} {e['name']} — {value}")

    me = data.get("me")
    if me:
        lines.append(f"\n<i>Ты на {me['rank']}-м месте</i>")
    return "\n".join(lines)


async def _show(message: Message, user_id: int, metric: str, edit: bool):
    data = await client.get_leaderboard(metric, user_id)
    text = _render(data)
    kb = _toggle_kb(metric)
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    await _show(message, message.from_user.id, "xp", edit=False)


@router.callback_query(lambda c: c.data == "menu:leaderboard")
async def cb_leaderboard(call: CallbackQuery):
    await _show(call.message, call.from_user.id, "xp", edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("lb:"))
async def cb_leaderboard_toggle(call: CallbackQuery):
    metric = call.data.split(":")[1]
    await _show(call.message, call.from_user.id, metric, edit=True)
    await call.answer()
