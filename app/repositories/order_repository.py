from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models.order import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentStatus,
    OrderStatusHistory,
    OrderAssignment,
)
from app.repositories.base import BaseRepository
from app.schemas.common import PaginationMeta


class OrderRepository(BaseRepository[Order]):
    def __init__(self, db: Session):
        super().__init__(Order, db)

    def get_by_id_detailed(self, order_id: int) -> Optional[Order]:
        stmt = (
            select(Order)
            .options(
                joinedload(Order.customer),
                joinedload(Order.assigned_agent),
                joinedload(Order.warehouse),
                selectinload(Order.items).joinedload(OrderItem.product),
                selectinload(Order.status_history),
                selectinload(Order.assignments).joinedload(OrderAssignment.agent),
            )
            .where(Order.id == order_id)
        )
        return self.db.scalar(stmt)

    def get_by_number(self, order_number: str) -> Optional[Order]:
        stmt = (
            select(Order)
            .options(
                joinedload(Order.customer),
                joinedload(Order.assigned_agent),
                joinedload(Order.warehouse),
                selectinload(Order.items).joinedload(OrderItem.product),
            )
            .where(Order.order_number == order_number.strip())
        )
        return self.db.scalar(stmt)

    def list_orders(
        self,
        customer_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        warehouse_ids: Optional[List[int]] = None,
        status: Optional[OrderStatus] = None,
        payment_status: Optional[PaymentStatus] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Order], PaginationMeta]:
        stmt = (
            select(Order)
            .options(
                joinedload(Order.customer),
                joinedload(Order.assigned_agent),
                joinedload(Order.warehouse),
                selectinload(Order.items).joinedload(OrderItem.product),
            )
        )

        if customer_id is not None:
            stmt = stmt.where(Order.customer_id == customer_id)

        if warehouse_id is not None:
            stmt = stmt.where(Order.warehouse_id == warehouse_id)
        elif warehouse_ids is not None:
            stmt = stmt.where(Order.warehouse_id.in_(warehouse_ids))

        if status is not None:
            stmt = stmt.where(Order.status == status)

        if payment_status is not None:
            stmt = stmt.where(Order.payment_status == payment_status)

        if date_from is not None:
            stmt = stmt.where(Order.created_at >= date_from)

        if date_to is not None:
            stmt = stmt.where(Order.created_at <= date_to)

        if min_amount is not None:
            stmt = stmt.where(Order.total_amount >= min_amount)

        if max_amount is not None:
            stmt = stmt.where(Order.total_amount <= max_amount)

        # Sorting
        sort_column = getattr(Order, sort_by, Order.created_at)
        if sort_order.lower() == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())

        return self.paginate(stmt, page=page, page_size=page_size)

    def add_status_history(
        self,
        order_id: int,
        old_status: OrderStatus,
        new_status: OrderStatus,
        changed_by_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> OrderStatusHistory:
        history = OrderStatusHistory(
            order_id=order_id,
            old_status=old_status,
            new_status=new_status,
            changed_by_id=changed_by_id,
            notes=notes,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(history)
        self.db.flush()
        return history

    def add_assignment(
        self,
        order_id: int,
        agent_id: int,
        assigned_by_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> OrderAssignment:
        assignment = OrderAssignment(
            order_id=order_id,
            agent_id=agent_id,
            assigned_by_id=assigned_by_id,
            notes=notes,
            assigned_at=datetime.now(timezone.utc),
        )
        self.db.add(assignment)
        self.db.flush()
        return assignment
