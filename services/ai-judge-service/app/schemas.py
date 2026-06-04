from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CriterionIn(BaseModel):
    criterion: str
    weight: int = 1
    description: Optional[str] = None


class EvaluateRequest(BaseModel):
    user_id: int
    quest_id: int
    attempt_num: int
    user_input: str
    quest_title: str
    quest_instructions: str
    criteria: list[CriterionIn]


class CriterionScoreOut(BaseModel):
    criterion: str
    score: int  # 0–100
    comment: str


class EvaluationOut(BaseModel):
    id: int
    user_id: int
    quest_id: int
    attempt_num: int
    score: int  # 0–100, weighted average
    feedback: str
    criteria_scores: list[CriterionScoreOut]
    model_used: str
    tokens_used: Optional[int]
    evaluated_at: datetime

    model_config = {"from_attributes": True}


class EvaluationSummaryOut(BaseModel):
    id: int
    quest_id: int
    score: int
    evaluated_at: datetime

    model_config = {"from_attributes": True}
