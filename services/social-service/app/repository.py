import secrets
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Duel, Follow, LeaderboardEntry


async def admin_stats(session: AsyncSession) -> dict:
    total = await session.scalar(select(func.count()).select_from(Duel))
    finished = await session.scalar(
        select(func.count()).select_from(Duel).where(Duel.status == "finished")
    )
    return {"total_duels": total or 0, "finished_duels": finished or 0}


def _gen_code() -> str:
    return secrets.token_hex(4)  # 8 hex chars


async def create_duel(
    session: AsyncSession,
    challenger_id: int,
    quest_id: int,
    challenger_score: int,
    challenger_answer: str,
) -> Duel:
    """Create a pending duel with the challenger's answer already submitted."""
    duel = Duel(
        code=_gen_code(),
        challenger_id=challenger_id,
        quest_id=quest_id,
        status="pending",
        challenger_score=challenger_score,
        challenger_answer=challenger_answer,
    )
    session.add(duel)
    await session.flush()
    return duel


async def get_duel(session: AsyncSession, duel_id: int) -> Optional[Duel]:
    result = await session.execute(select(Duel).where(Duel.id == duel_id))
    return result.scalar_one_or_none()


async def get_duel_by_code(session: AsyncSession, code: str) -> Optional[Duel]:
    result = await session.execute(select(Duel).where(Duel.code == code))
    return result.scalar_one_or_none()


async def accept_and_resolve(
    session: AsyncSession,
    code: str,
    opponent_id: int,
    opponent_score: int,
    opponent_answer: str,
) -> tuple[Optional[Duel], Optional[str]]:
    """Opponent submits their answer; the duel resolves immediately.

    Returns (duel, error). error is a human-readable reason when resolution
    can't proceed (not found / already taken / self-challenge).
    """
    duel = await get_duel_by_code(session, code)
    if duel is None:
        return None, "Дуэль не найдена"
    if duel.status != "pending":
        return None, "Эта дуэль уже сыграна"
    if duel.challenger_id == opponent_id:
        return None, "Нельзя принять собственный вызов"

    duel.opponent_id = opponent_id
    duel.opponent_score = opponent_score
    duel.opponent_answer = opponent_answer
    duel.status = "finished"
    duel.finished_at = datetime.now(timezone.utc)

    if duel.challenger_score > opponent_score:
        duel.winner_id = duel.challenger_id
    elif opponent_score > duel.challenger_score:
        duel.winner_id = duel.opponent_id
    else:
        duel.winner_id = None  # tie

    await session.flush()
    return duel, None


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
