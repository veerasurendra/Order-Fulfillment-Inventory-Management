from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationType
from app.repositories.base import BaseRepository
from app.schemas.common import PaginationMeta


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db: Session):
        super().__init__(Notification, db)

    def create_notification(
        self,
        user_id: int,
        type: NotificationType,
        title: str,
        message: str,
        reference_entity: Optional[str] = None,
        reference_id: Optional[str] = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            reference_entity=reference_entity,
            reference_id=reference_id,
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(notification)
        self.db.flush()
        return notification

    def list_user_notifications(
        self,
        user_id: int,
        is_read: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Notification], PaginationMeta]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        if is_read is not None:
            stmt = stmt.where(Notification.is_read == is_read)

        return self.paginate(stmt, page=page, page_size=page_size)

    def mark_as_read(self, notification_id: int, user_id: int) -> Optional[Notification]:
        notification = self.db.get(Notification, notification_id)
        if notification and notification.user_id == user_id:
            notification.is_read = True
            self.db.flush()
            return notification
        return None

    def mark_all_as_read(self, user_id: int) -> int:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
        res = self.db.execute(stmt)
        self.db.flush()
        return res.rowcount
