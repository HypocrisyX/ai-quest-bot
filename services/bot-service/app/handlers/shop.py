from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import client
from app.keyboards import back_to_main, shop_menu


class SettingTitle(StatesGroup):
    awaiting_title = State()

router = Router()


def _shop_header(
    crystals: int,
    boost: int,
    freezes: int = 0,
    hints: int = 0,
    skips: int = 0,
) -> str:
    lines = [
        "🛒 <b>Магазин</b>",
        f"💎 Баланс: <b>{crystals}</b> кристаллов",
    ]
    if boost > 0:
        lines.append(f"⚡️ Активен буст ×2: ещё <b>{boost}</b> квест(а)")
    if freezes > 0:
        lines.append(f"🧊 Заморозок серии: <b>{freezes}</b>")
    if hints > 0:
        lines.append(f"💡 Бесплатных подсказок: <b>{hints}</b>")
    if skips > 0:
        lines.append(f"⏭ Пропусков квестов: <b>{skips}</b>")
    lines.append("\nВыбери товар:")
    return "\n".join(lines)


async def _render_shop(user_id: int):
    profile = await client.get_profile(user_id)
    stats = profile["stats"]
    crystals = stats["crystals"]
    boost = stats.get("xp_boost_quests", 0)
    freezes = stats.get("streak_freeze_count", 0)
    hints = stats.get("free_hints", 0)
    skips = stats.get("quest_skips", 0)
    items = await client.get_shop(user_id)
    return _shop_header(crystals, boost, freezes, hints, skips), shop_menu(items)


@router.message(Command("shop"))
async def cmd_shop(message: Message):
    text, kb = await _render_shop(message.from_user.id)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(lambda c: c.data == "menu:shop")
async def cb_shop(call: CallbackQuery):
    text, kb = await _render_shop(call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(lambda c: c.data == "shop:soon")
async def cb_shop_soon(call: CallbackQuery):
    await call.answer("🔜 Этот товар скоро появится", show_alert=True)


@router.callback_query(lambda c: c.data == "shop:poor")
async def cb_shop_poor(call: CallbackQuery):
    await call.answer("💎 Недостаточно кристаллов — проходи квесты!", show_alert=True)


@router.callback_query(F.data.startswith("shop:buy:"))
async def cb_shop_buy(call: CallbackQuery, state: FSMContext):
    item_key = call.data.split(":")[2]
    result = await client.purchase_item(call.from_user.id, item_key)
    if result.get("ok") and result.get("message", "").startswith("INPUT:"):
        await state.set_state(SettingTitle.awaiting_title)
        await call.message.edit_text(
            "🏷 <b>Введи свой титул</b> (1–20 символов):",
            parse_mode="HTML",
            reply_markup=back_to_main(),
        )
        await call.answer()
        return
    await call.answer(result["message"], show_alert=True)
    text, kb = await _render_shop(call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.message(SettingTitle.awaiting_title, F.text)
async def handle_title_input(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) < 1 or len(title) > 20:
        await message.answer("⚠️ Титул должен быть от 1 до 20 символов. Попробуй ещё раз:")
        return
    await client.set_title(message.from_user.id, title)
    await state.clear()
    await message.answer(
        f"🏷 Титул установлен: <b>{title}</b>",
        parse_mode="HTML",
    )


@router.message(SettingTitle.awaiting_title)
async def handle_title_non_text(message: Message):
    await message.answer("Пришли текст (1–20 символов).")
