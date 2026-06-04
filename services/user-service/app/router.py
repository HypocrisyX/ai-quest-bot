from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from . import repository as repo
from .database import get_db
from .schemas import (
    AddCrystalsRequest,
    AddCrystalsResponse,
    AddXpRequest,
    AddXpResponse,
    DuelApplyRequest,
    DuelApplyResponse,
    EarnedAchievementOut,
    GrantedAchievementOut,
    PurchaseRequest,
    PurchaseResponse,
    ReferralCreate,
    ReferralOut,
    ShopItemOut,
    SubscriptionOut,
    UserCreate,
    UserOut,
    UserProfileOut,
    UserStatsOut,
)

router = APIRouter()
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/admin/stats")
async def admin_stats(db: DB):
    return await repo.admin_stats(db)


@router.get("/admin/users")
async def admin_users(db: DB, limit: int = 10, offset: int = 0):
    return await repo.admin_list_users(db, limit, offset)


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


@router.post("/duels/apply", response_model=DuelApplyResponse)
async def apply_duel(data: DuelApplyRequest, db: DB):
    result = await repo.apply_duel_result(
        db, data.challenger_id, data.opponent_id, data.winner_id
    )
    return DuelApplyResponse(**result)


@router.get("/users/{user_id}/shop", response_model=list[ShopItemOut])
async def get_shop(user_id: int, db: DB):
    stats = await repo.get_user_stats(db, user_id)
    if stats is None:
        raise HTTPException(404, "User not found")
    return repo.list_shop_items(stats.crystals)


@router.post("/users/{user_id}/shop/purchase", response_model=PurchaseResponse)
async def purchase(user_id: int, data: PurchaseRequest, db: DB):
    ok, message, crystals_after = await repo.purchase_item(db, user_id, data.item_key)
    return PurchaseResponse(ok=ok, message=message, crystals_after=crystals_after)


@router.get("/users/{user_id}/subscription", response_model=SubscriptionOut | None)
async def get_subscription(user_id: int, db: DB):
    return await repo.get_active_subscription(db, user_id)


@router.get("/users/{user_id}/achievements", response_model=list[EarnedAchievementOut])
async def get_achievements(user_id: int, db: DB):
    return await repo.get_user_achievements(db, user_id)


@router.post(
    "/users/{user_id}/achievements/check",
    response_model=list[GrantedAchievementOut],
)
async def check_achievements(user_id: int, db: DB):
    """Evaluate rules and grant any newly-earned achievements. Returns the new ones."""
    return await repo.check_and_grant_achievements(db, user_id)


@router.post("/users/{user_id}/achievements/{code}", status_code=201)
async def grant_achievement(user_id: int, code: str, db: DB):
    ach = await repo.grant_achievement(db, user_id, code)
    if not ach:
        raise HTTPException(409, "Already granted or achievement not found")
    return {"granted": True}


@router.post("/referrals", response_model=ReferralOut, status_code=201)
async def create_referral(data: ReferralCreate, db: DB):
    referral = await repo.create_referral(db, data.referrer_id, data.referee_id)
    if not referral:
        raise HTTPException(409, "Referral already exists")
    return referral
