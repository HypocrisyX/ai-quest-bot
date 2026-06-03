from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .schemas import (
    MarkReadRequest, NotificationOut, NotificationPreferenceOut,
    SendNotificationRequest, UpdatePreferenceRequest,
)
from . import repository as repo

router = APIRouter()
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/notifications", response_model=NotificationOut, status_code=201)
async def send_notification(data: SendNotificationRequest, db: DB):
    template = await repo.get_template(db, data.template_code)
    if not template:
        raise HTTPException(404, "Template not found")

    enabled = await repo.is_enabled(db, data.user_id, template.category, data.channel)
    if not enabled:
        raise HTTPException(403, "Notifications disabled for this category")

    async with db.begin():
        notification = await repo.create_notification(
            db, data.user_id, data.template_code, data.payload, data.channel
        )
    return notification


@router.get("/notifications/pending", response_model=list[NotificationOut])
async def get_pending(limit: int = Query(100, le=500), db: DB = None):
    return await repo.get_pending_notifications(db, limit)


@router.get("/notifications/user/{user_id}", response_model=list[NotificationOut])
async def get_user_notifications(
    user_id: int, limit: int = Query(20, le=100), db: DB = None
):
    return await repo.get_user_notifications(db, user_id, limit)


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: int, data: MarkReadRequest, db: DB):
    async with db.begin():
        await repo.mark_read(db, notification_id, data.user_id)
    return {"read": True}


@router.post("/notifications/{notification_id}/sent")
async def mark_sent(notification_id: int, db: DB):
    async with db.begin():
        await repo.mark_sent(db, notification_id)
    return {"sent": True}


@router.post("/notifications/{notification_id}/failed")
async def mark_failed(notification_id: int, db: DB):
    async with db.begin():
        await repo.mark_failed(db, notification_id)
    return {"failed": True}


@router.get("/preferences/{user_id}", response_model=list[NotificationPreferenceOut])
async def get_preferences(user_id: int, db: DB):
    return await repo.get_preferences(db, user_id)


@router.put("/preferences", response_model=NotificationPreferenceOut)
async def update_preference(data: UpdatePreferenceRequest, db: DB):
    async with db.begin():
        await repo.upsert_preference(
            db, data.user_id, data.category, data.channel, data.enabled
        )
    return NotificationPreferenceOut(
        user_id=data.user_id,
        category=data.category,
        channel=data.channel,
        enabled=data.enabled,
    )
