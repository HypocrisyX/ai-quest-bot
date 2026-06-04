import uuid

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)  # telegram_id
    username = Column(String(64))
    first_name = Column(String(128))
    language_code = Column(String(8), default="ru")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    last_active_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class UserStats(Base):
    __tablename__ = "user_stats"

    user_id = Column(BigInteger, ForeignKey("users.id"), primary_key=True)
    level = Column(SmallInteger, default=1)
    xp = Column(Integer, default=0)
    xp_to_next = Column(Integer, default=1100)
    crystals = Column(Integer, default=0)
    elo_rating = Column(Integer, default=1000)
    streak_days = Column(SmallInteger, default=0)
    streak_last_at = Column(Date)
    total_quests = Column(Integer, default=0)
    class_title = Column(String(32), default="Новичок")
    xp_boost_quests = Column(Integer, nullable=False, server_default="0")  # remaining 2x-XP quests


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    plan = Column(String(16), nullable=False)
    status = Column(String(16), default="active")
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    payment_ref = Column(String(128))


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False)
    title = Column(String(128), nullable=False)
    description = Column(Text)
    icon = Column(String(16))
    xp_reward = Column(Integer, default=0)
    crystal_reward = Column(Integer, default=0)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    user_id = Column(BigInteger, ForeignKey("users.id"), primary_key=True)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), primary_key=True)
    earned_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class CrystalTransaction(Base):
    __tablename__ = "crystal_transactions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    delta = Column(Integer, nullable=False)
    reason = Column(String(32), nullable=False)
    ref_id = Column(String(64))
    balance = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class XpHistory(Base):
    __tablename__ = "xp_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    delta_xp = Column(Integer, nullable=False)
    reason = Column(String(32), nullable=False)
    ref_id = Column(String(64))
    level_after = Column(SmallInteger, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(BigInteger, nullable=False)
    referee_id = Column(BigInteger, unique=True, nullable=False)
    reward_granted = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
