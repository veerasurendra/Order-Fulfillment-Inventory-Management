from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.core.exceptions import (
    ResourceNotFoundError,
    BadRequestError,
    InsufficientInventoryError,
    InvalidInventoryTransferError,
    WarehouseAccessDeniedError,
)
from app.models.inventory import Inventory, InventoryTransaction, TransactionType
from app.models.product import Product, ProductStatus
from app.models.warehouse import Warehouse, WarehouseStatus
from app.models.user import User, UserRole
from app.models.notification import NotificationType
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.warehouse_repository import WarehouseRepository
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.schemas.inventory import (
    InventoryAdjustRequest,
    InventoryAdjustResponse,
    InventoryTransferRequest,
    InventoryTransferResponse,
    LowStockResponse,
    InventoryResponse,
)


class InventoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InventoryRepository(db)
        self.product_repo = ProductRepository(db)
        self.warehouse_repo = WarehouseRepository(db)
        self.audit_service = AuditService(db)
        self.notification_service = NotificationService(db)

    def _verify_warehouse_access(self, user: User, warehouse_id: int) -> None:
        if user.role == UserRole.ADMIN:
            return
        if not self.warehouse_repo.is_user_assigned(warehouse_id=warehouse_id, user_id=user.id):
            raise WarehouseAccessDeniedError(
                f"User '{user.username}' is not authorized for warehouse ID {warehouse_id}"
            )

    def get_or_create_inventory(
        self,
        product_id: int,
        warehouse_id: int,
        for_update: bool = False,
    ) -> Inventory:
        inv = self.repo.get_inventory(product_id=product_id, warehouse_id=warehouse_id, for_update=for_update)
        if not inv:
            # Verify product and warehouse exist
            product = self.product_repo.get_by_id(product_id)
            if not product:
                raise ResourceNotFoundError(f"Product with ID {product_id} not found")
            warehouse = self.warehouse_repo.get_by_id(warehouse_id)
            if not warehouse:
                raise ResourceNotFoundError(f"Warehouse with ID {warehouse_id} not found")

            inv = Inventory(
                product_id=product_id,
                warehouse_id=warehouse_id,
                available_quantity=0,
                reserved_quantity=0,
                damaged_quantity=0,
                reorder_level=10,
            )
            self.repo.create(inv)
            self.db.flush()
            if for_update:
                inv = self.repo.get_inventory(product_id=product_id, warehouse_id=warehouse_id, for_update=True)
        return inv

    def adjust_inventory(
        self,
        req: InventoryAdjustRequest,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> InventoryAdjustResponse:
        self._verify_warehouse_access(current_user, req.warehouse_id)

        # Acquire row lock for safe adjustment
        inv = self.get_or_create_inventory(req.product_id, req.warehouse_id, for_update=True)
        previous_qty = inv.available_quantity
        tx_type = TransactionType.ADJUSTMENT
        adj_amount = 0

        adj_type = req.adjustment_type.upper().strip()
        if adj_type == "SET":
            if req.quantity < 0:
                raise BadRequestError("Inventory quantity cannot be negative")
            adj_amount = req.quantity - previous_qty
            inv.available_quantity = req.quantity
        elif adj_type == "INCREASE":
            if req.quantity <= 0:
                raise BadRequestError("Increase quantity must be positive")
            adj_amount = req.quantity
            inv.available_quantity += req.quantity
        elif adj_type == "DECREASE":
            if req.quantity <= 0:
                raise BadRequestError("Decrease quantity must be positive")
            if inv.available_quantity < req.quantity:
                raise InsufficientInventoryError(
                    f"Cannot decrease {req.quantity} units; only {inv.available_quantity} available"
                )
            adj_amount = -req.quantity
            inv.available_quantity -= req.quantity
        elif adj_type == "DAMAGE":
            if req.quantity <= 0:
                raise BadRequestError("Damage quantity must be positive")
            if inv.available_quantity < req.quantity:
                raise InsufficientInventoryError(
                    f"Cannot mark {req.quantity} units as damaged; only {inv.available_quantity} available"
                )
            adj_amount = -req.quantity
            inv.available_quantity -= req.quantity
            inv.damaged_quantity += req.quantity
            tx_type = TransactionType.DAMAGE
        else:
            raise BadRequestError(f"Unsupported adjustment type: {req.adjustment_type}")

        new_qty = inv.available_quantity

        # Create immutable inventory transaction record
        self.repo.create_transaction(
            product_id=req.product_id,
            warehouse_id=req.warehouse_id,
            transaction_type=tx_type,
            quantity=adj_amount,
            reference_entity="MANUAL_ADJUSTMENT",
            reference_id=f"ADJ-{inv.id}-{int(datetime.now(timezone.utc).timestamp())}",
            user_id=current_user.id,
            metadata_json={
                "reason": req.reason,
                "adjustment_type": adj_type,
                "previous_quantity": previous_qty,
                "new_quantity": new_qty,
            },
        )

        # Check low stock threshold & trigger notification
        if inv.available_quantity <= inv.reorder_level:
            self._notify_low_stock(inv)

        self.audit_service.log(
            action="INVENTORY_ADJUSTED",
            entity="INVENTORY",
            entity_id=str(inv.id),
            user_id=current_user.id,
            ip_address=ip_address,
            metadata_json={
                "product_id": req.product_id,
                "warehouse_id": req.warehouse_id,
                "previous_quantity": previous_qty,
                "new_quantity": new_qty,
                "reason": req.reason,
            },
        )

        self.db.commit()
        self.db.refresh(inv)

        return InventoryAdjustResponse(
            inventory=InventoryResponse.model_validate(inv),
            previous_quantity=previous_qty,
            new_quantity=new_qty,
            adjustment_amount=adj_amount,
            reason=req.reason,
            user_id=current_user.id,
            timestamp=datetime.now(timezone.utc),
        )

    def transfer_inventory(
        self,
        req: InventoryTransferRequest,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> InventoryTransferResponse:
        """
        Atomically transfers inventory between warehouses with row-level locks
        and dual transaction logging (TRANSFER_OUT + TRANSFER_IN).
        """
        if req.source_warehouse_id == req.destination_warehouse_id:
            raise InvalidInventoryTransferError("Source and destination warehouses cannot be the same")

        if req.quantity <= 0:
            raise BadRequestError("Transfer quantity must be greater than zero")

        # Verify manager authorization for source warehouse
        self._verify_warehouse_access(current_user, req.source_warehouse_id)

        # Verify destination warehouse is active
        dest_warehouse = self.warehouse_repo.get_by_id(req.destination_warehouse_id)
        if not dest_warehouse or dest_warehouse.status != WarehouseStatus.ACTIVE:
            raise InvalidInventoryTransferError("Destination warehouse does not exist or is inactive")

        # Lock rows in consistent order to prevent deadlock
        first_wh, second_wh = sorted([req.source_warehouse_id, req.destination_warehouse_id])
        self.get_or_create_inventory(req.product_id, first_wh, for_update=True)
        self.get_or_create_inventory(req.product_id, second_wh, for_update=True)

        source_inv = self.repo.get_inventory(req.product_id, req.source_warehouse_id, for_update=True)
        dest_inv = self.repo.get_inventory(req.product_id, req.destination_warehouse_id, for_update=True)

        if not source_inv or source_inv.available_quantity < req.quantity:
            avail = source_inv.available_quantity if source_inv else 0
            raise InsufficientInventoryError(
                f"Insufficient inventory at source warehouse. Requested: {req.quantity}, Available: {avail}"
            )

        # Execute balance update
        source_inv.available_quantity -= req.quantity
        dest_inv.available_quantity += req.quantity

        transfer_ref = f"TRF-{req.source_warehouse_id}-{req.destination_warehouse_id}-{int(datetime.now(timezone.utc).timestamp())}"

        # Create TRANSFER_OUT transaction
        self.repo.create_transaction(
            product_id=req.product_id,
            warehouse_id=req.source_warehouse_id,
            transaction_type=TransactionType.TRANSFER_OUT,
            quantity=-req.quantity,
            reference_entity="INVENTORY_TRANSFER",
            reference_id=transfer_ref,
            user_id=current_user.id,
            metadata_json={"destination_warehouse_id": req.destination_warehouse_id, "reason": req.reason},
        )

        # Create TRANSFER_IN transaction
        self.repo.create_transaction(
            product_id=req.product_id,
            warehouse_id=req.destination_warehouse_id,
            transaction_type=TransactionType.TRANSFER_IN,
            quantity=req.quantity,
            reference_entity="INVENTORY_TRANSFER",
            reference_id=transfer_ref,
            user_id=current_user.id,
            metadata_json={"source_warehouse_id": req.source_warehouse_id, "reason": req.reason},
        )

        # Check low stock at source
        if source_inv.available_quantity <= source_inv.reorder_level:
            self._notify_low_stock(source_inv)

        # Generate transfer notification
        self.notification_service.notify(
            user_id=current_user.id,
            type=NotificationType.INVENTORY_TRANSFER,
            title="Inventory Transfer Completed",
            message=f"Transferred {req.quantity} units of product ID {req.product_id} from warehouse {req.source_warehouse_id} to {req.destination_warehouse_id}.",
            reference_entity="INVENTORY_TRANSFER",
            reference_id=transfer_ref,
        )

        self.audit_service.log(
            action="INVENTORY_TRANSFERRED",
            entity="INVENTORY",
            entity_id=transfer_ref,
            user_id=current_user.id,
            ip_address=ip_address,
            metadata_json={
                "source_warehouse_id": req.source_warehouse_id,
                "destination_warehouse_id": req.destination_warehouse_id,
                "product_id": req.product_id,
                "quantity": req.quantity,
            },
        )

        self.db.commit()
        self.db.refresh(source_inv)
        self.db.refresh(dest_inv)

        return InventoryTransferResponse(
            product_id=req.product_id,
            source_warehouse_id=req.source_warehouse_id,
            destination_warehouse_id=req.destination_warehouse_id,
            quantity=req.quantity,
            source_available_quantity=source_inv.available_quantity,
            destination_available_quantity=dest_inv.available_quantity,
            message="Inventory successfully transferred",
        )

    def _notify_low_stock(self, inv: Inventory) -> None:
        """Trigger low stock notification to warehouse users & admins."""
        product = self.product_repo.get_by_id(inv.product_id)
        prod_name = product.name if product else f"ID {inv.product_id}"
        wh_name = inv.warehouse.name if inv.warehouse else f"Warehouse {inv.warehouse_id}"

        # Notify assigned managers
        manager_ids = self.warehouse_repo.get_warehouse_users(inv.warehouse_id)
        for uid in manager_ids:
            self.notification_service.notify(
                user_id=uid,
                type=NotificationType.LOW_STOCK,
                title=f"Low Stock Alert: {prod_name}",
                message=f"Product {prod_name} in {wh_name} has reached low stock: {inv.available_quantity} units remaining (reorder level: {inv.reorder_level}).",
                reference_entity="INVENTORY",
                reference_id=str(inv.id),
            )

    def list_inventory(self, current_user: User, **kwargs):
        # If warehouse manager or fulfillment agent, scope to assigned warehouses if not explicitly specified
        if current_user.role in [UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT]:
            assigned_ids = self.warehouse_repo.get_user_warehouse_ids(current_user.id)
            if kwargs.get("warehouse_id") and kwargs["warehouse_id"] not in assigned_ids:
                raise WarehouseAccessDeniedError(f"Access denied to warehouse {kwargs['warehouse_id']}")
        return self.repo.list_inventory(**kwargs)

    def get_product_inventory(self, product_id: int) -> List[Inventory]:
        product = self.product_repo.get_by_id(product_id)
        if not product:
            raise ResourceNotFoundError(f"Product with ID {product_id} not found")
        return self.repo.get_by_product_id(product_id)

    def get_low_stock(self, current_user: User, warehouse_id: Optional[int] = None) -> List[LowStockResponse]:
        if warehouse_id and current_user.role in [UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT]:
            self._verify_warehouse_access(current_user, warehouse_id)

        items = self.repo.get_low_stock_items(warehouse_id=warehouse_id)
        results = []
        for item in items:
            results.append(
                LowStockResponse(
                    inventory_id=item.id,
                    product_id=item.product_id,
                    product_sku=item.product.sku if item.product else "",
                    product_name=item.product.name if item.product else "",
                    warehouse_id=item.warehouse_id,
                    warehouse_name=item.warehouse.name if item.warehouse else "",
                    available_quantity=item.available_quantity,
                    reorder_level=item.reorder_level,
                    is_out_of_stock=(item.available_quantity == 0),
                )
            )
        return results
