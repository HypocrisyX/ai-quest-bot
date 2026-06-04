from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from . import repository as repo
from .database import get_db
from .schemas import (
    CompleteQuestRequest,
    DailyQuestOut,
    QuestDetailOut,
    QuestHintRevealOut,
    QuestOut,
    QuestProgressOut,
    StartQuestRequest,
    UseHintRequest,
)

router = APIRouter()
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/quests", response_model=list[QuestOut])
async def list_quests(level: int = Query(..., ge=1), db: DB = None):
    return await repo.get_quests_for_level(db, level)


@router.get("/quests/{quest_id}", response_model=QuestDetailOut)
async def get_quest(quest_id: int, db: DB = None):
    detail = await repo.get_quest_detail(db, quest_id)
    if not detail:
        raise HTTPException(404, "Quest not found")
    return detail


@router.post("/quests/{quest_id}/start", response_model=QuestProgressOut, status_code=201)
async def start_quest(quest_id: int, data: StartQuestRequest, db: DB = None):
    quest = await repo.get_quest(db, quest_id)
    if not quest:
        raise HTTPException(404, "Quest not found")
    return await repo.start_quest(db, data.user_id, quest_id)


@router.post("/quests/{quest_id}/complete", response_model=QuestProgressOut)
async def complete_quest(quest_id: int, data: CompleteQuestRequest, db: DB = None):
    return await repo.complete_quest(db, data.user_id, quest_id, data.score, data.xp_earned)


@router.post("/quests/{quest_id}/fail", response_model=QuestProgressOut)
async def fail_quest(quest_id: int, data: StartQuestRequest, db: DB = None):
    return await repo.fail_quest(db, data.user_id, quest_id)


@router.get("/quests/{quest_id}/progress/{user_id}", response_model=QuestProgressOut | None)
async def get_progress(quest_id: int, user_id: int, db: DB = None):
    return await repo.get_user_progress(db, user_id, quest_id)


@router.post("/hints/{hint_id}/use", response_model=QuestHintRevealOut)
async def use_hint(hint_id: int, data: UseHintRequest, db: DB = None):
    hint = await repo.get_hint(db, hint_id)
    if not hint:
        raise HTTPException(404, "Hint not found")
    await repo.record_hint_used(db, data.user_id, hint_id)
    return QuestHintRevealOut.model_validate(hint)


@router.get("/daily", response_model=DailyQuestOut | None)
async def get_daily(
    user_level: int = Query(..., ge=1),
    for_date: date = Query(default_factory=date.today),
    db: DB = None,
):
    return await repo.get_daily_quest(db, for_date, user_level)


@router.post("/daily/{daily_id}/complete", status_code=201)
async def complete_daily(daily_id: int, user_id: int = Query(...), db: DB = None):
    if await repo.is_daily_completed(db, user_id, daily_id):
        raise HTTPException(409, "Already completed")
    await repo.complete_daily(db, user_id, daily_id)
    return {"completed": True}
