from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AiEvaluation


async def save_evaluation(
    session: AsyncSession,
    user_id: int,
    quest_id: int,
    attempt_num: int,
    user_input: str,
    ai_output: str,
    score: int,
    feedback: str,
    criteria_scores: list[dict[str, Any]],
    model_used: str,
    tokens_used: Optional[int] = None,
) -> AiEvaluation:
    evaluation = AiEvaluation(
        user_id=user_id,
        quest_id=quest_id,
        attempt_num=attempt_num,
        user_input=user_input,
        ai_output=ai_output,
        score=score,
        feedback=feedback,
        criteria_scores=criteria_scores,
        model_used=model_used,
        tokens_used=tokens_used,
    )
    session.add(evaluation)
    await session.flush()
    return evaluation


async def get_evaluation(
    session: AsyncSession, eval_id: int
) -> Optional[AiEvaluation]:
    result = await session.execute(
        select(AiEvaluation).where(AiEvaluation.id == eval_id)
    )
    return result.scalar_one_or_none()


async def get_user_quest_evaluations(
    session: AsyncSession, user_id: int, quest_id: int
) -> list[AiEvaluation]:
    result = await session.execute(
        select(AiEvaluation)
        .where(AiEvaluation.user_id == user_id, AiEvaluation.quest_id == quest_id)
        .order_by(AiEvaluation.attempt_num)
    )
    return list(result.scalars())


async def get_attempt_count(
    session: AsyncSession, user_id: int, quest_id: int
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(AiEvaluation)
        .where(AiEvaluation.user_id == user_id, AiEvaluation.quest_id == quest_id)
    )
    return result.scalar_one()


async def get_best_score(
    session: AsyncSession, user_id: int, quest_id: int
) -> Optional[int]:
    result = await session.execute(
        select(func.max(AiEvaluation.score))
        .where(AiEvaluation.user_id == user_id, AiEvaluation.quest_id == quest_id)
    )
    return result.scalar_one_or_none()
