import os

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import client, events
from app.keyboards import back_to_main, cancel, quest_detail, quest_list, quest_result

STREAK_MILESTONES = {7, 30, 100}

router = Router()

PASS_THRESHOLD = 60  # minimum score to pass a quest

# When false (AI_JUDGE_ENABLED=false), answers auto-approve without calling the
# AI judge — saves tokens during testing. Flip back to true to restore real
# evaluation. See app/handlers/quests.py:handle_answer.
AI_JUDGE_ENABLED = os.getenv("AI_JUDGE_ENABLED", "true").lower() == "true"


class QuestFlow(StatesGroup):
    awaiting_answer = State()


def _quest_card(q: dict) -> str:
    type_map = {"theory": "Теория", "practice": "Практика", "challenge": "Челлендж", "boss": "Босс"}
    type_label = type_map.get(q["type"], q["type"])
    lines = [
        f"⚔️ <b>{q['title']}</b>",
        f"📌 Тип: {type_label} · Уровень {q['level_min']}+",
        f"⚡️ Награда: +{q['xp_reward']} XP",
    ]
    if q.get("crystal_reward"):
        lines.append(f"💎 +{q['crystal_reward']} кристаллов")
    if q.get("time_limit_sec"):
        lines.append(f"⏱ Лимит: {q['time_limit_sec'] // 60} мин.")
    if q.get("description"):
        lines += ["", q["description"]]
    return "\n".join(lines)


def _score_bar(score: int) -> str:
    filled = round(score / 10)
    return "█" * filled + "░" * (10 - filled)


@router.message(Command("quests"))
async def cmd_quests(message: Message):
    profile = await client.get_profile(message.from_user.id)
    level = profile["stats"]["level"]
    quests = await client.get_quests(level)
    if not quests:
        await message.answer("Квестов для твоего уровня пока нет.", reply_markup=back_to_main())
        return
    await message.answer(
        f"⚔️ <b>Доступные квесты</b> (уровень {level}):",
        reply_markup=quest_list(quests),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "menu:quests")
async def cb_quests(call: CallbackQuery, state: FSMContext):
    await state.clear()
    profile = await client.get_profile(call.from_user.id)
    level = profile["stats"]["level"]
    quests = await client.get_quests(level)
    if not quests:
        await call.message.edit_text(
            "Квестов для твоего уровня пока нет.", reply_markup=back_to_main()
        )
        await call.answer()
        return
    await call.message.edit_text(
        f"⚔️ <b>Доступные квесты</b> (уровень {level}):",
        reply_markup=quest_list(quests),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("quest:detail:"))
async def cb_quest_detail(call: CallbackQuery):
    quest_id = int(call.data.split(":")[2])
    quest = await client.get_quest_detail(quest_id)
    has_hints = bool(quest.get("hints"))
    await call.message.edit_text(
        _quest_card(quest),
        reply_markup=quest_detail(quest_id, has_hints),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("quest:start:"))
async def cb_quest_start(call: CallbackQuery, state: FSMContext):
    quest_id = int(call.data.split(":")[2])
    user_id = call.from_user.id

    quest = await client.get_quest_detail(quest_id)
    progress = await client.start_quest(user_id, quest_id)
    attempt_num = progress.get("attempts", 1)

    await state.set_state(QuestFlow.awaiting_answer)
    await state.update_data(quest=quest, attempt_num=attempt_num)

    time_note = ""
    if quest.get("time_limit_sec"):
        time_note = f"\n⏱ Время: {quest['time_limit_sec'] // 60} мин."

    await call.message.edit_text(
        f"📋 <b>{quest['title']}</b>{time_note}\n\n"
        f"{quest['instructions']}\n\n"
        "✍️ Напиши свой ответ:",
        reply_markup=cancel(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(QuestFlow.awaiting_answer, F.text)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    quest = data["quest"]
    attempt_num = data["attempt_num"]
    user_id = message.from_user.id

    if AI_JUDGE_ENABLED:
        await message.answer("🤖 Оцениваю ответ...")
        evaluation = await client.evaluate(
            user_id=user_id,
            quest=quest,
            attempt_num=attempt_num,
            user_input=message.text,
        )
        score = evaluation["score"]
        feedback = evaluation["feedback"]
    else:
        # Test mode: auto-approve without calling the AI judge (saves tokens).
        score = 100
        feedback = "✅ Тестовый режим: ответ принят автоматически (AI-проверка отключена)."

    passed = score >= PASS_THRESHOLD

    bar = _score_bar(score)
    result_text = (
        f"{'✅' if passed else '❌'} "
        f"<b>{'Квест пройден!' if passed else 'Попробуй ещё раз'}</b>\n\n"
        f"📊 Результат: <b>{score}/100</b>\n"
        f"[{bar}]\n\n"
        f"💬 {feedback}"
    )

    if passed:
        xp_earned = quest["xp_reward"]
        await client.complete_quest(user_id, quest["id"], score, xp_earned)
        xp_result = await client.add_xp(user_id, xp_earned, "quest_complete")
        streak_result = await client.update_streak(user_id)

        result_text += f"\n\n⚡️ +{xp_earned} XP"
        if xp_result.get("leveled_up"):
            result_text += f"\n🎉 <b>Новый уровень: {xp_result['level_after']}!</b>"
            await events.publish_level_up(
                user_id,
                xp_result["level_before"],
                xp_result["level_after"],
            )
        if quest.get("crystal_reward"):
            result_text += f"\n💎 +{quest['crystal_reward']} кристаллов"

        streak_days = streak_result.get("streak_days", 0)
        if streak_days in STREAK_MILESTONES:
            await events.publish_streak_milestone(user_id, streak_days)
    else:
        await client.fail_quest(user_id, quest["id"])

    await state.clear()
    await message.answer(
        result_text,
        reply_markup=quest_result(quest["id"], passed),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("quest:hint:"))
async def cb_hint(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    quest = data.get("quest") or await client.get_quest_detail(int(call.data.split(":")[2]))
    hints = quest.get("hints", [])
    if not hints:
        await call.answer("Подсказок нет", show_alert=True)
        return

    first_hint = hints[0]
    cost = first_hint.get("cost", 5)
    try:
        await client.spend_crystals(call.from_user.id, cost, "hint")
        hint_detail = await client.use_hint(first_hint["id"], call.from_user.id)
        await call.answer(f"💡 {hint_detail['text']}", show_alert=True)
    except Exception:
        await call.answer(f"Недостаточно кристаллов (нужно {cost} 💎)", show_alert=True)
