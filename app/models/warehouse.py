import enum
from datetime import datetime, timezone
from typing import List
from sqlalchemy import String, Integer, Enum, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class WarehouseStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Warehouse(Base, TimestampMixin):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[WarehouseStatus] = mapped_column(
        Enum(WarehouseStatus, native_enum=False, length=20),
        default=WarehouseStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    capacity: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)

    # Relationships
    user_assignments: Mapped[List["WarehouseUser"]] = relationship(
        "WarehouseUser", back_populates="warehouse", cascade="all, delete-orphan"
    )
    inventory_items: Mapped[List["Inventory"]] = relationship(
        "Inventory", back_populates="warehouse", cascade="all, delete-orphan"
    )
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="warehouse")


class WarehouseUser(Base):
    __tablename__ = "warehouse_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("warehouse_id", "user_id", name="uq_warehouse_user"),
    )

    warehouse: Mapped["Warehouse"] = relationship("Warehouse", back_populates="user_assignments")
    user: Mapped["User"] = relationship("User", back_populates="warehouse_assignments")
