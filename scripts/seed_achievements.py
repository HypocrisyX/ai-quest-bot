"""Seed script: achievement catalog for user-service DB.

Unlock conditions live in code (user-service repository.ACHIEVEMENT_RULES);
this table holds only the display data and rewards.
"""
import asyncio
import os

import asyncpg

DB_URL = os.getenv(
    "USER_DB_URL",
    "postgresql://postgres:postgres@localhost:5432/user_service",
)

# (code, title, description, icon, xp_reward, crystal_reward)
ACHIEVEMENTS = [
    ("first_quest", "Первые шаги", "Пройди свой первый квест", "🎯", 20, 5),
    ("quests_5", "Разогрев", "Пройди 5 квестов", "🖐", 40, 10),
    ("quests_10", "Десятка", "Пройди 10 квестов", "🔟", 80, 15),
    ("quests_25", "Эрудит", "Пройди 25 квестов", "📚", 150, 30),
    ("level_2", "Ученик", "Достигни 2 уровня", "⭐️", 0, 10),
    ("level_3", "Практик", "Достигни 3 уровня", "🌟", 0, 20),
    ("streak_3", "Постоянство", "Серия 3 дня подряд", "🔥", 30, 10),
    ("streak_7", "Неделя в деле", "Серия 7 дней подряд", "💫", 100, 25),
]


async def seed(conn: asyncpg.Connection) -> None:
    print("Upserting achievements...")
    await conn.executemany(
        """
        INSERT INTO achievements (code, title, description, icon, xp_reward, crystal_reward)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (code) DO UPDATE SET
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            icon = EXCLUDED.icon,
            xp_reward = EXCLUDED.xp_reward,
            crystal_reward = EXCLUDED.crystal_reward
        """,
        ACHIEVEMENTS,
    )
    total = await conn.fetchval("SELECT COUNT(*) FROM achievements")
    print(f"Done! {total} achievements in DB.")


async def main() -> None:
    conn = await asyncpg.connect(DB_URL)
    try:
        await seed(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
