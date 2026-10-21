from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.notification import NotificationType


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: NotificationType
    title: str
    message: str
    reference_entity: Optional[str] = None
    reference_id: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
