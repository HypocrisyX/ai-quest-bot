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
from sqlalchemy.sql import func

from .database import Base


class GameLevel(Base):
    __tablename__ = "game_levels"

    level = Column(SmallInteger, primary_key=True)
    title = Column(String(64), nullable=False)
    xp_required = Column(Integer, nullable=False)
    description = Column(Text)
    requires_sub = Column(Boolean, default=False)
    reward_crystals = Column(Integer, default=0)


class Quest(Base):
    __tablename__ = "quests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level_min = Column(SmallInteger, ForeignKey("game_levels.level"), nullable=False)
    level_max = Column(SmallInteger)
    type = Column(String(16), nullable=False)  # theory, practice, challenge, boss
    title = Column(String(128), nullable=False)
    description = Column(Text)
    instructions = Column(Text, nullable=False)
    ai_tool = Column(String(64))
    xp_reward = Column(Integer, default=50)
    crystal_reward = Column(Integer, default=0)
    time_limit_sec = Column(Integer)
    order_index = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


class QuestCriterion(Base):
    __tablename__ = "quest_criteria"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quest_id = Column(Integer, ForeignKey("quests.id", ondelete="CASCADE"), nullable=False)
    criterion = Column(String(128), nullable=False)
    weight = Column(SmallInteger, default=1)
    description = Column(Text)


class QuestHint(Base):
    __tablename__ = "quest_hints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quest_id = Column(Integer, ForeignKey("quests.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(SmallInteger, nullable=False)
    cost = Column(SmallInteger, default=5)
    text = Column(Text, nullable=False)


class UserQuestProgress(Base):
    __tablename__ = "user_quest_progress"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    status = Column(String(16), default="in_progress")  # in_progress, completed, failed
    attempts = Column(SmallInteger, default=0)
    best_score = Column(SmallInteger)
    xp_earned = Column(Integer, default=0)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    completed_at = Column(TIMESTAMP(timezone=True))


class UserHintUsed(Base):
    __tablename__ = "user_hints_used"

    user_id = Column(BigInteger, primary_key=True)
    hint_id = Column(Integer, ForeignKey("quest_hints.id"), primary_key=True)
    used_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class DailyQuest(Base):
    __tablename__ = "daily_quests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    level_min = Column(SmallInteger, nullable=False)
    xp_bonus = Column(Integer, default=25)


class UserDailyCompletion(Base):
    __tablename__ = "user_daily_completions"

    user_id = Column(BigInteger, primary_key=True)
    daily_id = Column(Integer, ForeignKey("daily_quests.id"), primary_key=True)
    completed_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
