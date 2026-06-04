from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⚔️ Квесты", callback_data="menu:quests")
    kb.button(text="📅 Ежедневный", callback_data="menu:daily")
    kb.button(text="👤 Профиль", callback_data="menu:profile")
    kb.button(text="🏆 Топ", callback_data="menu:leaderboard")
    kb.adjust(2)
    return kb.as_markup()


def quest_list(quests: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for q in quests:
        type_icons = {"theory": "📖", "practice": "💻", "challenge": "🔥", "boss": "👹"}
        type_icon = type_icons.get(q["type"], "❓")
        kb.button(text=f"{type_icon} {q['title']}", callback_data=f"quest:detail:{q['id']}")
    kb.button(text="◀️ Назад", callback_data="menu:main")
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
