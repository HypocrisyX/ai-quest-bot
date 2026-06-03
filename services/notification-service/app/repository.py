from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Notification, NotificationPreference, NotificationTemplate


async def get_template(
    session: AsyncSession, code: str
) -> Optional[NotificationTemplate]:
    result = await session.execute(
        select(NotificationTemplate).where(NotificationTemplate.code == code)
    )
    return result.scalar_one_or_none()


async def create_notification(
    session: AsyncSession,
    user_id: int,
    template_code: str,
    payload: dict[str, Any],
    channel: str = "telegram",
) -> Notification:
    notification = Notification(
        user_id=user_id,
        template_code=template_code,
        payload=payload,
        channel=channel,
    )
    session.add(notification)
    await session.flush()
    return notification


async def get_pending_notifications(
    session: AsyncSession, limit: int = 100
) -> list[Notification]:
    result = await session.execute(
        select(Notification)
        .where(Notification.status == "pending")
        .order_by(Notification.created_at)
        .limit(limit)
    )
    return list(result.scalars())


async def get_user_notifications(
    session: AsyncSession, user_id: int, limit: int = 20
) -> list[Notification]:
    result = await session.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def mark_sent(session: AsyncSession, notification_id: int) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.id == notification_id)
        .values(status="sent", sent_at=datetime.now(timezone.utc))
    )


async def mark_failed(session: AsyncSession, notification_id: int) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.id == notification_id)
        .values(status="failed")
    )


async def mark_read(
    session: AsyncSession, notification_id: int, user_id: int
) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(status="read", read_at=datetime.now(timezone.utc))
    )


async def is_enabled(
    session: AsyncSession, user_id: int, category: str, channel: str
) -> bool:
    result = await session.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.category == category,
            NotificationPreference.channel == channel,
        )
    )
    pref = result.scalar_one_or_none()
    return pref.enabled if pref else True


async def upsert_preference(
    session: AsyncSession,
    user_id: int,
    category: str,
    channel: str,
    enabled: bool,
) -> None:
    stmt = (
        insert(NotificationPreference)
        .values(user_id=user_id, category=category, channel=channel, enabled=enabled)
        .on_conflict_do_update(
            index_elements=["user_id", "category", "channel"],
            set_={"enabled": enabled},
        )
    )
    await session.execute(stmt)


async def get_preferences(
    session: AsyncSession, user_id: int
) -> list[NotificationPreference]:
    result = await session.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id
        )
    )
    return list(result.scalars())
