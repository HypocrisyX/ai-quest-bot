"""Tests for social-service repository — duels, leaderboard, follows."""
from datetime import date, datetime, timedelta, timezone

from app import repository as repo

# ── duels: create / fetch ─────────────────────────────────────────────────────

async def _make_duel(db, challenger_id=1, quest_id=10, score=100):
    return await repo.create_duel(
        db, challenger_id=challenger_id, quest_id=quest_id,
        challenger_score=score, challenger_answer="ans",
    )


async def test_create_duel_pending_with_code(db):
    duel = await _make_duel(db)
    assert duel.status == "pending"
    assert duel.code and len(duel.code) == 8
    assert duel.opponent_id is None


async def test_get_duel_by_code(db):
    duel = await _make_duel(db)
    found = await repo.get_duel_by_code(db, duel.code)
    assert found is not None and found.id == duel.id
    assert await repo.get_duel_by_code(db, "nope") is None


# ── duels: resolution ─────────────────────────────────────────────────────────

async def test_accept_challenger_wins(db):
    duel = await _make_duel(db, challenger_id=1, score=100)
    resolved, err = await repo.accept_and_resolve(db, duel.code, 2, 50, "b")
    assert err is None
    assert resolved.status == "finished"
    assert resolved.winner_id == 1


async def test_accept_opponent_wins(db):
    duel = await _make_duel(db, challenger_id=1, score=40)
    resolved, err = await repo.accept_and_resolve(db, duel.code, 2, 90, "b")
    assert err is None
    assert resolved.winner_id == 2


async def test_accept_tie(db):
    duel = await _make_duel(db, challenger_id=1, score=70)
    resolved, err = await repo.accept_and_resolve(db, duel.code, 2, 70, "b")
    assert err is None
    assert resolved.winner_id is None  # tie


async def test_accept_self_rejected(db):
    duel = await _make_duel(db, challenger_id=1)
    resolved, err = await repo.accept_and_resolve(db, duel.code, 1, 50, "b")
    assert resolved is None
    assert "собствен" in err


async def test_accept_not_found(db):
    resolved, err = await repo.accept_and_resolve(db, "missing", 2, 50, "b")
    assert resolved is None
    assert err == "Дуэль не найдена"


async def test_accept_already_played(db):
    duel = await _make_duel(db, challenger_id=1)
    await repo.accept_and_resolve(db, duel.code, 2, 50, "b")
    resolved, err = await repo.accept_and_resolve(db, duel.code, 3, 80, "c")
    assert resolved is None
    assert "сыграна" in err


async def test_accept_expired(db):
    duel = await _make_duel(db, challenger_id=1)
    # Age it past the TTL.
    duel.created_at = datetime.now(timezone.utc) - (repo.DUEL_TTL + timedelta(hours=1))
    await db.flush()
    resolved, err = await repo.accept_and_resolve(db, duel.code, 2, 50, "b")
    assert resolved is None
    assert "истекла" in err


# ── leaderboard ───────────────────────────────────────────────────────────────

async def _lb(db, day, user_id, rank, score):
    await repo.upsert_leaderboard_entry(
        db, "week", day, user_id=user_id, rank=rank,
        score=score, xp_gained=score, quests_done=1,
    )


async def test_leaderboard_upsert_and_order(db):
    today = date.today()
    await _lb(db, today, user_id=1, rank=2, score=50)
    await _lb(db, today, user_id=2, rank=1, score=90)
    board = await repo.get_leaderboard(db, "week", today)
    assert [e.rank for e in board] == [1, 2]
    assert board[0].user_id == 2


async def test_leaderboard_upsert_updates_existing(db):
    today = date.today()
    await _lb(db, today, user_id=1, rank=5, score=10)
    await _lb(db, today, user_id=1, rank=1, score=99)
    board = await repo.get_leaderboard(db, "week", today)
    assert len(board) == 1  # same user/period → updated, not duplicated
    assert board[0].rank == 1
    assert board[0].score == 99


# ── follows ───────────────────────────────────────────────────────────────────

async def test_follow_and_lists(db):
    await repo.follow(db, follower_id=1, followed_id=2)
    followers = await repo.get_followers(db, 2)
    following = await repo.get_following(db, 1)
    assert [f.follower_id for f in followers] == [1]
    assert [f.followed_id for f in following] == [2]


async def test_follow_duplicate_returns_none(db):
    await repo.follow(db, 1, 2)
    again = await repo.follow(db, 1, 2)
    assert again is None


async def test_unfollow(db):
    await repo.follow(db, 1, 2)
    await repo.unfollow(db, 1, 2)
    assert await repo.get_followers(db, 2) == []
