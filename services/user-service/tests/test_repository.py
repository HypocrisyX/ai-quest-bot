"""Tests for user-service business logic in repository.py."""
from datetime import date, timedelta

from app import repository as repo
from app.schemas import UserCreate

# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_data(telegram_id: int = 100) -> UserCreate:
    return UserCreate(id=telegram_id, first_name="Test", username="tester")


async def _make_user(db, telegram_id: int = 100):
    user, _ = await repo.get_or_create_user(db, _user_data(telegram_id))
    return user


# ── get_or_create_user ────────────────────────────────────────────────────────

async def test_create_user_new(db):
    user, created = await repo.get_or_create_user(db, _user_data(1))
    assert created is True
    assert user.id == 1
    assert user.first_name == "Test"


async def test_create_user_idempotent(db):
    await repo.get_or_create_user(db, _user_data(2))
    user, created = await repo.get_or_create_user(db, _user_data(2))
    assert created is False
    assert user.id == 2


async def test_create_user_creates_stats(db):
    user, _ = await repo.get_or_create_user(db, _user_data(3))
    stats = await repo.get_user_stats(db, user.id)
    assert stats is not None
    assert stats.level == 1
    assert stats.xp == 0
    assert stats.crystals == 0


# ── add_xp ────────────────────────────────────────────────────────────────────

async def test_add_xp_no_levelup(db):
    await _make_user(db, 10)
    result = await repo.add_xp(db, 10, 50, "quest_complete")
    assert result.xp_after == 50
    assert result.level_before == 1
    assert result.level_after == 1
    assert result.leveled_up is False


async def test_add_xp_exact_levelup(db):
    """1100 XP at level 1 (xp_to_next=1100) triggers exactly one level-up."""
    await _make_user(db, 11)
    result = await repo.add_xp(db, 11, 1100, "quest_complete")
    assert result.leveled_up is True
    assert result.level_after == 2
    assert result.xp_after == 0  # consumed exactly


async def test_add_xp_overflow_levelup(db):
    """1150 XP at level 1 → level-up with 50 XP carried over."""
    await _make_user(db, 12)
    result = await repo.add_xp(db, 12, 1150, "quest_complete")
    assert result.leveled_up is True
    assert result.level_after == 2
    assert result.xp_after == 50


async def test_add_xp_multiple_levelups(db):
    """Enough XP to skip two levels at once."""
    await _make_user(db, 13)
    # Level 1 needs 1100, level 2 needs 500 → 1600+ XP triggers 2 level-ups
    result = await repo.add_xp(db, 13, 1700, "quest_complete")
    assert result.level_after >= 3


async def test_add_xp_persisted(db):
    await _make_user(db, 14)
    await repo.add_xp(db, 14, 30, "quest_complete")
    stats = await repo.get_user_stats(db, 14)
    assert stats.xp == 30


# ── add_crystals ──────────────────────────────────────────────────────────────

async def test_add_crystals_positive(db):
    await _make_user(db, 20)
    result = await repo.add_crystals(db, 20, 50, "reward")
    assert result.balance_before == 0
    assert result.balance_after == 50


async def test_add_crystals_subtract(db):
    await _make_user(db, 21)
    await repo.add_crystals(db, 21, 100, "reward")
    result = await repo.add_crystals(db, 21, -30, "hint")
    assert result.balance_after == 70


async def test_add_crystals_floor_zero(db):
    """Balance cannot go below 0 even with large negative delta."""
    await _make_user(db, 22)
    result = await repo.add_crystals(db, 22, -999, "hint")
    assert result.balance_after == 0


# ── leaderboard ───────────────────────────────────────────────────────────────

async def test_leaderboard_xp_ranks_by_level_then_xp(db):
    await _make_user(db, 90)
    await _make_user(db, 91)
    await _make_user(db, 92)
    # 90: level 2; 91: level 1 + 200xp; 92: level 1 + 50xp
    (await repo.get_user_stats(db, 90)).level = 2
    s91 = await repo.get_user_stats(db, 91)
    s91.xp = 200
    s92 = await repo.get_user_stats(db, 92)
    s92.xp = 50
    await db.flush()

    board = await repo.leaderboard(db, "xp", limit=10)
    ranked_ids = [e["user_id"] for e in board]
    assert ranked_ids[:3] == [90, 91, 92]
    assert board[0]["rank"] == 1


async def test_leaderboard_elo_orders_desc(db):
    await _make_user(db, 93)
    await _make_user(db, 94)
    (await repo.get_user_stats(db, 93)).elo_rating = 1200
    (await repo.get_user_stats(db, 94)).elo_rating = 900
    await db.flush()

    board = await repo.leaderboard(db, "elo", limit=10)
    assert board[0]["user_id"] == 93
    assert board[0]["elo_rating"] == 1200


async def test_user_rank_reflects_position(db):
    await _make_user(db, 95)
    await _make_user(db, 96)
    (await repo.get_user_stats(db, 95)).level = 5
    await db.flush()

    top = await repo.user_rank(db, 95, "xp")
    lower = await repo.user_rank(db, 96, "xp")
    assert top["rank"] == 1
    assert lower["rank"] == 2


async def test_user_rank_missing_user(db):
    assert await repo.user_rank(db, 999999, "xp") is None


# ── marketplace settle ────────────────────────────────────────────────────────

async def test_marketplace_settle_moves_crystals_minus_commission(db):
    await _make_user(db, 200)  # seller
    await _make_user(db, 201)  # buyer
    await repo.add_crystals(db, 201, 100, "test")
    result = await repo.marketplace_settle(db, buyer_id=201, seller_id=200, price=100)
    assert result["ok"] is True
    # 10% commission → seller gets 90
    assert result["seller_earned"] == 90
    assert result["commission"] == 10
    assert (await repo.get_user_stats(db, 201)).crystals == 0
    assert (await repo.get_user_stats(db, 200)).crystals == 90


async def test_marketplace_settle_insufficient(db):
    await _make_user(db, 202)
    await _make_user(db, 203)
    result = await repo.marketplace_settle(db, buyer_id=203, seller_id=202, price=100)
    assert result["ok"] is False
    assert result["reason"] == "insufficient"


async def test_marketplace_settle_self_rejected(db):
    await _make_user(db, 204)
    await repo.add_crystals(db, 204, 100, "test")
    result = await repo.marketplace_settle(db, buyer_id=204, seller_id=204, price=50)
    assert result["ok"] is False
    assert result["reason"] == "self"


# ── duels (ELO + rewards) ─────────────────────────────────────────────────────

async def test_duel_tie_equal_ratings_no_elo_change(db):
    await _make_user(db, 80)
    await _make_user(db, 81)
    result = await repo.apply_duel_result(db, 80, 81, winner_id=None)
    assert result["challenger"]["elo_delta"] == 0
    assert result["opponent"]["elo_delta"] == 0
    assert result["challenger"]["crystals"] == repo.DUEL_CRYSTALS_TIE
    assert result["opponent"]["crystals"] == repo.DUEL_CRYSTALS_TIE


async def test_duel_win_is_zero_sum(db):
    await _make_user(db, 82)
    await _make_user(db, 83)
    result = await repo.apply_duel_result(db, 82, 83, winner_id=82)
    # Equal starting ratings → winner +16, loser -16 with K=32
    assert result["challenger"]["elo_delta"] == 16
    assert result["opponent"]["elo_delta"] == -16
    assert result["challenger"]["crystals"] == repo.DUEL_CRYSTALS_WIN
    assert result["opponent"]["crystals"] == 0


async def test_duel_winner_gains_loser_loses_rating(db):
    await _make_user(db, 84)
    await _make_user(db, 85)
    await repo.apply_duel_result(db, 84, 85, winner_id=85)  # opponent wins
    ch = await repo.get_user_stats(db, 84)
    op = await repo.get_user_stats(db, 85)
    assert op.elo_rating > 1000
    assert ch.elo_rating < 1000


async def test_duel_elo_floor(db):
    await _make_user(db, 86)
    await _make_user(db, 87)
    stats = await repo.get_user_stats(db, 86)
    stats.elo_rating = repo.ELO_MIN  # already at floor
    await db.flush()
    await repo.apply_duel_result(db, 86, 87, winner_id=87)  # challenger loses
    ch = await repo.get_user_stats(db, 86)
    assert ch.elo_rating >= repo.ELO_MIN


# ── shop + xp boost ───────────────────────────────────────────────────────────

async def test_purchase_xp_boost_grants_charges(db):
    await _make_user(db, 60)
    await repo.add_crystals(db, 60, 100, "test")
    ok, _, crystals_after = await repo.purchase_item(db, 60, "xp_boost")
    assert ok is True
    assert crystals_after == 50  # 100 - 50 cost
    stats = await repo.get_user_stats(db, 60)
    assert stats.xp_boost_quests == repo.XP_BOOST_QUESTS


async def test_purchase_insufficient_crystals(db):
    await _make_user(db, 61)
    ok, msg, _ = await repo.purchase_item(db, 61, "xp_boost")
    assert ok is False
    assert "едостаточно" in msg


async def test_purchase_unavailable_item(db):
    await _make_user(db, 62)
    await repo.add_crystals(db, 62, 500, "test")
    ok, _, _ = await repo.purchase_item(db, 62, "streak_freeze")
    assert ok is False


async def test_xp_boost_doubles_quest_xp(db):
    await _make_user(db, 63)
    await repo.add_crystals(db, 63, 100, "test")
    await repo.purchase_item(db, 63, "xp_boost")

    result = await repo.add_xp(db, 63, 50, "quest_complete")
    assert result.xp_after == 100  # 50 doubled

    stats = await repo.get_user_stats(db, 63)
    assert stats.xp_boost_quests == repo.XP_BOOST_QUESTS - 1


async def test_xp_boost_not_applied_to_non_quest(db):
    await _make_user(db, 64)
    await repo.add_crystals(db, 64, 100, "test")
    await repo.purchase_item(db, 64, "xp_boost")

    # Non-quest reason should not consume or apply the boost.
    result = await repo.add_xp(db, 64, 50, "referral")
    assert result.xp_after == 50
    stats = await repo.get_user_stats(db, 64)
    assert stats.xp_boost_quests == repo.XP_BOOST_QUESTS


# ── achievements ──────────────────────────────────────────────────────────────

async def _seed_achievement(db, code, xp=0, crystals=0):
    from app.models import Achievement
    ach = Achievement(
        code=code, title=code, description="", icon="🏅",
        xp_reward=xp, crystal_reward=crystals,
    )
    db.add(ach)
    await db.flush()
    return ach


async def test_achievement_first_quest_granted(db):
    await _make_user(db, 70)
    await _seed_achievement(db, "first_quest", xp=20, crystals=5)
    await repo.add_xp(db, 70, 50, "quest_complete")  # total_quests → 1

    granted = await repo.check_and_grant_achievements(db, 70)
    codes = [g["code"] for g in granted]
    assert "first_quest" in codes
    # Reward applied
    stats = await repo.get_user_stats(db, 70)
    assert stats.crystals == 5


async def test_achievement_not_regranted(db):
    await _make_user(db, 71)
    await _seed_achievement(db, "first_quest", xp=20, crystals=5)
    await repo.add_xp(db, 71, 50, "quest_complete")

    first = await repo.check_and_grant_achievements(db, 71)
    second = await repo.check_and_grant_achievements(db, 71)
    assert len(first) == 1
    assert second == []  # idempotent


async def test_achievement_locked_until_condition_met(db):
    await _make_user(db, 72)
    await _seed_achievement(db, "quests_5")
    # Only 1 quest done → quests_5 (needs 5) should not unlock
    await repo.add_xp(db, 72, 50, "quest_complete")
    granted = await repo.check_and_grant_achievements(db, 72)
    assert "quests_5" not in [g["code"] for g in granted]


async def test_achievement_level_based(db):
    await _make_user(db, 73)
    await _seed_achievement(db, "level_2", crystals=10)
    await repo.add_xp(db, 73, 1100, "quest_complete")  # → level 2

    granted = await repo.check_and_grant_achievements(db, 73)
    assert "level_2" in [g["code"] for g in granted]


# ── update_streak ─────────────────────────────────────────────────────────────

async def test_streak_first_day(db):
    await _make_user(db, 30)
    streak = await repo.update_streak(db, 30)
    assert streak == 1


async def test_streak_continuation(db):
    await _make_user(db, 31)
    stats = await repo.get_user_stats(db, 31)
    stats.streak_last_at = date.today() - timedelta(days=1)
    stats.streak_days = 5
    await db.flush()
    streak = await repo.update_streak(db, 31)
    assert streak == 6


async def test_streak_reset_after_gap(db):
    await _make_user(db, 32)
    stats = await repo.get_user_stats(db, 32)
    stats.streak_last_at = date.today() - timedelta(days=3)
    stats.streak_days = 10
    await db.flush()
    streak = await repo.update_streak(db, 32)
    assert streak == 1


async def test_streak_same_day_idempotent(db):
    """Calling update_streak twice in one day should not increment."""
    await _make_user(db, 33)
    await repo.update_streak(db, 33)
    streak = await repo.update_streak(db, 33)
    assert streak == 1


# ── referrals ─────────────────────────────────────────────────────────────────

async def test_create_referral(db):
    await _make_user(db, 40)
    await _make_user(db, 41)
    referral = await repo.create_referral(db, referrer_id=40, referee_id=41)
    assert referral is not None
    assert referral.referrer_id == 40
    assert referral.referee_id == 41
    assert referral.reward_granted is False


async def test_create_referral_duplicate_returns_none(db):
    await _make_user(db, 42)
    await _make_user(db, 43)
    await repo.create_referral(db, referrer_id=42, referee_id=43)
    duplicate = await repo.create_referral(db, referrer_id=42, referee_id=43)
    assert duplicate is None


async def test_create_referral_one_referee_only(db):
    """A user can be referred only once, even by a different referrer."""
    await _make_user(db, 44)
    await _make_user(db, 45)
    await _make_user(db, 46)
    await repo.create_referral(db, referrer_id=44, referee_id=46)
    second = await repo.create_referral(db, referrer_id=45, referee_id=46)
    assert second is None


async def test_complete_referral_grants_both(db):
    await _make_user(db, 50)
    await _make_user(db, 51)
    result = await repo.complete_referral(db, referrer_id=50, referee_id=51)
    assert result["created"] is True
    assert result["bonus"] == repo.REFERRAL_BONUS
    assert (await repo.get_user_stats(db, 50)).crystals == repo.REFERRAL_BONUS
    assert (await repo.get_user_stats(db, 51)).crystals == repo.REFERRAL_BONUS


async def test_complete_referral_self_rejected(db):
    await _make_user(db, 52)
    result = await repo.complete_referral(db, referrer_id=52, referee_id=52)
    assert result["created"] is False
    assert result["reason"] == "self"


async def test_complete_referral_idempotent_no_double_grant(db):
    await _make_user(db, 53)
    await _make_user(db, 54)
    await repo.complete_referral(db, referrer_id=53, referee_id=54)
    second = await repo.complete_referral(db, referrer_id=53, referee_id=54)
    assert second["created"] is False
    assert second["reason"] == "exists"
    # Referrer keeps only the single bonus, no double credit.
    assert (await repo.get_user_stats(db, 53)).crystals == repo.REFERRAL_BONUS


async def test_referral_stats_counts(db):
    await _make_user(db, 55)
    await _make_user(db, 56)
    await _make_user(db, 57)
    await repo.complete_referral(db, referrer_id=55, referee_id=56)
    await repo.complete_referral(db, referrer_id=55, referee_id=57)
    stats = await repo.referral_stats(db, 55)
    assert stats["invited"] == 2
    assert stats["earned"] == 2 * repo.REFERRAL_BONUS
