from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from . import repository as repo
from .database import get_db
from .schemas import (
    DuelCreate,
    DuelFinishRequest,
    DuelOut,
    FollowOut,
    FollowRequest,
    LeaderboardOut,
)

router = APIRouter()
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/duels", response_model=DuelOut, status_code=201)
async def create_duel(data: DuelCreate, db: DB):
    return await repo.create_duel(db, data.challenger_id, data.opponent_id, data.quest_id)


@router.get("/duels/{duel_id}", response_model=DuelOut)
async def get_duel(duel_id: int, db: DB):
    duel = await repo.get_duel(db, duel_id)
    if not duel:
        raise HTTPException(404, "Duel not found")
    return duel


@router.post("/duels/{duel_id}/accept", response_model=DuelOut)
async def accept_duel(duel_id: int, db: DB):
    duel = await repo.get_duel(db, duel_id)
    if not duel or duel.status != "pending":
        raise HTTPException(404, "Pending duel not found")
    return await repo.accept_duel(db, duel_id)


@router.post("/duels/{duel_id}/finish", response_model=DuelOut)
async def finish_duel(duel_id: int, data: DuelFinishRequest, db: DB):
    duel = await repo.get_duel(db, duel_id)
    if not duel or duel.status != "active":
        raise HTTPException(404, "Active duel not found")
    return await repo.finish_duel(db, duel_id, data.challenger_score, data.opponent_score)


@router.get("/leaderboard", response_model=LeaderboardOut)
async def get_leaderboard(
    period: str = Query("week", pattern="^(day|week|month|alltime)$"),
    period_start: date = Query(default_factory=date.today),
    limit: int = Query(50, le=200),
    db: DB = None,
):
    entries = await repo.get_leaderboard(db, period, period_start, limit)
    return LeaderboardOut(period=period, period_start=period_start, entries=entries)


@router.post("/follows", response_model=FollowOut, status_code=201)
async def follow_user(data: FollowRequest, db: DB):
    if data.follower_id == data.followed_id:
        raise HTTPException(400, "Cannot follow yourself")
    result = await repo.follow(db, data.follower_id, data.followed_id)
    if not result:
        raise HTTPException(409, "Already following")
    return result


@router.delete("/follows")
async def unfollow_user(data: FollowRequest, db: DB):
    await repo.unfollow(db, data.follower_id, data.followed_id)
    return {"unfollowed": True}


@router.get("/users/{user_id}/followers", response_model=list[FollowOut])
async def get_followers(user_id: int, db: DB):
    return await repo.get_followers(db, user_id)


@router.get("/users/{user_id}/following", response_model=list[FollowOut])
async def get_following(user_id: int, db: DB):
    return await repo.get_following(db, user_id)
