"""Tests for quest-service repository — core quest flow."""

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
    progress = await repo.complete_quest(
        db, user_id=300, quest_id=quest.id, score=85, xp_earned=100
    )
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
    progress = await repo.complete_quest(
        db, user_id=400, quest_id=quest.id, score=90, xp_earned=100
    )
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


# ── get_quests_with_status (sequential unlock) ────────────────────────────────

async def _seed_three_quests(db, category: str = "text") -> list[Quest]:
    await _seed_level(db, 1)
    quests = []
    for i in range(1, 4):
        q = Quest(
            level_min=1, type="practice", category=category, title=f"Quest {i}",
            instructions="Do it.", xp_reward=50, order_index=i, is_active=True,
        )
        db.add(q)
        quests.append(q)
    await db.flush()
    return quests


async def test_status_first_unlocked_rest_locked(db):
    await _seed_three_quests(db)
    items = await repo.get_quests_with_status(db, category="text", user_id=1)
    statuses = [it["status"] for it in items]
    assert statuses == ["unlocked", "locked", "locked"]


async def test_status_unlocks_next_after_completion(db):
    quests = await _seed_three_quests(db)
    await repo.start_quest(db, user_id=2, quest_id=quests[0].id)
    await repo.complete_quest(db, user_id=2, quest_id=quests[0].id, score=100, xp_earned=50)

    items = await repo.get_quests_with_status(db, category="text", user_id=2)
    statuses = [it["status"] for it in items]
    assert statuses == ["completed", "unlocked", "locked"]


async def test_status_all_completed(db):
    quests = await _seed_three_quests(db)
    for q in quests:
        await repo.start_quest(db, user_id=3, quest_id=q.id)
        await repo.complete_quest(db, user_id=3, quest_id=q.id, score=100, xp_earned=50)

    items = await repo.get_quests_with_status(db, category="text", user_id=3)
    statuses = [it["status"] for it in items]
    assert statuses == ["completed", "completed", "completed"]


# ── get_categories_with_status (sequential worlds) ────────────────────────────

async def test_categories_image_locked_until_text_done(db):
    await _seed_three_quests(db, category="text")
    img = Quest(
        level_min=1, type="practice", category="image", title="Img 1",
        instructions="Draw.", xp_reward=50, order_index=10, is_active=True,
    )
    db.add(img)
    await db.flush()

    cats = await repo.get_categories_with_status(db, user_id=50)
    by_key = {c["key"]: c for c in cats}
    assert by_key["text"]["status"] == "unlocked"
    assert by_key["image"]["status"] == "locked"
    assert by_key["video"]["status"] == "locked"


async def test_categories_image_unlocks_after_all_text_done(db):
    text_quests = await _seed_three_quests(db, category="text")
    img = Quest(
        level_min=1, type="practice", category="image", title="Img 1",
        instructions="Draw.", xp_reward=50, order_index=10, is_active=True,
    )
    db.add(img)
    await db.flush()

    for q in text_quests:
        await repo.start_quest(db, user_id=51, quest_id=q.id)
        await repo.complete_quest(db, user_id=51, quest_id=q.id, score=100, xp_earned=50)

    cats = await repo.get_categories_with_status(db, user_id=51)
    by_key = {c["key"]: c for c in cats}
    assert by_key["text"]["status"] == "completed"
    assert by_key["image"]["status"] == "unlocked"
    assert by_key["video"]["status"] == "locked"


async def test_categories_video_soon_when_empty_and_reachable(db):
    # No quests at all → text is empty/soon, nothing after unlocks.
    cats = await repo.get_categories_with_status(db, user_id=52)
    by_key = {c["key"]: c for c in cats}
    assert by_key["text"]["status"] == "soon"
    assert by_key["image"]["status"] == "locked"


# ── training progress ─────────────────────────────────────────────────────────

async def test_training_progress_incomplete(db):
    await _seed_three_quests(db, category="text")
    progress = await repo.training_progress(db, user_id=60)
    assert progress["total"] == 3
    assert progress["completed"] == 0
    assert progress["complete"] is False


async def test_training_progress_complete(db):
    quests = await _seed_three_quests(db, category="text")
    for q in quests:
        await repo.start_quest(db, user_id=61, quest_id=q.id)
        await repo.complete_quest(db, user_id=61, quest_id=q.id, score=100, xp_earned=50)
    progress = await repo.training_progress(db, user_id=61)
    assert progress["total"] == 3
    assert progress["completed"] == 3
    assert progress["complete"] is True


# ── skip_quest ────────────────────────────────────────────────────────────────

async def test_skip_quest_marks_completed_score_zero(db):
    quest = await _seed_quest(db)
    user_id = 55001
    result = await repo.skip_quest(db, user_id, quest.id)
    assert result is True
    progress = await repo.get_user_progress(db, user_id, quest.id)
    assert progress is not None
    assert progress.status == "completed"
    assert progress.best_score == 0
    assert progress.xp_earned == 0


async def test_skip_quest_idempotent(db):
    quest = await _seed_quest(db)
    user_id = 55002
    await repo.skip_quest(db, user_id, quest.id)
    result = await repo.skip_quest(db, user_id, quest.id)
    assert result is True


async def test_skip_quest_returns_false_for_missing_quest(db):
    result = await repo.skip_quest(db, 999, 99999)
    assert result is False
