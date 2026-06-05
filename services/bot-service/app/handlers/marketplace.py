import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import client
from app.handlers.admin import ADMIN_IDS
from app.keyboards import back_to_main, cancel

router = Router()
logger = logging.getLogger("bot-service")

PAGE = 6
PRICE_MIN = 10
PRICE_MAX = 10000


class ListingFlow(StatesGroup):
    title = State()
    description = State()
    price = State()
    payload_text = State()
    payload_extra = State()


# ── Menu (gated by training completion) ───────────────────────────────────────

def _menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🛍 Каталог", callback_data="market:catalog:0")
    kb.button(text="➕ Выставить", callback_data="market:sell")
    kb.button(text="📦 Мои товары", callback_data="market:mylistings")
    kb.button(text="🎒 Мои покупки", callback_data="market:purchases")
    kb.button(text="🏠 Главное меню", callback_data="menu:main")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


async def _open_market(message: Message, user_id: int, edit: bool):
    progress = await client.training_complete(user_id)
    if not progress.get("complete"):
        done, total = progress.get("completed", 0), progress.get("total", 0)
        text = (
            "🏪 <b>Маркетплейс</b> открывается после прохождения всех квестов.\n\n"
            f"Прогресс: <b>{done}/{total}</b>. Заверши обучение — и продавай "
            "свои промпты, агентов и идеи за кристаллы!"
        )
        kb = back_to_main()
    else:
        text = (
            "🏪 <b>Маркетплейс</b>\n\n"
            "Покупай и продавай промпты, ботов, AI-агентов за 💎.\n"
            "С каждой продажи комиссия 10% идёт площадке."
        )
        kb = _menu_kb()
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("market"))
async def cmd_market(message: Message):
    await _open_market(message, message.from_user.id, edit=False)


@router.callback_query(lambda c: c.data == "menu:market")
async def cb_market(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await _open_market(call.message, call.from_user.id, edit=True)
    await call.answer()


# ── Catalog ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("market:catalog:"))
async def cb_catalog(call: CallbackQuery):
    offset = int(call.data.split(":")[2])
    data = await client.list_listings(call.from_user.id, limit=PAGE, offset=offset)
    total, listings = data["total"], data["listings"]

    kb = InlineKeyboardBuilder()
    if not listings:
        text = "🛍 <b>Каталог пуст.</b> Стань первым продавцом!"
    else:
        text = f"🛍 <b>Каталог</b> ({offset + 1}–{offset + len(listings)} из {total})"
        for it in listings:
            kb.button(
                text=f"{it['title']} — {it['price']}💎",
                callback_data=f"market:view:{it['id']}",
            )
    nav = []
    if offset > 0:
        nav.append(("◀️", f"market:catalog:{max(0, offset - PAGE)}"))
    if offset + PAGE < total:
        nav.append(("▶️", f"market:catalog:{offset + PAGE}"))
    for label, cb in nav:
        kb.button(text=label, callback_data=cb)
    kb.button(text="◀️ Маркетплейс", callback_data="menu:market")
    kb.adjust(1, *([2] if len(nav) == 2 else [1] * len(nav)), 1)

    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("market:view:"))
async def cb_view(call: CallbackQuery):
    listing_id = int(call.data.split(":")[2])
    listing = await client.get_listing(listing_id)
    if listing is None:
        await call.answer("Товар недоступен", show_alert=True)
        return

    purchased = await client.has_purchased(call.from_user.id, listing_id)
    is_owner = listing["seller_id"] == call.from_user.id

    text = (
        f"🛍 <b>{listing['title']}</b>\n\n"
        f"{listing.get('description') or '—'}\n\n"
        f"💎 Цена: <b>{listing['price']}</b> · продаж: {listing['sales_count']}"
    )
    kb = InlineKeyboardBuilder()
    if is_owner:
        text += "\n\n<i>Это твой товар.</i>"
    elif purchased:
        kb.button(text="🎒 Получить снова", callback_data=f"market:get:{listing_id}")
    else:
        kb.button(text=f"💎 Купить за {listing['price']}", callback_data=f"market:buy:{listing_id}")
    kb.button(text="⚠️ Пожаловаться", callback_data=f"market:report:{listing_id}")
    kb.button(text="◀️ Каталог", callback_data="market:catalog:0")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()


# ── Buy + deliver ─────────────────────────────────────────────────────────────

async def _deliver(message: Message, listing_id: int):
    payload = await client.get_listing_payload(listing_id)
    text = f"📦 <b>{payload['title']}</b>\n\n{payload['payload_text']}"
    if payload.get("payload_url"):
        text += f"\n\n🔗 {payload['payload_url']}"
    await message.answer(text, parse_mode="HTML")
    if payload.get("payload_file_id"):
        try:
            await message.answer_document(payload["payload_file_id"])
        except Exception:
            logger.info("Could not send file for listing %s", listing_id)


@router.callback_query(F.data.startswith("market:get:"))
async def cb_get(call: CallbackQuery):
    listing_id = int(call.data.split(":")[2])
    if not await client.has_purchased(call.from_user.id, listing_id):
        await call.answer("Сначала купи товар", show_alert=True)
        return
    await _deliver(call.message, listing_id)
    await call.answer("Выдано ✅")


@router.callback_query(F.data.startswith("market:buy:"))
async def cb_buy(call: CallbackQuery):
    listing_id = int(call.data.split(":")[2])
    buyer_id = call.from_user.id

    listing = await client.get_listing(listing_id)
    if listing is None:
        await call.answer("Товар недоступен", show_alert=True)
        return
    seller_id = listing["seller_id"]
    if seller_id == buyer_id:
        await call.answer("Нельзя купить свой товар", show_alert=True)
        return
    if await client.has_purchased(buyer_id, listing_id):
        await _deliver(call.message, listing_id)
        await call.answer("Ты уже владеешь этим — выдал снова ✅")
        return

    settle = await client.marketplace_settle(buyer_id, seller_id, listing["price"])
    if not settle.get("ok"):
        reason = settle.get("reason")
        msg = "Недостаточно кристаллов 💎" if reason == "insufficient" else "Не удалось купить"
        await call.answer(msg, show_alert=True)
        return

    seller_earned = settle["seller_earned"]
    await client.record_purchase(listing_id, buyer_id, listing["price"], seller_earned)

    await call.answer("Куплено! ✅")
    await _deliver(call.message, listing_id)

    # Notify the seller.
    try:
        await call.message.bot.send_message(
            seller_id,
            f"💰 Твой товар «{listing['title']}» купили! +{seller_earned} 💎",
        )
    except Exception:
        logger.info("Could not notify seller %s", seller_id)


@router.callback_query(F.data.startswith("market:report:"))
async def cb_report(call: CallbackQuery):
    listing_id = int(call.data.split(":")[2])
    listing = await client.get_listing(listing_id)
    title = listing["title"] if listing else f"#{listing_id}"
    for admin_id in ADMIN_IDS:
        try:
            await call.message.bot.send_message(
                admin_id,
                f"⚠️ Жалоба на товар «{title}» (id {listing_id}) "
                f"от пользователя {call.from_user.id}",
            )
        except Exception:
            pass
    await call.answer("Жалоба отправлена админам", show_alert=True)


# ── Sell: create listing FSM ──────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "market:sell")
async def cb_sell(call: CallbackQuery, state: FSMContext):
    progress = await client.training_complete(call.from_user.id)
    if not progress.get("complete"):
        await call.answer("Сначала пройди все квесты", show_alert=True)
        return
    await state.set_state(ListingFlow.title)
    await call.message.edit_text(
        "➕ <b>Новый товар</b>\n\nШаг 1/5. Введи <b>название</b>:",
        reply_markup=cancel(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(ListingFlow.title, F.text)
async def sell_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text[:128])
    await state.set_state(ListingFlow.description)
    await message.answer("Шаг 2/5. Введи <b>описание</b> (или /skip):", parse_mode="HTML")


@router.message(ListingFlow.description, F.text)
async def sell_description(message: Message, state: FSMContext):
    desc = "" if message.text.strip() == "/skip" else message.text
    await state.update_data(description=desc)
    await state.set_state(ListingFlow.price)
    await message.answer(
        f"Шаг 3/5. Введи <b>цену</b> в кристаллах ({PRICE_MIN}–{PRICE_MAX}):",
        parse_mode="HTML",
    )


@router.message(ListingFlow.price, F.text)
async def sell_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer(f"Введи число от {PRICE_MIN} до {PRICE_MAX}.")
        return
    if not (PRICE_MIN <= price <= PRICE_MAX):
        await message.answer(f"Цена должна быть от {PRICE_MIN} до {PRICE_MAX}.")
        return
    await state.update_data(price=price)
    await state.set_state(ListingFlow.payload_text)
    await message.answer(
        "Шаг 4/5. Введи <b>сам товар</b> — текст, который получит покупатель "
        "(промпт, инструкция и т.д.):",
        parse_mode="HTML",
    )


@router.message(ListingFlow.payload_text, F.text)
async def sell_payload_text(message: Message, state: FSMContext):
    await state.update_data(payload_text=message.text)
    await state.set_state(ListingFlow.payload_extra)
    await message.answer(
        "Шаг 5/5. По желанию приложи <b>файл</b> или пришли <b>ссылку</b> "
        "(или /skip для публикации):",
        parse_mode="HTML",
    )


async def _publish(message: Message, state: FSMContext, file_id=None, url=None):
    data = await state.get_data()
    listing = await client.create_listing(
        seller_id=message.from_user.id,
        title=data["title"],
        description=data.get("description", ""),
        price=data["price"],
        payload_text=data["payload_text"],
        payload_file_id=file_id,
        payload_url=url,
    )
    await state.clear()
    await message.answer(
        f"✅ <b>Товар опубликован!</b>\n\n"
        f"«{listing['title']}» — {listing['price']} 💎\n"
        "Он появился в каталоге.",
        reply_markup=back_to_main(),
        parse_mode="HTML",
    )


@router.message(ListingFlow.payload_extra, F.photo)
async def sell_extra_photo(message: Message, state: FSMContext):
    await _publish(message, state, file_id=message.photo[-1].file_id)


@router.message(ListingFlow.payload_extra, F.document)
async def sell_extra_document(message: Message, state: FSMContext):
    await _publish(message, state, file_id=message.document.file_id)


@router.message(ListingFlow.payload_extra, F.text)
async def sell_extra_text(message: Message, state: FSMContext):
    text = message.text.strip()
    url = None if text == "/skip" else text
    await _publish(message, state, url=url)


# ── My listings / purchases ───────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "market:mylistings")
async def cb_mylistings(call: CallbackQuery):
    seller_id = call.from_user.id
    listings = await client.get_seller_listings(seller_id)
    stats = await client.get_seller_stats(seller_id)

    lines = [
        "📦 <b>Мои товары</b>",
        f"Продаж: <b>{stats['sales']}</b> · заработано: <b>{stats['earned']}</b> 💎\n",
    ]
    kb = InlineKeyboardBuilder()
    if not listings:
        lines.append("У тебя пока нет товаров.")
    else:
        for it in listings:
            lines.append(f"• {it['title']} — {it['price']}💎 (продаж: {it['sales_count']})")
            kb.button(
                text=f"🗑 Снять «{it['title'][:20]}»",
                callback_data=f"market:remove:{it['id']}",
            )
    kb.button(text="◀️ Маркетплейс", callback_data="menu:market")
    kb.adjust(1)
    await call.message.edit_text("\n".join(lines), reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("market:remove:"))
async def cb_remove_own(call: CallbackQuery):
    listing_id = int(call.data.split(":")[2])
    listing = await client.get_listing(listing_id)
    if listing and listing["seller_id"] != call.from_user.id:
        await call.answer("Это не твой товар", show_alert=True)
        return
    await client.remove_listing(listing_id)
    await call.answer("Товар снят с продажи", show_alert=True)
    await cb_mylistings(call)


@router.callback_query(lambda c: c.data == "market:purchases")
async def cb_purchases(call: CallbackQuery):
    purchases = await client.get_buyer_purchases(call.from_user.id)
    kb = InlineKeyboardBuilder()
    if not purchases:
        text = "🎒 <b>Мои покупки</b>\n\nПока пусто."
    else:
        text = "🎒 <b>Мои покупки</b>\n\nНажми, чтобы получить снова:"
        for p in purchases:
            listing = p["listing"]
            kb.button(text=f"🎁 {listing['title']}", callback_data=f"market:get:{listing['id']}")
    kb.button(text="◀️ Маркетплейс", callback_data="menu:market")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()
