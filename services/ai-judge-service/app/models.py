from sqlalchemy import TIMESTAMP, BigInteger, Column, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from .database import Base


class AiEvaluation(Base):
    __tablename__ = "ai_evaluations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    quest_id = Column(Integer, nullable=False)
    attempt_num = Column(SmallInteger, nullable=False)
    user_input = Column(Text, nullable=False)
    ai_output = Column(Text)
    score = Column(SmallInteger)
    feedback = Column(Text)
    criteria_scores = Column(JSONB)
    model_used = Column(String(32))
    tokens_used = Column(Integer)
    evaluated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
