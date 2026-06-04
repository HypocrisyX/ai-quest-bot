from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .schemas import (
    AddCrystalsRequest, AddCrystalsResponse,
    AddXpRequest, AddXpResponse,
    AchievementOut, ReferralCreate, ReferralOut,
    SubscriptionOut, UserCreate, UserOut, UserProfileOut, UserStatsOut,
)
from . import repository as repo

router = APIRouter()
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/users", response_model=UserOut, status_code=201)
async def register_user(data: UserCreate, db: DB):
    user, _ = await repo.get_or_create_user(db, data)
    await repo.update_last_active(db, user.id)
    return user


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: int, db: DB):
    user = await repo.get_user(db, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user


@router.get("/users/{user_id}/profile", response_model=UserProfileOut)
async def get_profile(user_id: int, db: DB):
    user = await repo.get_user(db, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    stats = await repo.get_user_stats(db, user_id)
    return UserProfileOut(
        user=UserOut.model_validate(user),
        stats=UserStatsOut.model_validate(stats),
    )


@router.post("/users/{user_id}/xp", response_model=AddXpResponse)
async def add_xp(user_id: int, data: AddXpRequest, db: DB):
    return await repo.add_xp(db, user_id, data.delta_xp, data.reason, data.ref_id)


@router.post("/users/{user_id}/crystals", response_model=AddCrystalsResponse)
async def add_crystals(user_id: int, data: AddCrystalsRequest, db: DB):
    return await repo.add_crystals(db, user_id, data.delta, data.reason, data.ref_id)


@router.post("/users/{user_id}/streak", response_model=dict)
async def update_streak(user_id: int, db: DB):
    streak = await repo.update_streak(db, user_id)
    return {"streak_days": streak}


@router.get("/users/{user_id}/subscription", response_model=SubscriptionOut | None)
async def get_subscription(user_id: int, db: DB):
    return await repo.get_active_subscription(db, user_id)


@router.get("/users/{user_id}/achievements", response_model=list[AchievementOut])
async def get_achievements(user_id: int, db: DB):
    await repo.get_user_achievements(db, user_id)
    return []


@router.post("/users/{user_id}/achievements/{code}", status_code=201)
async def grant_achievement(user_id: int, code: str, db: DB):
    ua = await repo.grant_achievement(db, user_id, code)
    if not ua:
        raise HTTPException(409, "Already granted or achievement not found")
    return {"granted": True}


@router.post("/referrals", response_model=ReferralOut, status_code=201)
async def create_referral(data: ReferralCreate, db: DB):
    referral = await repo.create_referral(db, data.referrer_id, data.referee_id)
    if not referral:
        raise HTTPException(409, "Referral already exists")
    return referral
