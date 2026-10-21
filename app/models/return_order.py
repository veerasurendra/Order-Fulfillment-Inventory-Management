import enum
from typing import List, Optional
from sqlalchemy import (
    String,
    Integer,
    Enum,
    ForeignKey,
    Boolean,
    Text,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class ReturnStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RECEIVED = "RECEIVED"
    REFUNDED = "REFUNDED"


class ItemCondition(str, enum.Enum):
    GOOD = "GOOD"
    DAMAGED = "DAMAGED"


class ReturnOrder(Base, TimestampMixin):
    __tablename__ = "returns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    return_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReturnStatus] = mapped_column(
        Enum(ReturnStatus, native_enum=False, length=30),
        default=ReturnStatus.REQUESTED,
        nullable=False,
        index=True,
    )
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship("Order")
    customer: Mapped["User"] = relationship("User")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    items: Mapped[List["ReturnItem"]] = relationship("ReturnItem", back_populates="return_order", cascade="all, delete-orphan")


class ReturnItem(Base):
    __tablename__ = "return_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("returns.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    condition: Mapped[ItemCondition] = mapped_column(
        Enum(ItemCondition, native_enum=False, length=20),
        default=ItemCondition.GOOD,
        nullable=False,
    )
    restocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_return_item_qty_positive"),
    )

    return_order: Mapped["ReturnOrder"] = relationship("ReturnOrder", back_populates="items")
    product: Mapped["Product"] = relationship("Product")
