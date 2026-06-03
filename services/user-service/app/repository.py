from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Achievement, CrystalTransaction, Referral,
    Subscription, User, UserAchievement, UserStats, XpHistory,
)
from .schemas import (
    AddCrystalsResponse, AddXpResponse, UserCreate,
)


async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession, data: UserCreate
) -> tuple[User, bool]:
    user = await get_user(session, data.id)
    if user:
        return user, False

    user = User(
        id=data.id,
        username=data.username,
        first_name=data.first_name,
        language_code=data.language_code,
    )
    stats = UserStats(user_id=data.id)
    session.add(user)
    session.add(stats)
    await session.flush()
    return user, True


async def update_last_active(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(last_active_at=datetime.now(timezone.utc))
    )


async def get_user_stats(session: AsyncSession, user_id: int) -> Optional[UserStats]:
    result = await session.execute(
        select(UserStats).where(UserStats.user_id == user_id)
    )
    return result.scalar_one_or_none()


def _xp_to_next_level(level: int) -> int:
    return 100 * level


async def add_xp(
    session: AsyncSession,
    user_id: int,
    delta_xp: int,
    reason: str,
    ref_id: Optional[str] = None,
) -> AddXpResponse:
    stats = await get_user_stats(session, user_id)
    level_before = stats.level
    xp_before = stats.xp

    stats.xp += delta_xp
    leveled_up = False

    while stats.xp >= stats.xp_to_next:
        stats.xp -= stats.xp_to_next
        stats.level += 1
        stats.xp_to_next = _xp_to_next_level(stats.level)
        leveled_up = True

    stats.total_quests = (stats.total_quests or 0) + (1 if reason == "quest_complete" else 0)

    session.add(
        XpHistory(
            user_id=user_id,
            delta_xp=delta_xp,
            reason=reason,
            ref_id=ref_id,
            level_after=stats.level,
        )
    )
    await session.flush()

    return AddXpResponse(
        level_before=level_before,
        level_after=stats.level,
        xp_before=xp_before,
        xp_after=stats.xp,
        leveled_up=leveled_up,
    )


async def add_crystals(
    session: AsyncSession,
    user_id: int,
    delta: int,
    reason: str,
    ref_id: Optional[str] = None,
) -> AddCrystalsResponse:
    stats = await get_user_stats(session, user_id)
    balance_before = stats.crystals
    stats.crystals = max(0, stats.crystals + delta)

    session.add(
        CrystalTransaction(
            user_id=user_id,
            delta=delta,
            reason=reason,
            ref_id=ref_id,
            balance=stats.crystals,
        )
    )
    await session.flush()

    return AddCrystalsResponse(
        balance_before=balance_before,
        balance_after=stats.crystals,
    )


async def update_streak(session: AsyncSession, user_id: int) -> int:
    stats = await get_user_stats(session, user_id)
    today = date.today()

    if stats.streak_last_at == today:
        return stats.streak_days

    yesterday = date.fromordinal(today.toordinal() - 1)
    if stats.streak_last_at == yesterday:
        stats.streak_days += 1
    else:
        stats.streak_days = 1

    stats.streak_last_at = today
    await session.flush()
    return stats.streak_days


async def get_active_subscription(
    session: AsyncSession, user_id: int
) -> Optional[Subscription]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def get_user_achievements(
    session: AsyncSession, user_id: int
) -> list[UserAchievement]:
    result = await session.execute(
        select(UserAchievement).where(UserAchievement.user_id == user_id)
    )
    return list(result.scalars())


async def grant_achievement(
    session: AsyncSession, user_id: int, achievement_code: str
) -> Optional[UserAchievement]:
    ach_result = await session.execute(
        select(Achievement).where(Achievement.code == achievement_code)
    )
    achievement = ach_result.scalar_one_or_none()
    if not achievement:
        return None

    existing = await session.execute(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement.id,
        )
    )
    if existing.scalar_one_or_none():
        return None

    ua = UserAchievement(user_id=user_id, achievement_id=achievement.id)
    session.add(ua)
    await session.flush()
    return ua


async def create_referral(
    session: AsyncSession, referrer_id: int, referee_id: int
) -> Optional[Referral]:
    existing = await session.execute(
        select(Referral).where(Referral.referee_id == referee_id)
    )
    if existing.scalar_one_or_none():
        return None

    referral = Referral(referrer_id=referrer_id, referee_id=referee_id)
    session.add(referral)
    await session.flush()
    return referral


async def grant_referral_reward(session: AsyncSession, referral_id: int) -> None:
    await session.execute(
        update(Referral)
        .where(Referral.id == referral_id)
        .values(reward_granted=True)
    )
