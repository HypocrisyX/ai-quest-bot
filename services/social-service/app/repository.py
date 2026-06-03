from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Duel, Follow, LeaderboardEntry


async def create_duel(
    session: AsyncSession,
    challenger_id: int,
    opponent_id: int,
    quest_id: int,
) -> Duel:
    duel = Duel(
        challenger_id=challenger_id,
        opponent_id=opponent_id,
        quest_id=quest_id,
    )
    session.add(duel)
    await session.flush()
    return duel


async def get_duel(session: AsyncSession, duel_id: int) -> Optional[Duel]:
    result = await session.execute(
        select(Duel).where(Duel.id == duel_id)
    )
    return result.scalar_one_or_none()


async def get_active_duel(
    session: AsyncSession, user_id: int
) -> Optional[Duel]:
    result = await session.execute(
        select(Duel).where(
            Duel.status.in_(["pending", "active"]),
            (Duel.challenger_id == user_id) | (Duel.opponent_id == user_id),
        ).order_by(Duel.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def accept_duel(session: AsyncSession, duel_id: int) -> Duel:
    duel = await get_duel(session, duel_id)
    duel.status = "active"
    await session.flush()
    return duel


async def finish_duel(
    session: AsyncSession,
    duel_id: int,
    challenger_score: int,
    opponent_score: int,
    elo_delta: Optional[int] = None,
) -> Duel:
    duel = await get_duel(session, duel_id)
    duel.challenger_score = challenger_score
    duel.opponent_score = opponent_score
    duel.finished_at = datetime.now(timezone.utc)
    duel.status = "finished"
    duel.elo_delta = elo_delta

    if challenger_score > opponent_score:
        duel.winner_id = duel.challenger_id
    elif opponent_score > challenger_score:
        duel.winner_id = duel.opponent_id

    await session.flush()
    return duel


async def get_leaderboard(
    session: AsyncSession,
    period: str,
    period_start: date,
    limit: int = 50,
) -> list[LeaderboardEntry]:
    result = await session.execute(
        select(LeaderboardEntry)
        .where(
            LeaderboardEntry.period == period,
            LeaderboardEntry.period_start == period_start,
        )
        .order_by(LeaderboardEntry.rank)
        .limit(limit)
    )
    return list(result.scalars())


async def upsert_leaderboard_entry(
    session: AsyncSession,
    period: str,
    period_start: date,
    user_id: int,
    rank: int,
    score: int,
    xp_gained: int,
    quests_done: int,
) -> None:
    stmt = (
        insert(LeaderboardEntry)
        .values(
            period=period,
            period_start=period_start,
            user_id=user_id,
            rank=rank,
            score=score,
            xp_gained=xp_gained,
            quests_done=quests_done,
        )
        .on_conflict_do_update(
            constraint="uq_leaderboard_user_period",
            set_={"rank": rank, "score": score, "xp_gained": xp_gained, "quests_done": quests_done},
        )
    )
    await session.execute(stmt)


async def follow(
    session: AsyncSession, follower_id: int, followed_id: int
) -> Optional[Follow]:
    existing = await session.execute(
        select(Follow).where(
            Follow.follower_id == follower_id,
            Follow.followed_id == followed_id,
        )
    )
    if existing.scalar_one_or_none():
        return None

    f = Follow(follower_id=follower_id, followed_id=followed_id)
    session.add(f)
    await session.flush()
    return f


async def unfollow(
    session: AsyncSession, follower_id: int, followed_id: int
) -> None:
    await session.execute(
        delete(Follow).where(
            Follow.follower_id == follower_id,
            Follow.followed_id == followed_id,
        )
    )


async def get_followers(
    session: AsyncSession, user_id: int
) -> list[Follow]:
    result = await session.execute(
        select(Follow).where(Follow.followed_id == user_id)
    )
    return list(result.scalars())


async def get_following(
    session: AsyncSession, user_id: int
) -> list[Follow]:
    result = await session.execute(
        select(Follow).where(Follow.follower_id == user_id)
    )
    return list(result.scalars())
