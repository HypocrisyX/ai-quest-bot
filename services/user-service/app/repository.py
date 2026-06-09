from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select, update
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


# ── Admin ─────────────────────────────────────────────────────────────────────

async def admin_stats(session: AsyncSession) -> dict:
    total_users = await session.scalar(select(func.count()).select_from(User))
    today = date.today()
    active_today = await session.scalar(
        select(func.count()).select_from(User).where(
            func.date(User.last_active_at) == today
        )
    )
    return {"total_users": total_users or 0, "active_today": active_today or 0}


async def admin_list_users(
    session: AsyncSession, limit: int = 10, offset: int = 0
) -> dict:
    total = await session.scalar(select(func.count()).select_from(User))
    result = await session.execute(
        select(User, UserStats)
        .join(UserStats, UserStats.user_id == User.id)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    users = [
        {
            "id": u.id,
            "username": u.username,
            "first_name": u.first_name,
            "level": s.level,
            "xp": s.xp,
            "crystals": s.crystals,
            "elo_rating": s.elo_rating,
            "total_quests": s.total_quests,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_active_at": u.last_active_at.isoformat() if u.last_active_at else None,
        }
        for u, s in result
    ]
    return {"total": total or 0, "users": users}


# ── Leaderboard ───────────────────────────────────────────────────────────────

def _display_name(username: Optional[str], first_name: str) -> str:
    return f"@{username}" if username else first_name


async def leaderboard(
    session: AsyncSession, metric: str, limit: int = 10
) -> list[dict]:
    """Top users ranked live. metric: 'xp' (level then xp) or 'elo'."""
    if metric == "elo":
        order = (UserStats.elo_rating.desc(), UserStats.level.desc())
    else:
        order = (UserStats.level.desc(), UserStats.xp.desc())

    result = await session.execute(
        select(
            User.id, User.username, User.first_name,
            UserStats.level, UserStats.xp, UserStats.elo_rating,
        )
        .join(UserStats, UserStats.user_id == User.id)
        .order_by(*order)
        .limit(limit)
    )
    return [
        {
            "rank": i,
            "user_id": uid,
            "name": _display_name(username, first_name),
            "level": level,
            "xp": xp,
            "elo_rating": elo,
        }
        for i, (uid, username, first_name, level, xp, elo) in enumerate(result, start=1)
    ]


async def user_rank(
    session: AsyncSession, user_id: int, metric: str
) -> Optional[dict]:
    """The user's own rank (1-based) and metric value, or None if no stats."""
    stats = await get_user_stats(session, user_id)
    if stats is None:
        return None

    if metric == "elo":
        higher = await session.scalar(
            select(func.count()).select_from(UserStats).where(
                UserStats.elo_rating > stats.elo_rating
            )
        )
        value = stats.elo_rating
    else:
        higher = await session.scalar(
            select(func.count()).select_from(UserStats).where(
                (UserStats.level > stats.level)
                | ((UserStats.level == stats.level) & (UserStats.xp > stats.xp))
            )
        )
        value = stats.level

    return {"rank": (higher or 0) + 1, "value": value}


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


async def _stats_for_update(session: AsyncSession, user_id: int) -> Optional[UserStats]:
    """Row-locked read (SELECT ... FOR UPDATE). Use in every path that MUTATES
    user_stats so concurrent requests serialize instead of racing the balance.
    """
    result = await session.execute(
        select(UserStats).where(UserStats.user_id == user_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def _lock_two(session: AsyncSession, a_id: int, b_id: int) -> None:
    """Lock two users' rows in a deadlock-safe order (ascending id)."""
    for uid in sorted({a_id, b_id}):
        await _stats_for_update(session, uid)


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
    stats = await _stats_for_update(session, user_id)
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
    stats = await _stats_for_update(session, user_id)
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
    await _lock_two(session, challenger_id, opponent_id)
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


# ── Marketplace ───────────────────────────────────────────────────────────────

MARKETPLACE_COMMISSION_PCT = 10  # app's cut of each sale


async def marketplace_settle(
    session: AsyncSession, buyer_id: int, seller_id: int, price: int
) -> dict:
    """Move crystals buyer→seller for a marketplace purchase, minus commission.

    The commission share simply leaves circulation (= the app's revenue; becomes
    real money once Stars are wired up). Returns ok + amounts.
    """
    if price <= 0:
        return {"ok": False, "reason": "invalid_price", "seller_earned": 0, "buyer_balance": 0}
    if buyer_id == seller_id:
        return {"ok": False, "reason": "self", "seller_earned": 0, "buyer_balance": 0}

    await _lock_two(session, buyer_id, seller_id)
    buyer = await get_user_stats(session, buyer_id)
    seller = await get_user_stats(session, seller_id)
    if buyer is None or seller is None:
        return {"ok": False, "reason": "missing_user", "seller_earned": 0, "buyer_balance": 0}
    if buyer.crystals < price:
        return {
            "ok": False, "reason": "insufficient",
            "seller_earned": 0, "buyer_balance": buyer.crystals,
        }

    seller_earned = round(price * (100 - MARKETPLACE_COMMISSION_PCT) / 100)
    await add_crystals(session, buyer_id, -price, "marketplace_buy")
    await add_crystals(session, seller_id, seller_earned, "marketplace_sell")

    return {
        "ok": True,
        "reason": None,
        "seller_earned": seller_earned,
        "commission": price - seller_earned,
        "buyer_balance": buyer.crystals,
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
        "description": "Сохранит серию если пропустишь один день",
        "cost": 80,
        "available": True,
    },
    {
        "key": "hint_pack",
        "title": "💡 Набор подсказок",
        "description": "3 бесплатные подсказки для квестов",
        "cost": 60,
        "available": True,
    },
    {
        "key": "skip_quest",
        "title": "⏭ Пропуск квеста",
        "description": "Пропустить сложный квест (засчитывается без награды)",
        "cost": 120,
        "available": True,
    },
    {
        "key": "custom_title",
        "title": "🏷 Свой титул",
        "description": "Кастомный титул в профиле (1–20 символов)",
        "cost": 200,
        "available": True,
    },
]

_SHOP_BY_KEY = {item["key"]: item for item in SHOP_ITEMS}


async def purchase_item(
    session: AsyncSession, user_id: int, item_key: str
) -> tuple[bool, str, int]:
    """Returns (ok, message, crystals_after)."""
    stats = await _stats_for_update(session, user_id)
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
    elif item_key == "streak_freeze":
        stats.streak_freeze_count = (stats.streak_freeze_count or 0) + 1
        msg = "🧊 Заморозка добавлена! Сохранит серию при пропуске одного дня."
    elif item_key == "hint_pack":
        stats.free_hints = (stats.free_hints or 0) + 3
        msg = "💡 3 бесплатные подсказки добавлены!"
    elif item_key == "skip_quest":
        stats.quest_skips = (stats.quest_skips or 0) + 1
        msg = "⏭ Пропуск квеста добавлен!"
    elif item_key == "custom_title":
        msg = "INPUT:custom_title"
    else:
        msg = "Покупка совершена"

    await session.flush()
    return True, msg, stats.crystals


async def consume_free_hint(session: AsyncSession, user_id: int) -> dict:
    stats = await _stats_for_update(session, user_id)
    if stats is None or (stats.free_hints or 0) <= 0:
        return {"used_free": False, "free_hints_left": 0}
    stats.free_hints -= 1
    await session.flush()
    return {"used_free": True, "free_hints_left": stats.free_hints}


async def consume_skip(session: AsyncSession, user_id: int) -> dict:
    stats = await _stats_for_update(session, user_id)
    if stats is None or (stats.quest_skips or 0) <= 0:
        return {"consumed": False, "skips_left": 0}
    stats.quest_skips -= 1
    await session.flush()
    return {"consumed": True, "skips_left": stats.quest_skips}


async def set_title(session: AsyncSession, user_id: int, title: str) -> str:
    stats = await _stats_for_update(session, user_id)
    if stats is None:
        raise ValueError("User not found")
    stats.class_title = title.strip()
    await session.flush()
    return stats.class_title


def list_shop_items(crystals: int) -> list[dict]:
    return [
        {**item, "can_afford": crystals >= item["cost"]}
        for item in SHOP_ITEMS
    ]


async def update_streak(session: AsyncSession, user_id: int) -> int:
    stats = await _stats_for_update(session, user_id)
    today = date.today()

    if stats.streak_last_at == today:
        return stats.streak_days

    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    if stats.streak_last_at == yesterday:
        stats.streak_days += 1
    elif stats.streak_last_at == two_days_ago and (stats.streak_freeze_count or 0) > 0:
        stats.streak_freeze_count -= 1
        # streak_days unchanged — freeze preserves it, doesn't advance it
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
    stats = await _stats_for_update(session, user_id)
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


REFERRAL_BONUS = 100  # crystals to BOTH referrer and referee


async def complete_referral(
    session: AsyncSession, referrer_id: int, referee_id: int
) -> dict:
    """Link referee→referrer and grant the bonus to both. Idempotent per referee.

    Returns {created: bool, bonus: int, reason: str|None}.
    """
    if referrer_id == referee_id:
        return {"created": False, "bonus": 0, "reason": "self"}

    referrer = await get_user_stats(session, referrer_id)
    referee = await get_user_stats(session, referee_id)
    if referrer is None or referee is None:
        return {"created": False, "bonus": 0, "reason": "missing_user"}

    referral = await create_referral(session, referrer_id, referee_id)
    if referral is None:
        return {"created": False, "bonus": 0, "reason": "exists"}

    await add_crystals(session, referrer_id, REFERRAL_BONUS, "referral")
    await add_crystals(session, referee_id, REFERRAL_BONUS, "referral")
    await grant_referral_reward(session, referral.id)

    return {"created": True, "bonus": REFERRAL_BONUS, "reason": None}


async def referral_stats(session: AsyncSession, referrer_id: int) -> dict:
    invited = await session.scalar(
        select(func.count()).select_from(Referral).where(
            Referral.referrer_id == referrer_id
        )
    )
    invited = invited or 0
    return {"invited": invited, "earned": invited * REFERRAL_BONUS}
