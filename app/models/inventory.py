import enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    Integer,
    String,
    Enum,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    CheckConstraint,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class TransactionType(str, enum.Enum):
    PURCHASE = "PURCHASE"
    SALE = "SALE"
    RESERVATION = "RESERVATION"
    RELEASE = "RELEASE"
    ADJUSTMENT = "ADJUSTMENT"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    RETURN = "RETURN"
    DAMAGE = "DAMAGE"


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    available_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    damaged_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uq_inventory_product_warehouse"),
        CheckConstraint("available_quantity >= 0", name="chk_available_qty_non_negative"),
        CheckConstraint("reserved_quantity >= 0", name="chk_reserved_qty_non_negative"),
        CheckConstraint("damaged_quantity >= 0", name="chk_damaged_qty_non_negative"),
    )

    product: Mapped["Product"] = relationship("Product", back_populates="inventory_items")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse", back_populates="inventory_items")


class InventoryTransaction(Base):
    """Immutable audit trail for all inventory movements."""
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, native_enum=False, length=30),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_entity: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    product: Mapped["Product"] = relationship("Product")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    user: Mapped[Optional["User"]] = relationship("User")
