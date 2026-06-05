from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    DailyQuest,
    Quest,
    QuestCriterion,
    QuestHint,
    UserDailyCompletion,
    UserHintUsed,
    UserQuestProgress,
)
from .schemas import QuestCriterionOut, QuestDetailOut, QuestHintOut

# ── Admin ─────────────────────────────────────────────────────────────────────

async def admin_stats(session: AsyncSession) -> dict:
    total_quests = await session.scalar(select(func.count()).select_from(Quest))
    active_quests = await session.scalar(
        select(func.count()).select_from(Quest).where(Quest.is_active)
    )
    total_completions = await session.scalar(
        select(func.count()).select_from(UserQuestProgress).where(
            UserQuestProgress.status == "completed"
        )
    )
    return {
        "total_quests": total_quests or 0,
        "active_quests": active_quests or 0,
        "total_completions": total_completions or 0,
    }


async def admin_list_quests(session: AsyncSession) -> list[dict]:
    """All quests ordered by category+order_index, each with a completion count."""
    completed = (
        select(
            UserQuestProgress.quest_id,
            func.count().label("cnt"),
        )
        .where(UserQuestProgress.status == "completed")
        .group_by(UserQuestProgress.quest_id)
        .subquery()
    )
    result = await session.execute(
        select(Quest, func.coalesce(completed.c.cnt, 0))
        .outerjoin(completed, completed.c.quest_id == Quest.id)
        .order_by(Quest.order_index)
    )
    cat_rank = {"text": 0, "image": 1, "video": 2}
    items = [
        {
            "id": q.id,
            "title": q.title,
            "category": q.category,
            "type": q.type,
            "order_index": q.order_index,
            "is_active": q.is_active,
            "completions": cnt,
        }
        for q, cnt in result
    ]
    items.sort(key=lambda x: (cat_rank.get(x["category"], 99), x["order_index"]))
    return items


async def get_quest(session: AsyncSession, quest_id: int) -> Optional[Quest]:
    result = await session.execute(
        select(Quest).where(Quest.id == quest_id, Quest.is_active)
    )
    return result.scalar_one_or_none()


async def get_quests_for_level(
    session: AsyncSession, user_level: int
) -> list[Quest]:
    result = await session.execute(
        select(Quest).where(
            Quest.level_min <= user_level,
            Quest.is_active,
        ).order_by(Quest.order_index)
    )
    return list(result.scalars())


# Category "worlds" in unlock order — like RPG locations.
CATEGORY_ORDER = [
    ("text", "Текстовые промпты"),
    ("image", "Генерация изображений"),
    ("video", "Генерация видео"),
]


async def _completed_quest_ids(session: AsyncSession, user_id: int) -> set[int]:
    result = await session.execute(
        select(UserQuestProgress.quest_id).where(
            UserQuestProgress.user_id == user_id,
            UserQuestProgress.status == "completed",
        )
    )
    return set(result.scalars())


async def get_quests_with_status(
    session: AsyncSession, category: str, user_id: int
) -> list[dict]:
    """Quests in a category, each tagged with sequential-unlock status.

    Walking quests in order_index order: completed quests stay 'completed',
    the first not-yet-completed quest is 'unlocked', everything after is 'locked'.
    """
    result = await session.execute(
        select(Quest)
        .where(Quest.category == category, Quest.is_active)
        .order_by(Quest.order_index)
    )
    quests = list(result.scalars())
    completed_ids = await _completed_quest_ids(session, user_id)

    items: list[dict] = []
    unlock_next = True
    for quest in quests:
        if quest.id in completed_ids:
            status = "completed"
        elif unlock_next:
            status = "unlocked"
            unlock_next = False  # lock everything after the first open quest
        else:
            status = "locked"
        items.append({"quest": quest, "status": status})
    return items


async def training_progress(session: AsyncSession, user_id: int) -> dict:
    """Overall completion across all active quests. complete=True unlocks marketplace."""
    total = await session.scalar(
        select(func.count()).select_from(Quest).where(Quest.is_active)
    )
    completed = await session.scalar(
        select(func.count())
        .select_from(UserQuestProgress)
        .join(Quest, Quest.id == UserQuestProgress.quest_id)
        .where(UserQuestProgress.status == "completed", Quest.is_active)
    )
    total = total or 0
    completed = completed or 0
    return {
        "completed": completed,
        "total": total,
        "complete": total > 0 and completed >= total,
    }


async def get_completed_quests(
    session: AsyncSession, user_id: int, limit: int = 50
) -> list[dict]:
    """Completed quests for a user, newest first, joined with quest title/category."""
    result = await session.execute(
        select(
            Quest.id, Quest.title, Quest.category,
            UserQuestProgress.best_score, UserQuestProgress.completed_at,
        )
        .join(UserQuestProgress, UserQuestProgress.quest_id == Quest.id)
        .where(
            UserQuestProgress.user_id == user_id,
            UserQuestProgress.status == "completed",
        )
        .order_by(UserQuestProgress.completed_at.desc())
        .limit(limit)
    )
    return [
        {
            "quest_id": row.id,
            "title": row.title,
            "category": row.category,
            "best_score": row.best_score,
            "completed_at": row.completed_at,
        }
        for row in result
    ]


async def get_categories_with_status(
    session: AsyncSession, user_id: int
) -> list[dict]:
    """Category 'worlds' with sequential unlock: a category opens only once
    every quest in the previous category is completed.

    status: 'completed' (all done) | 'unlocked' (open, in progress) |
            'locked' (previous not finished) | 'soon' (open slot, no quests yet)
    """
    completed_ids = await _completed_quest_ids(session, user_id)

    items: list[dict] = []
    prev_fully_done = True  # first category is always open
    for key, title in CATEGORY_ORDER:
        ids_result = await session.execute(
            select(Quest.id).where(Quest.category == key, Quest.is_active)
        )
        ids = list(ids_result.scalars())
        total = len(ids)
        done = sum(1 for qid in ids if qid in completed_ids)

        if not prev_fully_done:
            status = "locked"
        elif total == 0:
            status = "soon"  # reachable, but no content yet (e.g. video)
        elif done >= total:
            status = "completed"
        else:
            status = "unlocked"

        items.append({
            "key": key, "title": title, "status": status,
            "total": total, "completed": done,
        })
        # next world unlocks only when this one is fully cleared
        prev_fully_done = prev_fully_done and total > 0 and done >= total

    return items


async def get_quest_criteria(
    session: AsyncSession, quest_id: int
) -> list[QuestCriterion]:
    result = await session.execute(
        select(QuestCriterion).where(QuestCriterion.quest_id == quest_id)
    )
    return list(result.scalars())


async def get_quest_hints(
    session: AsyncSession, quest_id: int
) -> list[QuestHint]:
    result = await session.execute(
        select(QuestHint)
        .where(QuestHint.quest_id == quest_id)
        .order_by(QuestHint.order_index)
    )
    return list(result.scalars())


async def get_quest_detail(
    session: AsyncSession, quest_id: int
) -> Optional[QuestDetailOut]:
    quest = await get_quest(session, quest_id)
    if not quest:
        return None

    criteria = await get_quest_criteria(session, quest_id)
    hints = await get_quest_hints(session, quest_id)

    return QuestDetailOut(
        **{c: getattr(quest, c) for c in QuestDetailOut.model_fields if hasattr(quest, c)},
        criteria=[QuestCriterionOut.model_validate(c) for c in criteria],
        hints=[QuestHintOut.model_validate(h) for h in hints],
    )


async def get_hint(session: AsyncSession, hint_id: int) -> Optional[QuestHint]:
    result = await session.execute(
        select(QuestHint).where(QuestHint.id == hint_id)
    )
    return result.scalar_one_or_none()


async def get_user_progress(
    session: AsyncSession, user_id: int, quest_id: int
) -> Optional[UserQuestProgress]:
    result = await session.execute(
        select(UserQuestProgress).where(
            UserQuestProgress.user_id == user_id,
            UserQuestProgress.quest_id == quest_id,
        )
    )
    return result.scalar_one_or_none()


async def start_quest(
    session: AsyncSession, user_id: int, quest_id: int
) -> UserQuestProgress:
    progress = await get_user_progress(session, user_id, quest_id)
    if progress:
        progress.status = "in_progress"
        progress.attempts += 1
        await session.flush()
        return progress

    progress = UserQuestProgress(user_id=user_id, quest_id=quest_id, attempts=1)
    session.add(progress)
    await session.flush()
    return progress


async def complete_quest(
    session: AsyncSession,
    user_id: int,
    quest_id: int,
    score: int,
    xp_earned: int,
) -> UserQuestProgress:
    progress = await get_user_progress(session, user_id, quest_id)
    progress.status = "completed"
    progress.xp_earned = xp_earned
    progress.completed_at = datetime.now(timezone.utc)

    if progress.best_score is None or score > progress.best_score:
        progress.best_score = score

    await session.flush()
    return progress


async def fail_quest(
    session: AsyncSession, user_id: int, quest_id: int
) -> UserQuestProgress:
    progress = await get_user_progress(session, user_id, quest_id)
    progress.status = "failed"
    await session.flush()
    return progress


async def is_hint_used(
    session: AsyncSession, user_id: int, hint_id: int
) -> bool:
    result = await session.execute(
        select(UserHintUsed).where(
            UserHintUsed.user_id == user_id,
            UserHintUsed.hint_id == hint_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def record_hint_used(
    session: AsyncSession, user_id: int, hint_id: int
) -> None:
    if not await is_hint_used(session, user_id, hint_id):
        session.add(UserHintUsed(user_id=user_id, hint_id=hint_id))
        await session.flush()


async def get_daily_quest(
    session: AsyncSession, for_date: date, user_level: int
) -> Optional[DailyQuest]:
    result = await session.execute(
        select(DailyQuest).where(
            DailyQuest.date == for_date,
            DailyQuest.level_min <= user_level,
        ).order_by(DailyQuest.level_min.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def is_daily_completed(
    session: AsyncSession, user_id: int, daily_id: int
) -> bool:
    result = await session.execute(
        select(UserDailyCompletion).where(
            UserDailyCompletion.user_id == user_id,
            UserDailyCompletion.daily_id == daily_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def complete_daily(
    session: AsyncSession, user_id: int, daily_id: int
) -> UserDailyCompletion:
    completion = UserDailyCompletion(user_id=user_id, daily_id=daily_id)
    session.add(completion)
    await session.flush()
    return completion
