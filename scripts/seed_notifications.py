"""Seed script: notification templates for notification-service DB."""
import asyncio
import os

import asyncpg

DB_URL = os.getenv(
    "NOTIFICATION_DB_URL",
    "postgresql://postgres:postgres@localhost:5436/notification_service",
)

TEMPLATES = [
    # (code, title, body_template, category)
    (
        "quest_completed",
        "Квест пройден",
        "✅ Квест «{quest_title}» пройден! Оценка: {score}/100. +{xp} XP",
        "quest",
    ),
    (
        "level_up",
        "Новый уровень",
        "🎉 Поздравляем! Ты достиг уровня {level} — {title}!",
        "quest",
    ),
    (
        "streak_milestone",
        "Серия дней",
        "🔥 Серия {streak_days} дней! Ты занимаешься каждый день — это круто!",
        "streak",
    ),
    (
        "duel_challenge",
        "Вызов на дуэль",
        "⚔️ Тебя вызвали на дуэль! Квест: «{quest_title}». Принять вызов?",
        "duel",
    ),
    (
        "duel_finished_win",
        "Победа в дуэли",
        "🏆 Ты победил в дуэли! Счёт: {my_score} vs {their_score}. +{elo_delta} ELO",
        "duel",
    ),
    (
        "duel_finished_loss",
        "Поражение в дуэли",
        "😔 Дуэль проиграна. Счёт: {my_score} vs {their_score}. {elo_delta} ELO",
        "duel",
    ),
    (
        "daily_reminder",
        "Ежедневный квест",
        "📅 Не забудь выполнить ежедневный квест! Бонус: +{xp_bonus} XP",
        "system",
    ),
    (
        "achievement_unlocked",
        "Достижение получено",
        "🏅 Достижение разблокировано: «{title}»! {description}",
        "quest",
    ),
]


async def seed(conn: asyncpg.Connection) -> None:
    count = await conn.fetchval("SELECT COUNT(*) FROM notification_templates")
    if count > 0:
        print(f"Already seeded ({count} templates). Skipping.")
        return

    print("Inserting notification templates...")
    await conn.executemany(
        """
        INSERT INTO notification_templates (code, title, body_template, category)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT DO NOTHING
        """,
        TEMPLATES,
    )
    print(f"Done! Inserted {len(TEMPLATES)} templates.")


async def main() -> None:
    conn = await asyncpg.connect(DB_URL)
    try:
        await seed(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
