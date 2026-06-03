from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class NotificationTemplateOut(BaseModel):
    code: str
    title: str
    body_template: str
    category: str

    model_config = {"from_attributes": True}


class SendNotificationRequest(BaseModel):
    user_id: int
    template_code: str
    payload: dict[str, Any] = {}
    channel: str = "telegram"


class NotificationOut(BaseModel):
    id: int
    user_id: int
    template_code: str
    payload: Optional[dict[str, Any]]
    channel: str
    status: str
    created_at: datetime
    sent_at: Optional[datetime]
    read_at: Optional[datetime]

    model_config = {"from_attributes": True}


class MarkReadRequest(BaseModel):
    notification_id: int
    user_id: int


class NotificationPreferenceOut(BaseModel):
    user_id: int
    category: str
    channel: str
    enabled: bool

    model_config = {"from_attributes": True}


class UpdatePreferenceRequest(BaseModel):
    user_id: int
    category: str
    channel: str
    enabled: bool
