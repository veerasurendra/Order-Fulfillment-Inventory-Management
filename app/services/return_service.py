import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from app.core.exceptions import (
    ResourceNotFoundError,
    BadRequestError,
    ForbiddenError,
    InvalidReturnStatusError,
    WarehouseAccessDeniedError,
)
from app.models.return_order import ReturnOrder, ReturnItem, ReturnStatus, ItemCondition
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole
from app.models.inventory import TransactionType
from app.models.notification import NotificationType
from app.repositories.return_repository import ReturnRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.warehouse_repository import WarehouseRepository
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.schemas.return_order import ReturnCreate, ReturnStatusUpdateRequest

ALLOWED_RETURN_TRANSITIONS: Dict[ReturnStatus, List[ReturnStatus]] = {
    ReturnStatus.REQUESTED: [ReturnStatus.APPROVED, ReturnStatus.REJECTED],
    ReturnStatus.APPROVED: [ReturnStatus.RECEIVED],
    ReturnStatus.RECEIVED: [ReturnStatus.REFUNDED],
    ReturnStatus.REJECTED: [],
    ReturnStatus.REFUNDED: [],
}


class ReturnService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReturnRepository(db)
        self.order_repo = OrderRepository(db)
        self.inventory_repo = InventoryRepository(db)
        self.warehouse_repo = WarehouseRepository(db)
        self.audit_service = AuditService(db)
        self.notification_service = NotificationService(db)

    def _generate_return_number(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand_suffix = uuid.uuid4().hex[:6].upper()
        return f"RET-{today_str}-{rand_suffix}"

    def create_return_request(
        self,
        req: ReturnCreate,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> ReturnOrder:
        order = self.order_repo.get_by_id_detailed(req.order_id)
        if not order:
            raise ResourceNotFoundError(f"Order with ID {req.order_id} not found")

        if current_user.role == UserRole.CUSTOMER and order.customer_id != current_user.id:
            raise ForbiddenError("You can only request returns for your own orders")

        # Returns only eligible for DELIVERED orders
        if order.status != OrderStatus.DELIVERED:
            raise BadRequestError(
                f"Returns can only be requested for DELIVERED orders. Current order status: {order.status.value}"
            )

        if not req.items:
            raise BadRequestError("Return request must specify at least one item")

        # Validate that returned items were actually in the order and quantities match
        order_item_map = {item.product_id: item.quantity for item in order.items}
        for r_item in req.items:
            if r_item.product_id not in order_item_map:
                raise BadRequestError(f"Product ID {r_item.product_id} was not part of this order")
            if r_item.quantity > order_item_map[r_item.product_id]:
                raise BadRequestError(
                    f"Return quantity ({r_item.quantity}) exceeds ordered quantity ({order_item_map[r_item.product_id]})"
                )

        return_number = self._generate_return_number()
        return_order = ReturnOrder(
            return_number=return_number,
            order_id=order.id,
            customer_id=order.customer_id,
            warehouse_id=order.warehouse_id,
            reason=req.reason.strip(),
            status=ReturnStatus.REQUESTED,
        )
        self.repo.create(return_order)
        self.db.flush()

        for item_in in req.items:
            return_item = ReturnItem(
                return_id=return_order.id,
                product_id=item_in.product_id,
                quantity=item_in.quantity,
                condition=item_in.condition,
                restocked=False,
            )
            self.db.add(return_item)

        self.notification_service.notify(
            user_id=order.customer_id,
            type=NotificationType.RETURN_REQUESTED,
            title=f"Return {return_order.return_number} Requested",
            message=f"Your return request for order {order.order_number} has been submitted for review.",
            reference_entity="RETURN",
            reference_id=str(return_order.id),
        )

        self.audit_service.log(
            action="RETURN_CREATED",
            entity="RETURN",
            entity_id=str(return_order.id),
            user_id=current_user.id,
            ip_address=ip_address,
            metadata_json={"return_number": return_order.return_number, "order_id": order.id},
        )

        self.db.commit()
        return self.repo.get_by_id_detailed(return_order.id)

    def get_return(self, return_id: int, current_user: User) -> ReturnOrder:
        ret = self.repo.get_by_id_detailed(return_id)
        if not ret:
            raise ResourceNotFoundError(f"Return request with ID {return_id} not found")

        if current_user.role == UserRole.CUSTOMER and ret.customer_id != current_user.id:
            raise ForbiddenError("You are not authorized to view this return request")

        if current_user.role in [UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT]:
            if not self.warehouse_repo.is_user_assigned(ret.warehouse_id, current_user.id):
                raise WarehouseAccessDeniedError(f"Access denied to warehouse ID {ret.warehouse_id}")

        return ret

    def update_return_status(
        self,
        return_id: int,
        req: ReturnStatusUpdateRequest,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> ReturnOrder:
        if current_user.role == UserRole.CUSTOMER:
            raise ForbiddenError("Customers cannot modify return statuses")

        ret = self.get_return(return_id, current_user)
        old_status = ret.status
        new_status = req.status

        if new_status == old_status:
            return ret

        allowed = ALLOWED_RETURN_TRANSITIONS.get(old_status, [])
        if new_status not in allowed:
            raise InvalidReturnStatusError(
                f"Cannot transition return from '{old_status.value}' to '{new_status.value}'"
            )

        if req.admin_notes:
            ret.admin_notes = req.admin_notes

        # If return is approved
        if new_status == ReturnStatus.APPROVED:
            self.notification_service.notify(
                user_id=ret.customer_id,
                type=NotificationType.RETURN_APPROVED,
                title=f"Return {ret.return_number} Approved",
                message=f"Your return request {ret.return_number} has been approved. Please ship the items back.",
                reference_entity="RETURN",
                reference_id=str(ret.id),
            )
            self.audit_service.log(
                action="RETURN_APPROVED",
                entity="RETURN",
                entity_id=str(ret.id),
                user_id=current_user.id,
                ip_address=ip_address,
                metadata_json={"return_number": ret.return_number},
            )

        # If return is received at warehouse -> restock inventory!
        elif new_status == ReturnStatus.RECEIVED:
            for item in ret.items:
                if not item.restocked:
                    inv = self.inventory_repo.get_inventory(
                        product_id=item.product_id,
                        warehouse_id=ret.warehouse_id,
                        for_update=True,
                    )
                    if not inv:
                        inv = Inventory(
                            product_id=item.product_id,
                            warehouse_id=ret.warehouse_id,
                            available_quantity=0,
                            reserved_quantity=0,
                            damaged_quantity=0,
                            reorder_level=10,
                        )
                        self.inventory_repo.create(inv)
                        self.db.flush()

                    if item.condition == ItemCondition.GOOD:
                        inv.available_quantity += item.quantity
                    else:
                        inv.damaged_quantity += item.quantity

                    item.restocked = True

                    # Immutable transaction
                    self.inventory_repo.create_transaction(
                        product_id=item.product_id,
                        warehouse_id=ret.warehouse_id,
                        transaction_type=TransactionType.RETURN,
                        quantity=item.quantity,
                        reference_entity="RETURN",
                        reference_id=ret.return_number,
                        user_id=current_user.id,
                        metadata_json={
                            "condition": item.condition.value,
                            "return_id": ret.id,
                        },
                    )

        ret.status = new_status
        self.db.commit()
        return self.repo.get_by_id_detailed(ret.id)

    def list_returns(self, current_user: User, **kwargs):
        if current_user.role == UserRole.CUSTOMER:
            kwargs["customer_id"] = current_user.id
        elif current_user.role in [UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT]:
            user_wh_ids = self.warehouse_repo.get_warehouse_users(current_user.id)
            if kwargs.get("warehouse_id"):
                if kwargs["warehouse_id"] not in user_wh_ids:
                    raise WarehouseAccessDeniedError(f"Access denied to warehouse {kwargs['warehouse_id']}")
            else:
                kwargs["warehouse_ids"] = user_wh_ids

        return self.repo.list_returns(**kwargs)
