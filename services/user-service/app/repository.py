from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Achievement,
    CrystalTransaction,
    Referral,
    Subscription,
    User,
    UserAchievement,
    UserStats,
    XpHistory,
)
from .schemas import (
    AddCrystalsResponse,
    AddXpResponse,
    UserCreate,
)


async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession, data: UserCreate
) -> tuple[User, bool]:
    user = await get_user(session, data.id)
    if user:
        return user, False

    user = User(
        id=data.id,
        username=data.username,
        first_name=data.first_name,
        language_code=data.language_code,
    )
    stats = UserStats(user_id=data.id)
    session.add(user)
    session.add(stats)
    await session.flush()
    return user, True


async def update_last_active(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(last_active_at=datetime.now(timezone.utc))
    )


async def get_user_stats(session: AsyncSession, user_id: int) -> Optional[UserStats]:
    result = await session.execute(
        select(UserStats).where(UserStats.user_id == user_id)
    )
    return result.scalar_one_or_none()


_LEVEL_XP = {1: 1100, 2: 500, 3: 800, 4: 1200, 5: 2000}


def _xp_to_next_level(level: int) -> int:
    return _LEVEL_XP.get(level, 300 * level)


async def add_xp(
    session: AsyncSession,
    user_id: int,
    delta_xp: int,
    reason: str,
    ref_id: Optional[str] = None,
) -> AddXpResponse:
    stats = await get_user_stats(session, user_id)
    level_before = stats.level
    xp_before = stats.xp

    # Apply an active 2x XP boost on quest completions, consuming one charge.
    if reason == "quest_complete" and (stats.xp_boost_quests or 0) > 0:
        delta_xp *= 2
        stats.xp_boost_quests -= 1

    stats.xp += delta_xp
    leveled_up = False

    while stats.xp >= stats.xp_to_next:
        stats.xp -= stats.xp_to_next
        stats.level += 1
        stats.xp_to_next = _xp_to_next_level(stats.level)
        leveled_up = True

    stats.total_quests = (stats.total_quests or 0) + (1 if reason == "quest_complete" else 0)

    session.add(
        XpHistory(
            user_id=user_id,
            delta_xp=delta_xp,
            reason=reason,
            ref_id=ref_id,
            level_after=stats.level,
        )
    )
    await session.flush()

    return AddXpResponse(
        level_before=level_before,
        level_after=stats.level,
        xp_before=xp_before,
        xp_after=stats.xp,
        leveled_up=leveled_up,
    )


async def add_crystals(
    session: AsyncSession,
    user_id: int,
    delta: int,
    reason: str,
    ref_id: Optional[str] = None,
) -> AddCrystalsResponse:
    stats = await get_user_stats(session, user_id)
    balance_before = stats.crystals
    stats.crystals = max(0, stats.crystals + delta)

    session.add(
        CrystalTransaction(
            user_id=user_id,
            delta=delta,
            reason=reason,
            ref_id=ref_id,
            balance=stats.crystals,
        )
    )
    await session.flush()

    return AddCrystalsResponse(
        balance_before=balance_before,
        balance_after=stats.crystals,
    )


# ── Duels (ELO + rewards) ─────────────────────────────────────────────────────

ELO_K = 32
ELO_MIN = 100
DUEL_CRYSTALS_WIN = 15
DUEL_CRYSTALS_TIE = 5


def _elo_delta(rating: int, opponent_rating: int, score: float) -> int:
    """Standard Elo delta. score: 1 win / 0.5 tie / 0 loss."""
    expected = 1 / (1 + 10 ** ((opponent_rating - rating) / 400))
    return round(ELO_K * (score - expected))


async def apply_duel_result(
    session: AsyncSession,
    challenger_id: int,
    opponent_id: int,
    winner_id: Optional[int],
) -> dict:
    """Update both players' ELO + crystals for a finished duel.

    winner_id None means a tie. Returns per-player deltas for display.
    """
    ch = await get_user_stats(session, challenger_id)
    op = await get_user_stats(session, opponent_id)

    if winner_id is None:
        ch_score, op_score = 0.5, 0.5
    elif winner_id == challenger_id:
        ch_score, op_score = 1.0, 0.0
    else:
        ch_score, op_score = 0.0, 1.0

    ch_elo = _elo_delta(ch.elo_rating, op.elo_rating, ch_score)
    op_elo = _elo_delta(op.elo_rating, ch.elo_rating, op_score)
    ch.elo_rating = max(ELO_MIN, ch.elo_rating + ch_elo)
    op.elo_rating = max(ELO_MIN, op.elo_rating + op_elo)

    def _reward(is_winner: bool, is_tie: bool) -> int:
        if is_tie:
            return DUEL_CRYSTALS_TIE
        return DUEL_CRYSTALS_WIN if is_winner else 0

    is_tie = winner_id is None
    ch_crystals = _reward(winner_id == challenger_id, is_tie)
    op_crystals = _reward(winner_id == opponent_id, is_tie)
    ch.crystals += ch_crystals
    op.crystals += op_crystals

    await session.flush()
    return {
        "challenger": {"elo_delta": ch_elo, "crystals": ch_crystals, "elo_after": ch.elo_rating},
        "opponent": {"elo_delta": op_elo, "crystals": op_crystals, "elo_after": op.elo_rating},
    }


# ── Shop ──────────────────────────────────────────────────────────────────────
# Catalog lives in code. Only "xp_boost" is functional; the rest are placeholders
# (available=False) to be filled in later.

XP_BOOST_QUESTS = 3  # number of 2x-XP quests granted per purchase

SHOP_ITEMS = [
    {
        "key": "xp_boost",
        "title": "⚡️ Буст XP ×2",
        "description": f"Двойной XP за следующие {XP_BOOST_QUESTS} квеста",
        "cost": 50,
        "available": True,
    },
    {
        "key": "streak_freeze",
        "title": "🧊 Заморозка серии",
        "description": "Скоро — сохранит серию при пропуске дня",
        "cost": 80,
        "available": False,
    },
    {
        "key": "hint_pack",
        "title": "💡 Набор подсказок",
        "description": "Скоро — пакет бесплатных подсказок",
        "cost": 60,
        "available": False,
    },
    {
        "key": "skip_quest",
        "title": "⏭ Пропуск квеста",
        "description": "Скоро — пропустить сложный квест",
        "cost": 120,
        "available": False,
    },
    {
        "key": "custom_title",
        "title": "🏷 Свой титул",
        "description": "Скоро — кастомный титул в профиле",
        "cost": 200,
        "available": False,
    },
]

_SHOP_BY_KEY = {item["key"]: item for item in SHOP_ITEMS}


async def purchase_item(
    session: AsyncSession, user_id: int, item_key: str
) -> tuple[bool, str, int]:
    """Returns (ok, message, crystals_after)."""
    stats = await get_user_stats(session, user_id)
    if stats is None:
        return False, "Профиль не найден", 0

    item = _SHOP_BY_KEY.get(item_key)
    if item is None:
        return False, "Товар не найден", stats.crystals
    if not item["available"]:
        return False, "Этот товар скоро появится", stats.crystals
    if stats.crystals < item["cost"]:
        return False, f"Недостаточно кристаллов (нужно {item['cost']} 💎)", stats.crystals

    # Charge and apply effect.
    stats.crystals -= item["cost"]
    session.add(
        CrystalTransaction(
            user_id=user_id,
            delta=-item["cost"],
            reason="shop",
            ref_id=item_key,
            balance=stats.crystals,
        )
    )

    if item_key == "xp_boost":
        stats.xp_boost_quests = (stats.xp_boost_quests or 0) + XP_BOOST_QUESTS
        msg = f"⚡️ Буст активирован! ×2 XP на следующие {XP_BOOST_QUESTS} квеста"
    else:
        msg = "Покупка совершена"

    await session.flush()
    return True, msg, stats.crystals


def list_shop_items(crystals: int) -> list[dict]:
    return [
        {**item, "can_afford": crystals >= item["cost"]}
        for item in SHOP_ITEMS
    ]


async def update_streak(session: AsyncSession, user_id: int) -> int:
    stats = await get_user_stats(session, user_id)
    today = date.today()

    if stats.streak_last_at == today:
        return stats.streak_days

    yesterday = date.fromordinal(today.toordinal() - 1)
    if stats.streak_last_at == yesterday:
        stats.streak_days += 1
    else:
        stats.streak_days = 1

    stats.streak_last_at = today
    await session.flush()
    return stats.streak_days


async def get_active_subscription(
    session: AsyncSession, user_id: int
) -> Optional[Subscription]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def get_user_achievements(
    session: AsyncSession, user_id: int
) -> list[dict]:
    """Earned achievements with full display data, newest first."""
    result = await session.execute(
        select(Achievement, UserAchievement.earned_at)
        .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
        .where(UserAchievement.user_id == user_id)
        .order_by(UserAchievement.earned_at.desc())
    )
    return [
        {
            "code": ach.code,
            "title": ach.title,
            "description": ach.description,
            "icon": ach.icon,
            "xp_reward": ach.xp_reward,
            "crystal_reward": ach.crystal_reward,
            "earned_at": earned_at,
        }
        for ach, earned_at in result
    ]


async def grant_achievement(
    session: AsyncSession, user_id: int, achievement_code: str
) -> Optional[Achievement]:
    """Idempotently grant an achievement. Returns the Achievement if newly
    granted, or None if it doesn't exist or the user already has it.
    """
    ach_result = await session.execute(
        select(Achievement).where(Achievement.code == achievement_code)
    )
    achievement = ach_result.scalar_one_or_none()
    if not achievement:
        return None

    existing = await session.execute(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement.id,
        )
    )
    if existing.scalar_one_or_none():
        return None

    session.add(UserAchievement(user_id=user_id, achievement_id=achievement.id))
    await session.flush()
    return achievement


# Unlock conditions keyed by achievement code. Each predicate takes UserStats.
ACHIEVEMENT_RULES = {
    "first_quest": lambda s: (s.total_quests or 0) >= 1,
    "quests_5": lambda s: (s.total_quests or 0) >= 5,
    "quests_10": lambda s: (s.total_quests or 0) >= 10,
    "quests_25": lambda s: (s.total_quests or 0) >= 25,
    "level_2": lambda s: s.level >= 2,
    "level_3": lambda s: s.level >= 3,
    "streak_3": lambda s: (s.streak_days or 0) >= 3,
    "streak_7": lambda s: (s.streak_days or 0) >= 7,
}


async def check_and_grant_achievements(
    session: AsyncSession, user_id: int
) -> list[dict]:
    """Evaluate all achievement rules against the user's current stats, grant
    any newly-met ones, apply their rewards, and return the newly granted list.
    """
    newly_granted: list[dict] = []
    stats = await get_user_stats(session, user_id)
    if stats is None:
        return newly_granted

    for code, rule in ACHIEVEMENT_RULES.items():
        if not rule(stats):
            continue
        achievement = await grant_achievement(session, user_id, code)
        if achievement is None:
            continue  # already earned or missing from catalog

        # Apply rewards directly (avoid add_xp boost/recursion).
        if achievement.crystal_reward:
            stats.crystals += achievement.crystal_reward
        if achievement.xp_reward:
            stats.xp += achievement.xp_reward

        newly_granted.append({
            "code": achievement.code,
            "title": achievement.title,
            "icon": achievement.icon,
            "xp_reward": achievement.xp_reward,
            "crystal_reward": achievement.crystal_reward,
        })

    if newly_granted:
        await session.flush()
    return newly_granted


async def create_referral(
    session: AsyncSession, referrer_id: int, referee_id: int
) -> Optional[Referral]:
    existing = await session.execute(
        select(Referral).where(Referral.referee_id == referee_id)
    )
    if existing.scalar_one_or_none():
        return None

    referral = Referral(referrer_id=referrer_id, referee_id=referee_id)
    session.add(referral)
    await session.flush()
    return referral


async def grant_referral_reward(session: AsyncSession, referral_id: int) -> None:
    await session.execute(
        update(Referral)
        .where(Referral.id == referral_id)
        .values(reward_granted=True)
    )
