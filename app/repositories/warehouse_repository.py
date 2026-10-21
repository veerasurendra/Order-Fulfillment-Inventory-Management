from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.models.warehouse import Warehouse, WarehouseUser, WarehouseStatus
from app.repositories.base import BaseRepository
from app.schemas.common import PaginationMeta


class WarehouseRepository(BaseRepository[Warehouse]):
    def __init__(self, db: Session):
        super().__init__(Warehouse, db)

    def get_by_name(self, name: str) -> Optional[Warehouse]:
        stmt = select(Warehouse).where(Warehouse.name == name.strip())
        return self.db.scalar(stmt)

    def list_warehouses(
        self,
        status: Optional[WarehouseStatus] = None,
        warehouse_ids: Optional[List[int]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Warehouse], PaginationMeta]:
        stmt = select(Warehouse).order_by(Warehouse.id.asc())

        if status:
            stmt = stmt.where(Warehouse.status == status)

        if warehouse_ids is not None:
            stmt = stmt.where(Warehouse.id.in_(warehouse_ids))

        return self.paginate(stmt, page=page, page_size=page_size)

    def is_user_assigned(self, warehouse_id: int, user_id: int) -> bool:
        stmt = select(WarehouseUser).where(
            WarehouseUser.warehouse_id == warehouse_id,
            WarehouseUser.user_id == user_id,
        )
        return self.db.scalar(stmt) is not None

    def assign_user(self, warehouse_id: int, user_id: int) -> WarehouseUser:
        assignment = WarehouseUser(warehouse_id=warehouse_id, user_id=user_id)
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def unassign_user(self, warehouse_id: int, user_id: int) -> None:
        stmt = delete(WarehouseUser).where(
            WarehouseUser.warehouse_id == warehouse_id,
            WarehouseUser.user_id == user_id,
        )
        self.db.execute(stmt)
        self.db.flush()

    def get_warehouse_users(self, warehouse_id: int) -> List[int]:
        stmt = select(WarehouseUser.user_id).where(WarehouseUser.warehouse_id == warehouse_id)
        return list(self.db.scalars(stmt).all())
