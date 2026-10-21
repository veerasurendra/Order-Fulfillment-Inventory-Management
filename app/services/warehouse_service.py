from typing import Optional, List
from sqlalchemy.orm import Session
from app.core.exceptions import (
    ConflictError,
    ResourceNotFoundError,
    WarehouseAccessDeniedError,
)
from app.models.warehouse import Warehouse, WarehouseStatus
from app.models.user import User, UserRole
from app.repositories.warehouse_repository import WarehouseRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate


class WarehouseService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = WarehouseRepository(db)
        self.user_repo = UserRepository(db)
        self.audit_service = AuditService(db)

    def check_user_warehouse_access(self, user: User, warehouse_id: int) -> None:
        """
        Verify that user is authorized for the given warehouse.
        Admins have global access.
        Warehouse Managers and Fulfillment Agents must have an assignment.
        """
        if user.role == UserRole.ADMIN:
            return

        is_assigned = self.repo.is_user_assigned(warehouse_id=warehouse_id, user_id=user.id)
        if not is_assigned:
            raise WarehouseAccessDeniedError(
                f"User '{user.username}' is not authorized to access warehouse ID {warehouse_id}"
            )

    def create_warehouse(self, req: WarehouseCreate, user_id: int, ip_address: Optional[str] = None) -> Warehouse:
        if self.repo.get_by_name(req.name):
            raise ConflictError(f"A warehouse with name '{req.name}' already exists")

        warehouse = Warehouse(
            name=req.name.strip(),
            location=req.location.strip(),
            status=req.status,
            capacity=req.capacity,
        )
        self.repo.create(warehouse)
        self.db.commit()
        self.db.refresh(warehouse)

        self.audit_service.log(
            action="WAREHOUSE_CREATED",
            entity="WAREHOUSE",
            entity_id=str(warehouse.id),
            user_id=user_id,
            ip_address=ip_address,
            metadata_json={"name": warehouse.name, "capacity": warehouse.capacity},
        )
        self.db.commit()
        return warehouse

    def get_warehouse(self, warehouse_id: int, current_user: Optional[User] = None) -> Warehouse:
        warehouse = self.repo.get_by_id(warehouse_id)
        if not warehouse:
            raise ResourceNotFoundError(f"Warehouse with ID {warehouse_id} not found")

        if current_user and current_user.role in [UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT]:
            self.check_user_warehouse_access(current_user, warehouse_id)

        return warehouse

    def update_warehouse(
        self,
        warehouse_id: int,
        req: WarehouseUpdate,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> Warehouse:
        self.check_user_warehouse_access(current_user, warehouse_id)
        warehouse = self.get_warehouse(warehouse_id)

        if req.name is not None:
            existing = self.repo.get_by_name(req.name)
            if existing and existing.id != warehouse.id:
                raise ConflictError(f"A warehouse with name '{req.name}' already exists")
            warehouse.name = req.name.strip()
        if req.location is not None:
            warehouse.location = req.location.strip()
        if req.capacity is not None:
            warehouse.capacity = req.capacity
        if req.status is not None:
            warehouse.status = req.status

        self.db.commit()
        self.db.refresh(warehouse)

        self.audit_service.log(
            action="WAREHOUSE_UPDATED",
            entity="WAREHOUSE",
            entity_id=str(warehouse.id),
            user_id=current_user.id,
            ip_address=ip_address,
            metadata_json={"name": warehouse.name, "status": warehouse.status.value},
        )
        self.db.commit()
        return warehouse

    def activate_warehouse(self, warehouse_id: int, current_user: User, ip_address: Optional[str] = None) -> Warehouse:
        self.check_user_warehouse_access(current_user, warehouse_id)
        warehouse = self.get_warehouse(warehouse_id)
        warehouse.status = WarehouseStatus.ACTIVE
        self.db.commit()
        self.db.refresh(warehouse)

        self.audit_service.log(
            action="WAREHOUSE_ACTIVATED",
            entity="WAREHOUSE",
            entity_id=str(warehouse.id),
            user_id=current_user.id,
            ip_address=ip_address,
        )
        self.db.commit()
        return warehouse

    def deactivate_warehouse(self, warehouse_id: int, current_user: User, ip_address: Optional[str] = None) -> Warehouse:
        self.check_user_warehouse_access(current_user, warehouse_id)
        warehouse = self.get_warehouse(warehouse_id)
        warehouse.status = WarehouseStatus.INACTIVE
        self.db.commit()
        self.db.refresh(warehouse)

        self.audit_service.log(
            action="WAREHOUSE_DEACTIVATED",
            entity="WAREHOUSE",
            entity_id=str(warehouse.id),
            user_id=current_user.id,
            ip_address=ip_address,
        )
        self.db.commit()
        return warehouse

    def list_warehouses(
        self,
        current_user: User,
        status: Optional[WarehouseStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ):
        warehouse_ids = None
        if current_user.role in [UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT]:
            warehouse_ids = self.user_repo.get_user_warehouse_ids(current_user.id)

        return self.repo.list_warehouses(
            status=status,
            warehouse_ids=warehouse_ids,
            page=page,
            page_size=page_size,
        )

    def assign_user(self, warehouse_id: int, target_user_id: int, current_user: User) -> None:
        warehouse = self.get_warehouse(warehouse_id)
        target_user = self.user_repo.get_by_id(target_user_id)
        if not target_user:
            raise ResourceNotFoundError(f"User with ID {target_user_id} not found")

        if self.repo.is_user_assigned(warehouse_id, target_user_id):
            return  # Already assigned

        self.repo.assign_user(warehouse_id, target_user_id)
        self.db.commit()

        self.audit_service.log(
            action="WAREHOUSE_USER_ASSIGNED",
            entity="WAREHOUSE_USER",
            entity_id=f"{warehouse_id}_{target_user_id}",
            user_id=current_user.id,
            metadata_json={"warehouse_id": warehouse_id, "user_id": target_user_id},
        )
        self.db.commit()

    def unassign_user(self, warehouse_id: int, target_user_id: int, current_user: User) -> None:
        warehouse = self.get_warehouse(warehouse_id)
        self.repo.unassign_user(warehouse_id, target_user_id)
        self.db.commit()

        self.audit_service.log(
            action="WAREHOUSE_USER_UNASSIGNED",
            entity="WAREHOUSE_USER",
            entity_id=f"{warehouse_id}_{target_user_id}",
            user_id=current_user.id,
            metadata_json={"warehouse_id": warehouse_id, "user_id": target_user_id},
        )
        self.db.commit()
