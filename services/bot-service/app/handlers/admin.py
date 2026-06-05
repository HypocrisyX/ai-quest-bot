import os
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import client

router = Router()

# Comma-separated Telegram IDs allowed into the admin panel.
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}

_PAGE = 8  # users per page


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _admin_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Сводка", callback_data="admin:stats")
    kb.button(text="👥 Участники", callback_data="admin:users:0")
    kb.button(text="⚔️ Квесты", callback_data="admin:quests")
    kb.button(text="🏪 Маркетплейс", callback_data="admin:market")
    kb.button(text="🏠 Главное меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def _back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Админка", callback_data="admin:menu")
    kb.adjust(1)
    return kb.as_markup()


async def _deny(target, user_id: int):
    """Tell a non-admin their ID so they can self-add to ADMIN_IDS."""
    text = (
        "⛔️ Доступ только для администраторов.\n\n"
        f"Твой Telegram ID: <code>{user_id}</code>\n"
        "Добавь его в <code>ADMIN_IDS</code> и перезапусти бота."
    )
    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML")
    else:
        await target.message.answer(text, parse_mode="HTML")
        await target.answer()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not _is_admin(message.from_user.id):
        await _deny(message, message.from_user.id)
        return
    await message.answer("🛠 <b>Админ-панель</b>", reply_markup=_admin_menu(), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "admin:menu")
async def cb_admin_menu(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await _deny(call, call.from_user.id)
        return
    await call.message.edit_text(
        "🛠 <b>Админ-панель</b>", reply_markup=_admin_menu(), parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(lambda c: c.data == "admin:stats")
async def cb_admin_stats(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await _deny(call, call.from_user.id)
        return
    users = await client.admin_user_stats()
    quests = await client.admin_quest_stats()
    duels = await client.admin_duel_stats()
    text = (
        "📊 <b>Общая сводка</b>\n\n"
        f"👥 Участников: <b>{users['total_users']}</b>\n"
        f"🟢 Активны сегодня: <b>{users['active_today']}</b>\n\n"
        f"⚔️ Квестов: <b>{quests['active_quests']}</b> активных "
        f"(всего {quests['total_quests']})\n"
        f"✅ Прохождений: <b>{quests['total_completions']}</b>\n\n"
        f"🤺 Дуэлей сыграно: <b>{duels['finished_duels']}</b> "
        f"(всего создано {duels['total_duels']})"
    )
    await call.message.edit_text(text, reply_markup=_back_kb(), parse_mode="HTML")
    await call.answer()


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).strftime("%d.%m.%y")
    except ValueError:
        return "—"


@router.callback_query(F.data.startswith("admin:users:"))
async def cb_admin_users(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await _deny(call, call.from_user.id)
        return
    offset = int(call.data.split(":")[2])
    data = await client.admin_users(limit=_PAGE, offset=offset)
    total = data["total"]
    users = data["users"]

    lines = [f"👥 <b>Участники</b> ({offset + 1}–{offset + len(users)} из {total})\n"]
    for u in users:
        uname = f"@{u['username']}" if u.get("username") else u["first_name"]
        lines.append(
            f"• <b>{uname}</b> — ур.{u['level']}, {u['xp']}xp, "
            f"{u['crystals']}💎, ELO {u['elo_rating']}\n"
            f"  ✅{u['total_quests']} квест. · рег. {_fmt_date(u['created_at'])} · "
            f"актив. {_fmt_date(u['last_active_at'])}"
        )

    kb = InlineKeyboardBuilder()
    if offset > 0:
        kb.button(text="◀️ Назад", callback_data=f"admin:users:{max(0, offset - _PAGE)}")
    if offset + _PAGE < total:
        kb.button(text="Вперёд ▶️", callback_data=f"admin:users:{offset + _PAGE}")
    kb.button(text="◀️ Админка", callback_data="admin:menu")
    kb.adjust(2, 1)

    await call.message.edit_text("\n".join(lines), reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()


_CAT_LABELS = {"text": "📝 Текст", "image": "🖼 Изображения", "video": "🎬 Видео"}


@router.callback_query(lambda c: c.data == "admin:quests")
async def cb_admin_quests(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await _deny(call, call.from_user.id)
        return
    quests = await client.admin_quests()

    lines = ["⚔️ <b>Квесты</b> (прохождений)\n"]
    current_cat = None
    for q in quests:
        if q["category"] != current_cat:
            current_cat = q["category"]
            lines.append(f"\n<b>{_CAT_LABELS.get(current_cat, current_cat)}</b>")
        active = "" if q["is_active"] else " 🚫"
        lines.append(f"{q['order_index']}. {q['title']} — <b>{q['completions']}</b>{active}")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "\n…"
    await call.message.edit_text(text, reply_markup=_back_kb(), parse_mode="HTML")
    await call.answer()


@router.callback_query(lambda c: c.data == "admin:market")
async def cb_admin_market(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await _deny(call, call.from_user.id)
        return
    listings = await client.admin_listings(limit=15)
    lines = ["🏪 <b>Маркетплейс</b> — последние товары\n"]
    kb = InlineKeyboardBuilder()
    if not listings:
        lines.append("Товаров пока нет.")
    else:
        for it in listings:
            flag = "" if it["status"] == "active" else " 🚫"
            lines.append(
                f"• {it['title']} — {it['price']}💎 "
                f"(продавец {it['seller_id']}, продаж {it['sales_count']}){flag}"
            )
            if it["status"] == "active":
                kb.button(
                    text=f"🗑 Снять «{it['title'][:18]}»",
                    callback_data=f"admin:market:remove:{it['id']}",
                )
    kb.button(text="◀️ Админка", callback_data="admin:menu")
    kb.adjust(1)
    await call.message.edit_text("\n".join(lines), reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("admin:market:remove:"))
async def cb_admin_market_remove(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await _deny(call, call.from_user.id)
        return
    listing_id = int(call.data.split(":")[3])
    await client.remove_listing(listing_id)
    await call.answer("Товар снят", show_alert=True)
    await cb_admin_market(call)
