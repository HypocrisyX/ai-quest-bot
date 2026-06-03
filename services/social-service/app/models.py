from sqlalchemy import BigInteger, Column, Date, Integer, SmallInteger, String, TIMESTAMP
from sqlalchemy.sql import func
from .database import Base


class Duel(Base):
    __tablename__ = "duels"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    challenger_id = Column(BigInteger, nullable=False)
    opponent_id = Column(BigInteger, nullable=False)
    quest_id = Column(Integer, nullable=False)
    status = Column(String(16), default="pending")  # pending, active, finished, expired
    challenger_score = Column(SmallInteger)
    opponent_score = Column(SmallInteger)
    winner_id = Column(BigInteger)
    elo_delta = Column(SmallInteger)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True))


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    period = Column(String(8), nullable=False)  # day, week, month, alltime
    period_start = Column(Date, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    rank = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False)
    xp_gained = Column(Integer, default=0)
    quests_done = Column(SmallInteger, default=0)
    captured_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Follow(Base):
    __tablename__ = "follows"

    follower_id = Column(BigInteger, primary_key=True)
    followed_id = Column(BigInteger, primary_key=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
