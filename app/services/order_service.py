import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.core.exceptions import (
    ResourceNotFoundError,
    BadRequestError,
    ForbiddenError,
    InsufficientInventoryError,
    InvalidOrderStatusError,
    ProductInactiveError,
    WarehouseAccessDeniedError,
)
from app.models.order import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentStatus,
    OrderStatusHistory,
    OrderAssignment,
)
from app.models.product import Product, ProductStatus
from app.models.warehouse import Warehouse, WarehouseStatus
from app.models.inventory import Inventory, TransactionType
from app.models.user import User, UserRole
from app.models.notification import NotificationType
from app.repositories.order_repository import OrderRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.warehouse_repository import WarehouseRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.schemas.order import (
    OrderCreate,
    OrderResponse,
    OrderStatusUpdateRequest,
    OrderAssignRequest,
    OrderCancelRequest,
    PaymentProcessRequest,
)

# Valid state machine transitions
ALLOWED_TRANSITIONS: Dict[OrderStatus, List[OrderStatus]] = {
    OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED, OrderStatus.FAILED],
    OrderStatus.CONFIRMED: [OrderStatus.PROCESSING, OrderStatus.CANCELLED, OrderStatus.FAILED],
    OrderStatus.PROCESSING: [OrderStatus.PACKED, OrderStatus.FAILED],
    OrderStatus.PACKED: [OrderStatus.SHIPPED, OrderStatus.FAILED],
    OrderStatus.SHIPPED: [OrderStatus.DELIVERED],
    OrderStatus.DELIVERED: [OrderStatus.RETURNED],
    OrderStatus.CANCELLED: [],
    OrderStatus.FAILED: [],
    OrderStatus.RETURNED: [],
}


class OrderService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OrderRepository(db)
        self.inventory_repo = InventoryRepository(db)
        self.product_repo = ProductRepository(db)
        self.warehouse_repo = WarehouseRepository(db)
        self.user_repo = UserRepository(db)
        self.audit_service = AuditService(db)
        self.notification_service = NotificationService(db)

    def _verify_warehouse_access(self, user: User, warehouse_id: int) -> None:
        if user.role == UserRole.ADMIN:
            return
        if not self.warehouse_repo.is_user_assigned(warehouse_id=warehouse_id, user_id=user.id):
            raise WarehouseAccessDeniedError(
                f"User '{user.username}' is not authorized for warehouse ID {warehouse_id}"
            )

    def _generate_order_number(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand_suffix = uuid.uuid4().hex[:6].upper()
        return f"ORD-{today_str}-{rand_suffix}"

    def create_order(
        self,
        req: OrderCreate,
        customer: User,
        ip_address: Optional[str] = None,
    ) -> Order:
        """
        Creates an order with transactional inventory reservation and row-level locking.
        Prevents negative stock and ensures concurrent safety.
        """
        # Validate warehouse
        warehouse = self.warehouse_repo.get_by_id(req.warehouse_id)
        if not warehouse or warehouse.status != WarehouseStatus.ACTIVE:
            raise BadRequestError(f"Warehouse ID {req.warehouse_id} does not exist or is inactive")

        if not req.items:
            raise BadRequestError("Order must contain at least one item")

        # To avoid deadlocks under concurrent requests, sort product IDs
        sorted_items = sorted(req.items, key=lambda x: x.product_id)

        subtotal = Decimal("0.00")
        total_discount = Decimal("0.00")
        total_tax = Decimal("0.00")
        order_items_to_create = []

        # Validate products & reserve inventory under row-level lock
        for item_in in sorted_items:
            product = self.product_repo.get_by_id(item_in.product_id)
            if not product:
                raise ResourceNotFoundError(f"Product ID {item_in.product_id} not found")

            # Inactive products cannot be added to new orders
            if product.status != ProductStatus.ACTIVE:
                raise ProductInactiveError(
                    f"Product '{product.name}' (SKU: {product.sku}) is inactive and cannot be ordered"
                )

            # Acquire row-level lock (SELECT ... FOR UPDATE)
            inv = self.inventory_repo.get_inventory(
                product_id=product.id,
                warehouse_id=warehouse.id,
                for_update=True,
            )

            if not inv or inv.available_quantity < item_in.quantity:
                available = inv.available_quantity if inv else 0
                raise InsufficientInventoryError(
                    f"Insufficient inventory for product SKU-{product.sku}. Requested: {item_in.quantity}, Available: {available}"
                )

            # Execute reservation
            inv.available_quantity -= item_in.quantity
            inv.reserved_quantity += item_in.quantity

            # Log RESERVATION inventory transaction
            self.inventory_repo.create_transaction(
                product_id=product.id,
                warehouse_id=warehouse.id,
                transaction_type=TransactionType.RESERVATION,
                quantity=item_in.quantity,
                reference_entity="ORDER",
                reference_id=None,  # updated after order number generation
                user_id=customer.id,
                metadata_json={"order_action": "ORDER_RESERVATION", "quantity": item_in.quantity},
            )

            # Check low-stock threshold
            if inv.available_quantity <= inv.reorder_level:
                self.notification_service.notify(
                    user_id=customer.id,
                    type=NotificationType.LOW_STOCK,
                    title=f"Low Stock Alert: {product.name}",
                    message=f"Product SKU {product.sku} reached low stock ({inv.available_quantity} units remaining) after order reservation.",
                    reference_entity="INVENTORY",
                    reference_id=str(inv.id),
                )

            # Calculate item financial amounts
            unit_price = product.price
            item_discount = item_in.discount or Decimal("0.00")
            item_subtotal = (unit_price * item_in.quantity) - item_discount
            # 5% tax example
            item_tax = (item_subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
            item_total = item_subtotal + item_tax

            subtotal += (unit_price * item_in.quantity)
            total_discount += item_discount
            total_tax += item_tax

            order_item = OrderItem(
                product_id=product.id,
                quantity=item_in.quantity,
                unit_price=unit_price,
                discount=item_discount,
                tax=item_tax,
                total=item_total,
            )
            order_items_to_create.append(order_item)

        order_number = self._generate_order_number()
        total_amount = subtotal - total_discount + total_tax
        delivery_date = req.expected_delivery_date or (datetime.now(timezone.utc) + timedelta(days=5))

        order = Order(
            order_number=order_number,
            customer_id=customer.id,
            warehouse_id=warehouse.id,
            subtotal=subtotal,
            discount=total_discount,
            tax=total_tax,
            total_amount=total_amount,
            status=OrderStatus.PENDING,
            payment_status=PaymentStatus.UNPAID,
            expected_delivery_date=delivery_date,
            notes=req.notes,
        )
        self.repo.create(order)
        self.db.flush()

        for item in order_items_to_create:
            item.order_id = order.id
            self.db.add(item)

        # Record Initial Status History
        self.repo.add_status_history(
            order_id=order.id,
            old_status=OrderStatus.PENDING,
            new_status=OrderStatus.PENDING,
            changed_by_id=customer.id,
            notes="Order created and inventory reserved",
        )

        # Customer Notification
        self.notification_service.notify(
            user_id=customer.id,
            type=NotificationType.ORDER_CREATED,
            title=f"Order {order.order_number} Created",
            message=f"Your order {order.order_number} for ${total_amount} has been successfully placed.",
            reference_entity="ORDER",
            reference_id=str(order.id),
        )

        # Audit Log
        self.audit_service.log(
            action="ORDER_CREATED",
            entity="ORDER",
            entity_id=str(order.id),
            user_id=customer.id,
            ip_address=ip_address,
            metadata_json={"order_number": order.order_number, "total_amount": str(total_amount)},
        )

        self.db.commit()
        return self.repo.get_by_id_detailed(order.id)

    def get_order(self, order_id: int, current_user: User) -> Order:
        order = self.repo.get_by_id_detailed(order_id)
        if not order:
            raise ResourceNotFoundError(f"Order with ID {order_id} not found")

        # Authorization check
        if current_user.role == UserRole.CUSTOMER and order.customer_id != current_user.id:
            raise ForbiddenError("You are not authorized to view this order")

        if current_user.role in [UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT]:
            self._verify_warehouse_access(current_user, order.warehouse_id)

        return order

    def update_order_status(
        self,
        order_id: int,
        req: OrderStatusUpdateRequest,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> Order:
        """
        Transition order status with state machine enforcement.
        """
        order = self.get_order(order_id, current_user)
        old_status = order.status
        new_status = req.status

        if new_status == old_status:
            return order

        allowed = ALLOWED_TRANSITIONS.get(old_status, [])
        if new_status not in allowed:
            raise InvalidOrderStatusError(
                f"Cannot transition order from '{old_status.value}' to '{new_status.value}'"
            )

        # Role checks for transitions
        if current_user.role == UserRole.CUSTOMER:
            if new_status != OrderStatus.CANCELLED:
                raise ForbiddenError("Customers can only cancel orders")

        # Fulfillment state transitions
        if new_status == OrderStatus.SHIPPED:
            # When shipped, convert reserved stock to permanent SALE
            for item in order.items:
                inv = self.inventory_repo.get_inventory(
                    product_id=item.product_id,
                    warehouse_id=order.warehouse_id,
                    for_update=True,
                )
                if inv:
                    inv.reserved_quantity = max(0, inv.reserved_quantity - item.quantity)
                self.inventory_repo.create_transaction(
                    product_id=item.product_id,
                    warehouse_id=order.warehouse_id,
                    transaction_type=TransactionType.SALE,
                    quantity=-item.quantity,
                    reference_entity="ORDER",
                    reference_id=order.order_number,
                    user_id=current_user.id,
                    metadata_json={"order_id": order.id, "unit_price": str(item.unit_price)},
                )

            self.notification_service.notify(
                user_id=order.customer_id,
                type=NotificationType.ORDER_SHIPPED,
                title=f"Order {order.order_number} Shipped",
                message=f"Your order {order.order_number} has been shipped from the warehouse.",
                reference_entity="ORDER",
                reference_id=str(order.id),
            )

        elif new_status == OrderStatus.DELIVERED:
            self.notification_service.notify(
                user_id=order.customer_id,
                type=NotificationType.ORDER_DELIVERED,
                title=f"Order {order.order_number} Delivered",
                message=f"Your order {order.order_number} has arrived safely.",
                reference_entity="ORDER",
                reference_id=str(order.id),
            )

        elif new_status == OrderStatus.CONFIRMED:
            self.notification_service.notify(
                user_id=order.customer_id,
                type=NotificationType.ORDER_CONFIRMED,
                title=f"Order {order.order_number} Confirmed",
                message=f"Your order {order.order_number} has been confirmed.",
                reference_entity="ORDER",
                reference_id=str(order.id),
            )

        elif new_status == OrderStatus.CANCELLED:
            # Release reserved inventory
            self._release_order_inventory(order, current_user)

        order.status = new_status
        self.repo.add_status_history(
            order_id=order.id,
            old_status=old_status,
            new_status=new_status,
            changed_by_id=current_user.id,
            notes=req.notes,
        )

        self.audit_service.log(
            action="ORDER_STATUS_CHANGED",
            entity="ORDER",
            entity_id=str(order.id),
            user_id=current_user.id,
            ip_address=ip_address,
            metadata_json={"old_status": old_status.value, "new_status": new_status.value, "notes": req.notes},
        )

        self.db.commit()
        return self.repo.get_by_id_detailed(order.id)

    def cancel_order(
        self,
        order_id: int,
        req: OrderCancelRequest,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> Order:
        """
        Cancel order and release reserved stock back into available inventory atomically.
        """
        order = self.get_order(order_id, current_user)

        # Customers can only cancel in PENDING or CONFIRMED
        if current_user.role == UserRole.CUSTOMER and order.status not in [OrderStatus.PENDING, OrderStatus.CONFIRMED]:
            raise InvalidOrderStatusError(
                f"Orders in state '{order.status.value}' cannot be cancelled by customers as fulfillment has begun"
            )

        if order.status in [OrderStatus.CANCELLED, OrderStatus.DELIVERED, OrderStatus.RETURNED]:
            raise InvalidOrderStatusError(f"Cannot cancel order in state '{order.status.value}'")

        old_status = order.status
        order.status = OrderStatus.CANCELLED

        # Release reserved inventory
        self._release_order_inventory(order, current_user)

        self.repo.add_status_history(
            order_id=order.id,
            old_status=old_status,
            new_status=OrderStatus.CANCELLED,
            changed_by_id=current_user.id,
            notes=req.reason,
        )

        self.notification_service.notify(
            user_id=order.customer_id,
            type=NotificationType.ORDER_CANCELLED,
            title=f"Order {order.order_number} Cancelled",
            message=f"Order {order.order_number} has been cancelled. Reserved inventory has been released.",
            reference_entity="ORDER",
            reference_id=str(order.id),
        )

        self.audit_service.log(
            action="ORDER_CANCELLED",
            entity="ORDER",
            entity_id=str(order.id),
            user_id=current_user.id,
            ip_address=ip_address,
            metadata_json={"reason": req.reason, "order_number": order.order_number},
        )

        self.db.commit()
        return self.repo.get_by_id_detailed(order.id)

    def _release_order_inventory(self, order: Order, user: User) -> None:
        """Release reserved units back to available quantity."""
        for item in order.items:
            inv = self.inventory_repo.get_inventory(
                product_id=item.product_id,
                warehouse_id=order.warehouse_id,
                for_update=True,
            )
            if inv:
                qty_to_release = min(inv.reserved_quantity, item.quantity)
                inv.reserved_quantity -= qty_to_release
                inv.available_quantity += qty_to_release

                self.inventory_repo.create_transaction(
                    product_id=item.product_id,
                    warehouse_id=order.warehouse_id,
                    transaction_type=TransactionType.RELEASE,
                    quantity=qty_to_release,
                    reference_entity="ORDER",
                    reference_id=order.order_number,
                    user_id=user.id,
                    metadata_json={"order_id": order.id, "reason": "Order cancelled, releasing reserved stock"},
                )

    def assign_order(
        self,
        order_id: int,
        req: OrderAssignRequest,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> Order:
        """
        Assign an order to a fulfillment agent.
        Rules:
        - Inactive agents cannot receive orders.
        - Agent must be authorized for order's warehouse.
        - Customers cannot assign orders.
        - Assignment changes audited.
        - Reassignment generates notification.
        """
        if current_user.role == UserRole.CUSTOMER:
            raise ForbiddenError("Customers are not permitted to assign orders")

        order = self.get_order(order_id, current_user)

        target_agent = self.user_repo.get_by_id(req.agent_id)
        if not target_agent:
            raise ResourceNotFoundError(f"Agent with ID {req.agent_id} not found")

        if not target_agent.is_active:
            raise BadRequestError("Cannot assign order to an inactive agent")

        if target_agent.role not in [UserRole.FULFILLMENT_AGENT, UserRole.WAREHOUSE_MANAGER, UserRole.ADMIN]:
            raise BadRequestError("Assigned user must be a fulfillment agent or manager")

        # Verify target agent is authorized for this warehouse
        if target_agent.role != UserRole.ADMIN:
            if not self.warehouse_repo.is_user_assigned(warehouse_id=order.warehouse_id, user_id=target_agent.id):
                raise WarehouseAccessDeniedError(
                    f"Agent '{target_agent.username}' is not authorized for warehouse ID {order.warehouse_id}"
                )

        previous_agent_id = order.assigned_agent_id
        order.assigned_agent_id = target_agent.id

        self.repo.add_assignment(
            order_id=order.id,
            agent_id=target_agent.id,
            assigned_by_id=current_user.id,
            notes=req.notes,
        )

        # Notify assigned agent
        self.notification_service.notify(
            user_id=target_agent.id,
            type=NotificationType.ORDER_ASSIGNED,
            title=f"Order {order.order_number} Assigned",
            message=f"You have been assigned to fulfill order {order.order_number}.",
            reference_entity="ORDER",
            reference_id=str(order.id),
        )

        self.audit_service.log(
            action="ORDER_ASSIGNED",
            entity="ORDER",
            entity_id=str(order.id),
            user_id=current_user.id,
            ip_address=ip_address,
            metadata_json={
                "previous_agent_id": previous_agent_id,
                "new_agent_id": target_agent.id,
                "order_number": order.order_number,
            },
        )

        self.db.commit()
        return self.repo.get_by_id_detailed(order.id)

    def process_payment(
        self,
        order_id: int,
        req: PaymentProcessRequest,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> Order:
        """Process order payment."""
        order = self.get_order(order_id, current_user)
        if order.status == OrderStatus.CANCELLED:
            raise BadRequestError("Cannot process payment for a cancelled order")

        order.payment_status = PaymentStatus.PAID
        if order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CONFIRMED
            self.repo.add_status_history(
                order_id=order.id,
                old_status=OrderStatus.PENDING,
                new_status=OrderStatus.CONFIRMED,
                changed_by_id=current_user.id,
                notes="Payment received, order confirmed",
            )

        self.audit_service.log(
            action="PAYMENT_RECEIVED",
            entity="ORDER",
            entity_id=str(order.id),
            user_id=current_user.id,
            ip_address=ip_address,
            metadata_json={"payment_method": req.payment_method, "amount": str(order.total_amount)},
        )

        self.db.commit()
        return self.repo.get_by_id_detailed(order.id)

    def list_orders(self, current_user: User, **kwargs):
        if current_user.role == UserRole.CUSTOMER:
            kwargs["customer_id"] = current_user.id
        elif current_user.role in [UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT]:
            assigned_ids = self.warehouse_repo.get_warehouse_users(current_user.id)
            user_wh_ids = self.user_repo.get_user_warehouse_ids(current_user.id)
            if kwargs.get("warehouse_id"):
                if kwargs["warehouse_id"] not in user_wh_ids:
                    raise WarehouseAccessDeniedError(f"Access denied to warehouse ID {kwargs['warehouse_id']}")
            else:
                kwargs["warehouse_ids"] = user_wh_ids

        return self.repo.list_orders(**kwargs)
