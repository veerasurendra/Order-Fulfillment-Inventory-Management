import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, Enum, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class NotificationType(str, enum.Enum):
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    ORDER_ASSIGNED = "ORDER_ASSIGNED"
    ORDER_SHIPPED = "ORDER_SHIPPED"
    ORDER_DELIVERED = "ORDER_DELIVERED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    RETURN_REQUESTED = "RETURN_REQUESTED"
    RETURN_APPROVED = "RETURN_APPROVED"
    LOW_STOCK = "LOW_STOCK"
    INVENTORY_TRANSFER = "INVENTORY_TRANSFER"
    FAILED_ORDER_PROCESSING = "FAILED_ORDER_PROCESSING"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, native_enum=False, length=40),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reference_entity: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="notifications")
