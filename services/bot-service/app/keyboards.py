from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⚔️ Квесты", callback_data="menu:quests")
    kb.button(text="📜 Мои квесты", callback_data="menu:myquests")
    kb.button(text="🛒 Магазин", callback_data="menu:shop")
    kb.button(text="🏅 Достижения", callback_data="menu:achievements")
    kb.button(text="⚔️ Дуэль", callback_data="menu:duels")
    kb.button(text="📅 Ежедневный", callback_data="menu:daily")
    kb.button(text="👤 Профиль", callback_data="menu:profile")
    kb.button(text="🏆 Топ", callback_data="menu:leaderboard")
    kb.adjust(2)
    return kb.as_markup()


def shop_menu(items: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for it in items:
        title, cost = it["title"], it["cost"]
        if not it["available"]:
            kb.button(text=f"🔜 {title}", callback_data="shop:soon")
        elif not it["can_afford"]:
            kb.button(text=f"🔒 {title} — {cost} 💎", callback_data="shop:poor")
        else:
            kb.button(text=f"{title} — {cost} 💎", callback_data=f"shop:buy:{it['key']}")
    kb.button(text="🏠 Главное меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


_CATEGORY_ICONS = {"text": "📝", "image": "🖼", "video": "🎬"}


def category_menu(categories: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in categories:
        key, title, status = c["key"], c["title"], c["status"]
        icon = _CATEGORY_ICONS.get(key, "📂")
        if status == "completed":
            kb.button(text=f"✅ {title}", callback_data=f"cat:{key}")
        elif status == "unlocked":
            label = f"{icon} {title} ({c['completed']}/{c['total']})"
            kb.button(text=label, callback_data=f"cat:{key}")
        elif status == "soon":
            kb.button(text=f"🔜 {title} (скоро)", callback_data="cat:soon")
        else:  # locked
            kb.button(text=f"🔒 {title}", callback_data="cat:locked")
    kb.button(text="🏠 Главное меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def quest_list(quests: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    type_icons = {"theory": "📖", "practice": "💻", "challenge": "🔥", "boss": "👹"}
    for q in quests:
        status = q.get("status", "unlocked")
        if status == "completed":
            text = f"✅ {q['title']}"
            kb.button(text=text, callback_data=f"quest:detail:{q['id']}")
        elif status == "locked":
            text = f"🔒 {q['title']}"
            kb.button(text=text, callback_data="quest:locked")
        else:  # unlocked
            icon = type_icons.get(q["type"], "❓")
            kb.button(text=f"{icon} {q['title']}", callback_data=f"quest:detail:{q['id']}")
    kb.button(text="◀️ К категориям", callback_data="menu:quests")
    kb.adjust(1)
    return kb.as_markup()


def quest_detail(quest_id: int, has_hints: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="▶️ Начать", callback_data=f"quest:start:{quest_id}")
    if has_hints:
        kb.button(text="💡 Подсказка", callback_data=f"quest:hint:{quest_id}")
    kb.button(text="◀️ К списку", callback_data="menu:quests")
    kb.adjust(1)
    return kb.as_markup()


def quest_result(quest_id: int, passed: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not passed:
        kb.button(text="🔄 Попробовать снова", callback_data=f"quest:start:{quest_id}")
    kb.button(text="⚔️ Другие квесты", callback_data="menu:quests")
    kb.button(text="🏠 Главное меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def cancel() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="menu:main")
    return kb.as_markup()


def back_to_main() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🏠 Главное меню", callback_data="menu:main")
    return kb.as_markup()


def duel_quest_list(quests: list[dict]) -> InlineKeyboardMarkup:
    """Quests the challenger can pick for a duel (locked ones excluded)."""
    kb = InlineKeyboardBuilder()
    type_icons = {"theory": "📖", "practice": "💻", "challenge": "🔥", "boss": "👹"}
    for q in quests:
        if q.get("status") == "locked":
            continue
        icon = type_icons.get(q["type"], "❓")
        kb.button(text=f"{icon} {q['title']}", callback_data=f"duel:quest:{q['id']}")
    kb.button(text="🏠 Главное меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def duel_challenge(code: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⚔️ Принять вызов", callback_data=f"duel:accept:{code}")
    kb.button(text="🏠 Главное меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()
