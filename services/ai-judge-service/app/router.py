from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from . import repository as repo
from .database import get_db
from .judge import evaluate_answer
from .schemas import EvaluateRequest, EvaluationOut, EvaluationSummaryOut

router = APIRouter()
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/evaluate", response_model=EvaluationOut, status_code=201)
async def evaluate(data: EvaluateRequest, db: DB):
    ai_output, score, feedback, criteria_scores, tokens_used = await evaluate_answer(
        quest_title=data.quest_title,
        quest_instructions=data.quest_instructions,
        criteria=data.criteria,
        user_input=data.user_input,
    )

    evaluation = await repo.save_evaluation(
        db,
        user_id=data.user_id,
        quest_id=data.quest_id,
        attempt_num=data.attempt_num,
        user_input=data.user_input,
        ai_output=ai_output,
        score=score,
        feedback=feedback,
        criteria_scores=[s.model_dump() for s in criteria_scores],
        model_used="claude-sonnet-4-6",
        tokens_used=tokens_used,
    )

    return EvaluationOut(
        id=evaluation.id,
        user_id=evaluation.user_id,
        quest_id=evaluation.quest_id,
        attempt_num=evaluation.attempt_num,
        score=score,
        feedback=feedback,
        criteria_scores=criteria_scores,
        model_used=evaluation.model_used,
        tokens_used=evaluation.tokens_used,
        evaluated_at=evaluation.evaluated_at,
    )


@router.get("/evaluations/{eval_id}", response_model=EvaluationOut)
async def get_evaluation(eval_id: int, db: DB):
    ev = await repo.get_evaluation(db, eval_id)
    if not ev:
        raise HTTPException(404, "Evaluation not found")
    return ev


@router.get(
    "/evaluations/user/{user_id}/quest/{quest_id}",
    response_model=list[EvaluationSummaryOut],
)
async def list_evaluations(user_id: int, quest_id: int, db: DB):
    return await repo.get_user_quest_evaluations(db, user_id, quest_id)


@router.get("/evaluations/user/{user_id}/quest/{quest_id}/attempts")
async def get_attempt_count(user_id: int, quest_id: int, db: DB):
    count = await repo.get_attempt_count(db, user_id, quest_id)
    best = await repo.get_best_score(db, user_id, quest_id)
    return {"attempts": count, "best_score": best}
