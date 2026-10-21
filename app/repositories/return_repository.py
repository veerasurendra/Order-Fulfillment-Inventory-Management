from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models.return_order import ReturnOrder, ReturnItem, ReturnStatus
from app.repositories.base import BaseRepository
from app.schemas.common import PaginationMeta


class ReturnRepository(BaseRepository[ReturnOrder]):
    def __init__(self, db: Session):
        super().__init__(ReturnOrder, db)

    def get_by_id_detailed(self, return_id: int) -> Optional[ReturnOrder]:
        stmt = (
            select(ReturnOrder)
            .options(
                joinedload(ReturnOrder.customer),
                joinedload(ReturnOrder.order),
                joinedload(ReturnOrder.warehouse),
                selectinload(ReturnOrder.items).joinedload(ReturnItem.product),
            )
            .where(ReturnOrder.id == return_id)
        )
        return self.db.scalar(stmt)

    def get_by_number(self, return_number: str) -> Optional[ReturnOrder]:
        stmt = (
            select(ReturnOrder)
            .options(
                joinedload(ReturnOrder.customer),
                joinedload(ReturnOrder.order),
                joinedload(ReturnOrder.warehouse),
                selectinload(ReturnOrder.items).joinedload(ReturnItem.product),
            )
            .where(ReturnOrder.return_number == return_number.strip())
        )
        return self.db.scalar(stmt)

    def list_returns(
        self,
        customer_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        warehouse_ids: Optional[List[int]] = None,
        status: Optional[ReturnStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[ReturnOrder], PaginationMeta]:
        stmt = (
            select(ReturnOrder)
            .options(
                joinedload(ReturnOrder.customer),
                joinedload(ReturnOrder.order),
                joinedload(ReturnOrder.warehouse),
                selectinload(ReturnOrder.items).joinedload(ReturnItem.product),
            )
            .order_by(ReturnOrder.created_at.desc())
        )

        if customer_id is not None:
            stmt = stmt.where(ReturnOrder.customer_id == customer_id)

        if warehouse_id is not None:
            stmt = stmt.where(ReturnOrder.warehouse_id == warehouse_id)
        elif warehouse_ids is not None:
            stmt = stmt.where(ReturnOrder.warehouse_id.in_(warehouse_ids))

        if status is not None:
            stmt = stmt.where(ReturnOrder.status == status)

        return self.paginate(stmt, page=page, page_size=page_size)
