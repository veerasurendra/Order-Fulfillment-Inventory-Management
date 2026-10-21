from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.pagination import PaginationParams
from app.models.user import User
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationResponse
from app.schemas.common import SuccessResponse, PaginatedResponse, MessageResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=PaginatedResponse[NotificationResponse])
def list_notifications(
    is_read: Optional[bool] = Query(None, description="Filter by read/unread status"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve notifications for the authenticated user."""
    service = NotificationService(db)
    items, meta = service.list_notifications(
        user_id=current_user.id,
        is_read=is_read,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse(
        data=[NotificationResponse.model_validate(n) for n in items],
        pagination=meta,
    )


@router.patch("/{id}/read", response_model=SuccessResponse[NotificationResponse])
def mark_notification_read(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a specific notification as read."""
    service = NotificationService(db)
    notif = service.mark_read(notification_id=id, user_id=current_user.id)
    return SuccessResponse(data=NotificationResponse.model_validate(notif), message="Notification marked as read")


@router.patch("/read-all", response_model=MessageResponse)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all unread notifications for current user as read."""
    service = NotificationService(db)
    count = service.mark_all_read(user_id=current_user.id)
    return MessageResponse(message=f"Marked {count} notifications as read")
