from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class DuelCreate(BaseModel):
    challenger_id: int
    opponent_id: int
    quest_id: int


class DuelOut(BaseModel):
    id: int
    challenger_id: int
    opponent_id: int
    quest_id: int
    status: str
    challenger_score: Optional[int]
    opponent_score: Optional[int]
    winner_id: Optional[int]
    elo_delta: Optional[int]
    created_at: datetime
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DuelFinishRequest(BaseModel):
    duel_id: int
    challenger_score: int
    opponent_score: int


class LeaderboardEntryOut(BaseModel):
    rank: int
    user_id: int
    score: int
    xp_gained: int
    quests_done: int

    model_config = {"from_attributes": True}


class LeaderboardOut(BaseModel):
    period: str
    period_start: date
    entries: list[LeaderboardEntryOut]


class FollowRequest(BaseModel):
    follower_id: int
    followed_id: int


class FollowOut(BaseModel):
    follower_id: int
    followed_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
