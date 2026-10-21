from typing import Optional, List
from sqlalchemy.orm import Session
from app.repositories.notification_repository import NotificationRepository
from app.models.notification import Notification, NotificationType
from app.core.exceptions import ResourceNotFoundError


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = NotificationRepository(db)

    def notify(
        self,
        user_id: int,
        type: NotificationType,
        title: str,
        message: str,
        reference_entity: Optional[str] = None,
        reference_id: Optional[str] = None,
    ) -> Notification:
        return self.repo.create_notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            reference_entity=reference_entity,
            reference_id=reference_id,
        )

    def list_notifications(self, user_id: int, is_read: Optional[bool] = None, page: int = 1, page_size: int = 20):
        return self.repo.list_user_notifications(user_id=user_id, is_read=is_read, page=page, page_size=page_size)

    def mark_read(self, notification_id: int, user_id: int) -> Notification:
        notification = self.repo.mark_as_read(notification_id=notification_id, user_id=user_id)
        if not notification:
            raise ResourceNotFoundError("Notification not found or access denied")
        self.db.commit()
        return notification

    def mark_all_read(self, user_id: int) -> int:
        count = self.repo.mark_all_as_read(user_id=user_id)
        self.db.commit()
        return count
