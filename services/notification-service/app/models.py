from sqlalchemy import BigInteger, Boolean, Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from .database import Base


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    code = Column(String(64), primary_key=True)
    title = Column(String(128), nullable=False)
    body_template = Column(Text, nullable=False)
    category = Column(String(32), nullable=False)  # quest, streak, duel, system, promo


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    template_code = Column(String(64), nullable=False)
    payload = Column(JSONB)
    channel = Column(String(16), default="telegram")  # telegram, push
    status = Column(String(16), default="pending")  # pending, sent, failed, read
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    sent_at = Column(TIMESTAMP(timezone=True))
    read_at = Column(TIMESTAMP(timezone=True))


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id = Column(BigInteger, primary_key=True)
    category = Column(String(32), primary_key=True)
    channel = Column(String(16), primary_key=True)
    enabled = Column(Boolean, default=True)
