from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class GameLevelOut(BaseModel):
    level: int
    title: str
    xp_required: int
    description: Optional[str]
    requires_sub: bool
    reward_crystals: int

    model_config = {"from_attributes": True}


class QuestCriterionOut(BaseModel):
    id: int
    criterion: str
    weight: int
    description: Optional[str]

    model_config = {"from_attributes": True}


class QuestHintOut(BaseModel):
    id: int
    order_index: int
    cost: int

    model_config = {"from_attributes": True}


class QuestHintRevealOut(BaseModel):
    id: int
    order_index: int
    cost: int
    text: str

    model_config = {"from_attributes": True}


class QuestOut(BaseModel):
    id: int
    level_min: int
    level_max: Optional[int]
    type: str
    title: str
    description: Optional[str]
    instructions: str
    ai_tool: Optional[str]
    xp_reward: int
    crystal_reward: int
    time_limit_sec: Optional[int]

    model_config = {"from_attributes": True}


class QuestDetailOut(QuestOut):
    criteria: list[QuestCriterionOut]
    hints: list[QuestHintOut]


class QuestListItemOut(QuestOut):
    # "completed" — passed; "unlocked" — playable now; "locked" — previous not done
    status: str


class CategoryOut(BaseModel):
    key: str            # text / image / video
    title: str
    # unlocked | completed | locked (prev unfinished) | soon (no quests yet)
    status: str
    total: int
    completed: int


class QuestProgressOut(BaseModel):
    id: int
    user_id: int
    quest_id: int
    status: str
    attempts: int
    best_score: Optional[int]
    xp_earned: int
    started_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class StartQuestRequest(BaseModel):
    user_id: int
    quest_id: int


class CompleteQuestRequest(BaseModel):
    user_id: int
    quest_id: int
    score: int
    xp_earned: int


class UseHintRequest(BaseModel):
    user_id: int
    hint_id: int


class DailyQuestOut(BaseModel):
    id: int
    date: date
    quest_id: int
    level_min: int
    xp_bonus: int
    quest: QuestOut

    model_config = {"from_attributes": True}


class DailyCompletionOut(BaseModel):
    user_id: int
    daily_id: int
    completed_at: datetime

    model_config = {"from_attributes": True}
