import json
import os
from typing import Any

import anthropic

from .schemas import CriterionIn, CriterionScoreOut

MODEL = os.getenv("JUDGE_MODEL", "claude-sonnet-4-6")
_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


_SYSTEM = """\
Ты — строгий, но справедливый судья AI-квестов. Твоя задача — оценить ответ пользователя \
на задание по каждому критерию и дать развёрнутую обратную связь на русском языке.

Ответь ТОЛЬКО валидным JSON следующей структуры (без markdown-блоков):
{
  "criteria_scores": [
    {"criterion": "<текст критерия>", "score": <0-100>, "comment": "<комментарий>"},
    ...
  ],
  "overall_feedback": "<общий отзыв 2-4 предложения>",
  "overall_score": <0-100, взвешенное среднее>
}"""


def _build_user_message(
    quest_title: str,
    quest_instructions: str,
    criteria: list[CriterionIn],
    user_input: str,
) -> str:
    criteria_text = "\n".join(
        f"{i + 1}. [{c.weight}x] {c.criterion}"
        + (f"\n   Описание: {c.description}" if c.description else "")
        for i, c in enumerate(criteria)
    )
    return (
        f"## Задание: {quest_title}\n\n"
        f"**Инструкция:**\n{quest_instructions}\n\n"
        f"**Критерии оценки:**\n{criteria_text}\n\n"
        f"**Ответ пользователя:**\n{user_input}"
    )


def _compute_weighted_score(
    criteria: list[CriterionIn],
    scores: list[dict[str, Any]],
) -> int:
    weight_map = {c.criterion: c.weight for c in criteria}
    total_weight = sum(weight_map.get(s["criterion"], 1) for s in scores)
    if total_weight == 0:
        return 0
    weighted_sum = sum(
        s["score"] * weight_map.get(s["criterion"], 1) for s in scores
    )
    return round(weighted_sum / total_weight)


async def evaluate_answer(
    quest_title: str,
    quest_instructions: str,
    criteria: list[CriterionIn],
    user_input: str,
) -> tuple[str, int, str, list[CriterionScoreOut], int]:
    """Returns (ai_output, score, feedback, criteria_scores, tokens_used)."""
    client = get_client()

    response = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": _build_user_message(
                    quest_title, quest_instructions, criteria, user_input
                ),
            }
        ],
    )

    ai_output = response.content[0].text
    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    parsed = json.loads(ai_output)
    raw_scores: list[dict] = parsed["criteria_scores"]
    feedback: str = parsed["overall_feedback"]

    score = _compute_weighted_score(criteria, raw_scores)
    criteria_scores = [CriterionScoreOut(**s) for s in raw_scores]

    return ai_output, score, feedback, criteria_scores, tokens_used
