from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import client
from app.keyboards import back_to_main

router = Router()

_CATEGORY_LABELS = {
    "text": "📝 Текстовые",
    "image": "🖼 Изображения",
    "video": "🎬 Видео",
}


def _render(categories: list[dict], completed: list[dict]) -> str:
    total = sum(c["total"] for c in categories)
    done = sum(c["completed"] for c in categories)

    lines = [f"📜 <b>Мои квесты</b> — пройдено {done}/{total}\n"]

    for c in categories:
        bar_done = c["completed"]
        bar_total = c["total"]
        lines.append(f"{_CATEGORY_LABELS.get(c['key'], c['title'])}: {bar_done}/{bar_total}")

    if completed:
        lines.append("\n<b>Последние пройденные:</b>")
        for q in completed[:10]:
            score = q.get("best_score")
            score_str = f" · {score}/100" if score is not None else ""
            lines.append(f"✅ {q['title']}{score_str}")
    else:
        lines.append("\nТы ещё не прошёл ни одного квеста. Вперёд! ⚔️")

    return "\n".join(lines)


async def _show(message: Message, user_id: int, edit: bool):
    categories = await client.get_categories(user_id)
    completed = await client.get_completed_quests(user_id)
    text = _render(categories, completed)
    if edit:
        await message.edit_text(text, reply_markup=back_to_main(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=back_to_main(), parse_mode="HTML")


@router.message(Command("myquests"))
async def cmd_myquests(message: Message):
    await _show(message, message.from_user.id, edit=False)


@router.callback_query(lambda c: c.data == "menu:myquests")
async def cb_myquests(call: CallbackQuery):
    await _show(call.message, call.from_user.id, edit=True)
    await call.answer()
