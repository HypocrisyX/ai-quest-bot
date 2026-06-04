"""Tests for quest-service repository — core quest flow."""
import pytest

from app import repository as repo
from app.models import GameLevel, Quest, QuestCriterion, QuestHint


# ── Fixtures ──────────────────────────────────────────────────────────────────

async def _seed_level(db, level: int = 1) -> GameLevel:
    lvl = GameLevel(level=level, title=f"Level {level}", xp_required=level * 100)
    db.add(lvl)
    await db.flush()
    return lvl


async def _seed_quest(db, level_min: int = 1, is_active: bool = True) -> Quest:
    await _seed_level(db, level_min)
    quest = Quest(
        level_min=level_min,
        type="practice",
        title="Test Quest",
        instructions="Do something with AI.",
        xp_reward=100,
        order_index=1,
        is_active=is_active,
    )
    db.add(quest)
    await db.flush()
    return quest


# ── get_quest ─────────────────────────────────────────────────────────────────

async def test_get_quest_active(db):
    quest = await _seed_quest(db)
    found = await repo.get_quest(db, quest.id)
    assert found is not None
    assert found.id == quest.id


async def test_get_quest_inactive_not_found(db):
    quest = await _seed_quest(db, is_active=False)
    found = await repo.get_quest(db, quest.id)
    assert found is None


async def test_get_quest_missing(db):
    found = await repo.get_quest(db, 99999)
    assert found is None


# ── get_quests_for_level ──────────────────────────────────────────────────────

async def test_get_quests_for_level_returns_matching(db):
    await _seed_quest(db, level_min=1)
    quests = await repo.get_quests_for_level(db, user_level=1)
    assert len(quests) >= 1
    assert all(q.level_min <= 1 for q in quests)


async def test_get_quests_for_level_excludes_higher(db):
    await _seed_level(db, 3)
    high_quest = Quest(
        level_min=3, type="boss", title="Hard Quest",
        instructions="Hard", xp_reward=300, order_index=10, is_active=True,
    )
    db.add(high_quest)
    await db.flush()
    quests = await repo.get_quests_for_level(db, user_level=1)
    ids = [q.id for q in quests]
    assert high_quest.id not in ids


# ── start_quest / progress ────────────────────────────────────────────────────

async def test_start_quest_creates_progress(db):
    quest = await _seed_quest(db)
    progress = await repo.start_quest(db, user_id=100, quest_id=quest.id)
    assert progress.user_id == 100
    assert progress.quest_id == quest.id
    assert progress.status == "in_progress"
    assert progress.attempts == 1


async def test_start_quest_retry_increments_attempts(db):
    quest = await _seed_quest(db)
    await repo.start_quest(db, user_id=200, quest_id=quest.id)
    progress = await repo.start_quest(db, user_id=200, quest_id=quest.id)
    assert progress.attempts == 2
    assert progress.status == "in_progress"


# ── complete_quest ────────────────────────────────────────────────────────────

async def test_complete_quest(db):
    quest = await _seed_quest(db)
    await repo.start_quest(db, user_id=300, quest_id=quest.id)
    progress = await repo.complete_quest(db, user_id=300, quest_id=quest.id, score=85, xp_earned=100)
    assert progress.status == "completed"
    assert progress.best_score == 85
    assert progress.xp_earned == 100
    assert progress.completed_at is not None


async def test_complete_quest_updates_best_score(db):
    quest = await _seed_quest(db)
    await repo.start_quest(db, user_id=400, quest_id=quest.id)
    await repo.complete_quest(db, user_id=400, quest_id=quest.id, score=60, xp_earned=80)
    # Retry with better score
    await repo.start_quest(db, user_id=400, quest_id=quest.id)
    progress = await repo.complete_quest(db, user_id=400, quest_id=quest.id, score=90, xp_earned=100)
    assert progress.best_score == 90


async def test_complete_quest_keeps_best_score_on_worse_attempt(db):
    quest = await _seed_quest(db)
    await repo.start_quest(db, user_id=500, quest_id=quest.id)
    await repo.complete_quest(db, user_id=500, quest_id=quest.id, score=90, xp_earned=100)
    await repo.start_quest(db, user_id=500, quest_id=quest.id)
    progress = await repo.complete_quest(db, user_id=500, quest_id=quest.id, score=50, xp_earned=60)
    assert progress.best_score == 90  # kept the higher score


# ── fail_quest ────────────────────────────────────────────────────────────────

async def test_fail_quest(db):
    quest = await _seed_quest(db)
    await repo.start_quest(db, user_id=600, quest_id=quest.id)
    progress = await repo.fail_quest(db, user_id=600, quest_id=quest.id)
    assert progress.status == "failed"


# ── hints ─────────────────────────────────────────────────────────────────────

async def test_record_hint_used(db):
    quest = await _seed_quest(db)
    hint = QuestHint(quest_id=quest.id, order_index=1, cost=5, text="Hint text")
    db.add(hint)
    await db.flush()

    assert not await repo.is_hint_used(db, user_id=700, hint_id=hint.id)
    await repo.record_hint_used(db, user_id=700, hint_id=hint.id)
    assert await repo.is_hint_used(db, user_id=700, hint_id=hint.id)


async def test_record_hint_used_idempotent(db):
    quest = await _seed_quest(db)
    hint = QuestHint(quest_id=quest.id, order_index=1, cost=5, text="Hint text")
    db.add(hint)
    await db.flush()

    await repo.record_hint_used(db, user_id=800, hint_id=hint.id)
    await repo.record_hint_used(db, user_id=800, hint_id=hint.id)  # no error, no duplicate
    assert await repo.is_hint_used(db, user_id=800, hint_id=hint.id)


# ── get_quest_detail ──────────────────────────────────────────────────────────

async def test_get_quest_detail_with_criteria_and_hints(db):
    quest = await _seed_quest(db)
    db.add(QuestCriterion(quest_id=quest.id, criterion="Criterion 1", weight=2))
    db.add(QuestCriterion(quest_id=quest.id, criterion="Criterion 2", weight=1))
    db.add(QuestHint(quest_id=quest.id, order_index=1, cost=5, text="Hint 1"))
    await db.flush()

    detail = await repo.get_quest_detail(db, quest.id)
    assert detail is not None
    assert len(detail.criteria) == 2
    assert len(detail.hints) == 1
    assert detail.criteria[0].criterion == "Criterion 1"
