from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import client
from app.keyboards import shop_menu

router = Router()


def _shop_header(crystals: int, boost: int) -> str:
    lines = [
        "🛒 <b>Магазин</b>",
        f"💎 Баланс: <b>{crystals}</b> кристаллов",
    ]
    if boost > 0:
        lines.append(f"⚡️ Активен буст ×2: ещё <b>{boost}</b> квест(а)")
    lines.append("\nВыбери товар:")
    return "\n".join(lines)


async def _render_shop(user_id: int):
    profile = await client.get_profile(user_id)
    crystals = profile["stats"]["crystals"]
    boost = profile["stats"].get("xp_boost_quests", 0)
    items = await client.get_shop(user_id)
    return _shop_header(crystals, boost), shop_menu(items)


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
async def cb_shop_buy(call: CallbackQuery):
    item_key = call.data.split(":")[2]
    result = await client.purchase_item(call.from_user.id, item_key)
    await call.answer(result["message"], show_alert=True)
    # Refresh the shop view with the new balance.
    text, kb = await _render_shop(call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
