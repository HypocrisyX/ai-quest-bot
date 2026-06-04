"""Unit tests for judge.py — all Claude API calls are mocked."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.judge import _compute_weighted_score, evaluate_answer
from app.schemas import CriterionIn

# ── _compute_weighted_score ───────────────────────────────────────────────────

def test_weighted_score_equal_weights():
    criteria = [CriterionIn(criterion="A", weight=1), CriterionIn(criterion="B", weight=1)]
    scores = [{"criterion": "A", "score": 80}, {"criterion": "B", "score": 60}]
    assert _compute_weighted_score(criteria, scores) == 70


def test_weighted_score_unequal_weights():
    criteria = [CriterionIn(criterion="A", weight=3), CriterionIn(criterion="B", weight=1)]
    scores = [{"criterion": "A", "score": 100}, {"criterion": "B", "score": 0}]
    # (100*3 + 0*1) / 4 = 75
    assert _compute_weighted_score(criteria, scores) == 75


def test_weighted_score_perfect():
    criteria = [CriterionIn(criterion="A", weight=2)]
    scores = [{"criterion": "A", "score": 100}]
    assert _compute_weighted_score(criteria, scores) == 100


def test_weighted_score_zero():
    criteria = [CriterionIn(criterion="A", weight=1)]
    scores = [{"criterion": "A", "score": 0}]
    assert _compute_weighted_score(criteria, scores) == 0


def test_weighted_score_unknown_criterion_defaults_weight_1():
    """Score for unknown criterion uses weight=1 as fallback."""
    criteria = [CriterionIn(criterion="Known", weight=2)]
    scores = [
        {"criterion": "Known", "score": 80},
        {"criterion": "Unknown", "score": 60},
    ]
    # (80*2 + 60*1) / 3 = 73.3 → round to 73
    result = _compute_weighted_score(criteria, scores)
    assert result == round((80 * 2 + 60 * 1) / 3)


# ── evaluate_answer ───────────────────────────────────────────────────────────

def _make_claude_response(score: int, feedback: str, criteria_scores: list[dict]) -> MagicMock:
    payload = json.dumps({
        "criteria_scores": criteria_scores,
        "overall_feedback": feedback,
        "overall_score": score,
    })
    content = MagicMock()
    content.text = payload

    usage = MagicMock()
    usage.input_tokens = 500
    usage.output_tokens = 150

    response = MagicMock()
    response.content = [content]
    response.usage = usage
    return response


CRITERIA = [
    CriterionIn(criterion="Clarity", weight=2),
    CriterionIn(criterion="Correctness", weight=3),
]

CRITERIA_SCORES = [
    {"criterion": "Clarity", "score": 80, "comment": "Clear explanation"},
    {"criterion": "Correctness", "score": 90, "comment": "Accurate answer"},
]


async def test_evaluate_answer_returns_correct_score():
    mock_response = _make_claude_response(
        score=86,
        feedback="Well done!",
        criteria_scores=CRITERIA_SCORES,
    )

    with patch("app.judge.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        ai_output, score, feedback, crit_scores, tokens = await evaluate_answer(
            quest_title="Test Quest",
            quest_instructions="Do something useful.",
            criteria=CRITERIA,
            user_input="My answer here.",
        )

    # Weighted: (80*2 + 90*3) / 5 = (160 + 270) / 5 = 86
    assert score == 86
    assert feedback == "Well done!"
    assert len(crit_scores) == 2
    assert tokens == 650  # 500 input + 150 output


async def test_evaluate_answer_calls_claude_once():
    mock_response = _make_claude_response(
        score=70,
        feedback="OK",
        criteria_scores=[{"criterion": "Clarity", "score": 70, "comment": "OK"}],
    )

    with patch("app.judge.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        await evaluate_answer(
            quest_title="Q",
            quest_instructions="Do X.",
            criteria=[CriterionIn(criterion="Clarity", weight=1)],
            user_input="Answer.",
        )

        mock_client.messages.create.assert_called_once()


async def test_evaluate_answer_passes_cache_control():
    """System prompt must use cache_control=ephemeral for cost efficiency."""
    mock_response = _make_claude_response(
        score=75,
        feedback="Good",
        criteria_scores=[{"criterion": "A", "score": 75, "comment": "Fine"}],
    )

    with patch("app.judge.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        await evaluate_answer(
            quest_title="Q",
            quest_instructions="Do X.",
            criteria=[CriterionIn(criterion="A", weight=1)],
            user_input="Answer.",
        )

        call_kwargs = mock_client.messages.create.call_args
        # System is passed as a list with cache_control
        system_arg = call_kwargs.kwargs["system"]
        assert isinstance(system_arg, list)
        assert system_arg[0]["cache_control"]["type"] == "ephemeral"


# ── router integration (mocked Claude) ───────────────────────────────────────

async def test_evaluate_endpoint(client):
    mock_response = _make_claude_response(
        score=80,
        feedback="Хороший ответ!",
        criteria_scores=[
            {"criterion": "Правильность", "score": 80, "comment": "Верно"},
        ],
    )

    with patch("app.judge.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        r = await client.post("/evaluate", json={
            "user_id": 1,
            "quest_id": 1,
            "attempt_num": 1,
            "user_input": "Промпт — это инструкция для AI.",
            "quest_title": "Что такое промпт?",
            "quest_instructions": "Объясни своими словами.",
            "criteria": [{"criterion": "Правильность", "weight": 1}],
        })

    assert r.status_code == 201
    data = r.json()
    assert data["score"] == 80
    assert data["feedback"] == "Хороший ответ!"
    assert len(data["criteria_scores"]) == 1


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
