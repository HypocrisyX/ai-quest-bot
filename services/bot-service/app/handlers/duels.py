import os
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import client
from app.keyboards import back_to_main, cancel, duel_challenge, duel_quest_list

router = Router()

AI_JUDGE_ENABLED = os.getenv("AI_JUDGE_ENABLED", "true").lower() == "true"

_bot_username: Optional[str] = None


class DuelFlow(StatesGroup):
    creating_answer = State()   # challenger writing their answer
    accepting_answer = State()  # opponent writing their answer


async def _duel_link(bot: Bot, code: str) -> str:
    global _bot_username
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = me.username
    return f"https://t.me/{_bot_username}?start=duel_{code}"


async def _score_answer(user_id: int, quest: dict, answer: str) -> int:
    """Test mode (AI off) → everyone scores 100 (ties). Real AI scoring later."""
    if AI_JUDGE_ENABLED:
        evaluation = await client.evaluate(user_id, quest, 1, answer)
        return evaluation["score"]
    return 100


# ── Challenger: create a duel ─────────────────────────────────────────────────

@router.message(Command("duel"))
async def cmd_duel(message: Message):
    await _show_quest_picker(message, message.from_user.id, edit=False)


@router.callback_query(lambda c: c.data == "menu:duels")
async def cb_duel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_quest_picker(call.message, call.from_user.id, edit=True)
    await call.answer()


async def _show_quest_picker(message: Message, user_id: int, edit: bool):
    quests = await client.get_quests("text", user_id)
    playable = [q for q in quests if q.get("status") != "locked"]
    header = (
        "⚔️ <b>Дуэль</b>\n"
        "Выбери квест — ты ответишь первым, затем отправишь ссылку сопернику.\n"
        "Победитель определяется по баллам (ELO + кристаллы)."
    )
    if not playable:
        text = "Сначала открой хотя бы один квест, чтобы вызвать на дуэль."
        kb = back_to_main()
    else:
        text = header
        kb = duel_quest_list(playable)
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("duel:quest:"))
async def cb_duel_quest(call: CallbackQuery, state: FSMContext):
    quest_id = int(call.data.split(":")[2])
    quest = await client.get_quest_detail(quest_id)
    await state.set_state(DuelFlow.creating_answer)
    await state.update_data(quest=quest)
    await call.message.edit_text(
        f"⚔️ <b>Дуэль: {quest['title']}</b>\n\n"
        f"{quest['instructions']}\n\n"
        "✍️ Напиши свой ответ — он будет засчитан в дуэли:",
        reply_markup=cancel(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(DuelFlow.creating_answer, F.text)
async def handle_challenger_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    quest = data["quest"]
    user_id = message.from_user.id

    score = await _score_answer(user_id, quest, message.text)
    duel = await client.create_duel(user_id, quest["id"], score, message.text)
    link = await _duel_link(message.bot, duel["code"])

    await state.clear()
    await message.answer(
        "✅ <b>Твой ответ принят!</b>\n\n"
        f"Отправь сопернику эту ссылку — он ответит на тот же квест,\n"
        "и мы определим победителя:\n\n"
        f"🔗 {link}\n\n"
        "<i>Дуэль ждёт соперника.</i>",
        reply_markup=back_to_main(),
        parse_mode="HTML",
    )


# ── Opponent: accept via deep link ────────────────────────────────────────────

@router.message(CommandStart(deep_link=True))
async def deep_link_start(message: Message, command: CommandObject, state: FSMContext):
    payload = command.args or ""
    user = message.from_user
    await client.register_user(user.id, user.username, user.first_name, user.language_code or "ru")

    if not payload.startswith("duel_"):
        # Unknown payload — fall back to a normal greeting.
        await message.answer("👋 Привет! Используй /start для главного меню.")
        return

    code = payload[len("duel_"):]
    duel = await client.get_duel_by_code(code)
    if duel is None or duel["status"] != "pending":
        await message.answer("⚔️ Эта дуэль уже недоступна.", reply_markup=back_to_main())
        return
    if duel["challenger_id"] == user.id:
        await message.answer(
            "😅 Это твоя собственная дуэль. Отправь ссылку другу!",
            reply_markup=back_to_main(),
        )
        return

    quest = await client.get_quest_detail(duel["quest_id"])
    await state.update_data(duel_code=code, quest=quest)
    await message.answer(
        f"⚔️ <b>Тебя вызвали на дуэль!</b>\n\n"
        f"Квест: <b>{quest['title']}</b>\n\n"
        "Прими вызов и ответь на тот же квест. Победитель получит ELO и кристаллы.",
        reply_markup=duel_challenge(code),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("duel:accept:"))
async def cb_duel_accept(call: CallbackQuery, state: FSMContext):
    code = call.data.split(":")[2]
    duel = await client.get_duel_by_code(code)
    if duel is None or duel["status"] != "pending":
        await call.answer("Эта дуэль уже недоступна", show_alert=True)
        return

    quest = await client.get_quest_detail(duel["quest_id"])
    await state.set_state(DuelFlow.accepting_answer)
    await state.update_data(duel_code=code, quest=quest)
    await call.message.edit_text(
        f"⚔️ <b>Дуэль: {quest['title']}</b>\n\n"
        f"{quest['instructions']}\n\n"
        "✍️ Напиши свой ответ:",
        reply_markup=cancel(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(DuelFlow.accepting_answer, F.text)
async def handle_opponent_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    quest = data["quest"]
    code = data["duel_code"]
    user_id = message.from_user.id

    score = await _score_answer(user_id, quest, message.text)

    try:
        resolution = await client.accept_duel(code, user_id, score, message.text)
    except Exception:
        await state.clear()
        await message.answer(
            "⚠️ Не удалось завершить дуэль (возможно, она уже сыграна).",
            reply_markup=back_to_main(),
        )
        return

    await state.clear()
    await _finalize_duel(message.bot, resolution, opponent_message=message)


async def _finalize_duel(bot: Bot, resolution: dict, opponent_message: Message):
    challenger_id = resolution["challenger_id"]
    opponent_id = resolution["opponent_id"]
    winner_id = resolution.get("winner_id")
    c_score = resolution["challenger_score"]
    o_score = resolution["opponent_score"]

    # Apply ELO + crystals (user-service owns ratings/economy).
    applied = await client.apply_duel_result(challenger_id, opponent_id, winner_id)

    def _result_for(user_id: int, my_score: int, their_score: int, me_key: str) -> str:
        if winner_id is None:
            head = "🤝 <b>Ничья!</b>"
        elif winner_id == user_id:
            head = "🏆 <b>Победа!</b>"
        else:
            head = "😔 <b>Поражение</b>"
        info = applied[me_key]
        elo_delta = info["elo_delta"]
        elo_sign = f"+{elo_delta}" if elo_delta >= 0 else str(elo_delta)
        lines = [
            "⚔️ <b>Дуэль завершена</b>",
            head,
            f"Счёт: <b>{my_score}</b> vs {their_score}",
            f"📊 ELO: {elo_sign} (стало {info['elo_after']})",
        ]
        if info["crystals"]:
            lines.append(f"💎 +{info['crystals']} кристаллов")
        return "\n".join(lines)

    # Opponent is here — reply inline.
    await opponent_message.answer(
        _result_for(opponent_id, o_score, c_score, "opponent"),
        reply_markup=back_to_main(),
        parse_mode="HTML",
    )
    # Challenger is elsewhere — push them the result.
    try:
        await bot.send_message(
            challenger_id,
            _result_for(challenger_id, c_score, o_score, "challenger"),
            parse_mode="HTML",
        )
    except Exception:
        pass  # challenger may have blocked the bot
