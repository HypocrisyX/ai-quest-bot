from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class UserCreate(BaseModel):
    id: int  # telegram_id
    username: Optional[str] = None
    first_name: str
    language_code: str = "ru"


class UserOut(BaseModel):
    id: int
    username: Optional[str]
    first_name: str
    language_code: str
    created_at: datetime
    last_active_at: datetime

    model_config = {"from_attributes": True}


class UserStatsOut(BaseModel):
    level: int
    xp: int
    xp_to_next: int
    crystals: int
    elo_rating: int
    streak_days: int
    streak_last_at: Optional[date]
    total_quests: int
    class_title: str

    model_config = {"from_attributes": True}


class UserProfileOut(BaseModel):
    user: UserOut
    stats: UserStatsOut


class SubscriptionOut(BaseModel):
    id: UUID
    user_id: int
    plan: str
    status: str
    started_at: datetime
    expires_at: datetime
    payment_ref: Optional[str]

    model_config = {"from_attributes": True}


class AchievementOut(BaseModel):
    id: int
    code: str
    title: str
    description: Optional[str]
    icon: Optional[str]
    xp_reward: int
    crystal_reward: int

    model_config = {"from_attributes": True}


class UserAchievementOut(BaseModel):
    achievement: AchievementOut
    earned_at: datetime


class AddXpRequest(BaseModel):
    user_id: int
    delta_xp: int
    reason: str
    ref_id: Optional[str] = None


class AddXpResponse(BaseModel):
    level_before: int
    level_after: int
    xp_before: int
    xp_after: int
    leveled_up: bool


class AddCrystalsRequest(BaseModel):
    user_id: int
    delta: int
    reason: str
    ref_id: Optional[str] = None


class AddCrystalsResponse(BaseModel):
    balance_before: int
    balance_after: int


class ReferralCreate(BaseModel):
    referrer_id: int
    referee_id: int


class ReferralOut(BaseModel):
    id: int
    referrer_id: int
    referee_id: int
    reward_granted: bool
    created_at: datetime

    model_config = {"from_attributes": True}
