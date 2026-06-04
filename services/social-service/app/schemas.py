from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class DuelCreate(BaseModel):
    challenger_id: int
    quest_id: int
    challenger_score: int
    challenger_answer: str


class DuelOut(BaseModel):
    id: int
    code: str
    challenger_id: int
    opponent_id: Optional[int]
    quest_id: int
    status: str
    challenger_score: Optional[int]
    opponent_score: Optional[int]
    winner_id: Optional[int]
    created_at: datetime
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DuelCreatedOut(BaseModel):
    id: int
    code: str
    quest_id: int


class DuelAcceptRequest(BaseModel):
    opponent_id: int
    opponent_score: int
    opponent_answer: str


class DuelResolutionOut(BaseModel):
    duel_id: int
    quest_id: int
    challenger_id: int
    opponent_id: int
    challenger_score: int
    opponent_score: int
    winner_id: Optional[int]   # None = tie
    is_tie: bool


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
