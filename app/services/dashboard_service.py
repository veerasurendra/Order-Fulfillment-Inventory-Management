from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.inventory import Inventory
from app.models.warehouse import Warehouse
from app.models.user import User, UserRole
from app.repositories.warehouse_repository import WarehouseRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.dashboard import (
    AdminDashboardResponse,
    WarehouseDashboardResponse,
    CustomerDashboardResponse,
)
from app.schemas.order import OrderResponse
from app.schemas.inventory import LowStockResponse
from app.core.exceptions import ResourceNotFoundError, WarehouseAccessDeniedError


class DashboardService:
    def __init__(self, db: Session):
        self.db = db
        self.warehouse_repo = WarehouseRepository(db)
        self.inventory_repo = InventoryRepository(db)
        self.order_repo = OrderRepository(db)

    def get_admin_dashboard(self) -> AdminDashboardResponse:
        total_orders = self.db.scalar(select(func.count(Order.id))) or 0
        pending_orders = self.db.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING)) or 0
        processing_orders = self.db.scalar(
            select(func.count(Order.id)).where(Order.status.in_([OrderStatus.CONFIRMED, OrderStatus.PROCESSING, OrderStatus.PACKED]))
        ) or 0
        completed_orders = self.db.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.DELIVERED)) or 0
        cancelled_orders = self.db.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.CANCELLED)) or 0

        # Total revenue from paid orders
        rev = self.db.scalar(select(func.sum(Order.total_amount)).where(Order.payment_status == PaymentStatus.PAID))
        total_revenue = Decimal(rev or "0.00")

        # Inventory metrics
        low_stock_count = self.db.scalar(
            select(func.count(Inventory.id)).where(Inventory.available_quantity <= Inventory.reorder_level)
        ) or 0
        out_of_stock_count = self.db.scalar(
            select(func.count(Inventory.id)).where(Inventory.available_quantity == 0)
        ) or 0

        # Recent 5 orders
        recent_orders_list, _ = self.order_repo.list_orders(page=1, page_size=5)
        recent_orders = [OrderResponse.model_validate(o) for o in recent_orders_list]

        return AdminDashboardResponse(
            total_orders=total_orders,
            pending_orders=pending_orders,
            processing_orders=processing_orders,
            completed_orders=completed_orders,
            cancelled_orders=cancelled_orders,
            total_revenue=total_revenue,
            low_stock_products_count=low_stock_count,
            out_of_stock_products_count=out_of_stock_count,
            recent_orders=recent_orders,
        )

    def get_warehouse_dashboard(self, warehouse_id: int, current_user: User) -> WarehouseDashboardResponse:
        warehouse = self.warehouse_repo.get_by_id(warehouse_id)
        if not warehouse:
            raise ResourceNotFoundError(f"Warehouse ID {warehouse_id} not found")

        if current_user.role != UserRole.ADMIN:
            if not self.warehouse_repo.is_user_assigned(warehouse_id, current_user.id):
                raise WarehouseAccessDeniedError(f"Access denied to warehouse ID {warehouse_id}")

        inv_stats = self.db.execute(
            select(
                func.count(Inventory.id),
                func.sum(Inventory.available_quantity),
                func.sum(Inventory.reserved_quantity),
            ).where(Inventory.warehouse_id == warehouse_id)
        ).first()

        total_items = inv_stats[0] or 0
        total_avail = inv_stats[1] or 0
        total_reserved = inv_stats[2] or 0

        pending_fulfillment = self.db.scalar(
            select(func.count(Order.id)).where(
                Order.warehouse_id == warehouse_id,
                Order.status.in_([OrderStatus.PENDING, OrderStatus.CONFIRMED]),
            )
        ) or 0

        processing = self.db.scalar(
            select(func.count(Order.id)).where(
                Order.warehouse_id == warehouse_id,
                Order.status.in_([OrderStatus.PROCESSING, OrderStatus.PACKED]),
            )
        ) or 0

        # Low stock items for this warehouse
        low_items_raw = self.inventory_repo.get_low_stock_items(warehouse_id=warehouse_id)
        low_items = [
            LowStockResponse(
                inventory_id=i.id,
                product_id=i.product_id,
                product_sku=i.product.sku if i.product else "",
                product_name=i.product.name if i.product else "",
                warehouse_id=i.warehouse_id,
                warehouse_name=warehouse.name,
                available_quantity=i.available_quantity,
                reorder_level=i.reorder_level,
                is_out_of_stock=(i.available_quantity == 0),
            )
            for i in low_items_raw
        ]

        # Today's shipments
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        todays_shipments = self.db.scalar(
            select(func.count(Order.id)).where(
                Order.warehouse_id == warehouse_id,
                Order.status.in_([OrderStatus.SHIPPED, OrderStatus.DELIVERED]),
                Order.updated_at >= today_start,
            )
        ) or 0

        return WarehouseDashboardResponse(
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.name,
            total_inventory_items=total_items,
            total_units_available=total_avail,
            total_units_reserved=total_reserved,
            pending_fulfillment=pending_fulfillment,
            processing_orders=processing,
            low_stock_items=low_items,
            todays_shipments_count=todays_shipments,
        )

    def get_customer_dashboard(self, customer_id: int) -> CustomerDashboardResponse:
        total_orders = self.db.scalar(select(func.count(Order.id)).where(Order.customer_id == customer_id)) or 0
        active_orders = self.db.scalar(
            select(func.count(Order.id)).where(
                Order.customer_id == customer_id,
                Order.status.in_([OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING, OrderStatus.PACKED, OrderStatus.SHIPPED]),
            )
        ) or 0
        completed_orders = self.db.scalar(
            select(func.count(Order.id)).where(Order.customer_id == customer_id, Order.status == OrderStatus.DELIVERED)
        ) or 0
        cancelled_orders = self.db.scalar(
            select(func.count(Order.id)).where(Order.customer_id == customer_id, Order.status == OrderStatus.CANCELLED)
        ) or 0

        spending = self.db.scalar(
            select(func.sum(Order.total_amount)).where(
                Order.customer_id == customer_id,
                Order.payment_status == PaymentStatus.PAID,
            )
        )
        total_spending = Decimal(spending or "0.00")

        recent_orders_list, _ = self.order_repo.list_orders(customer_id=customer_id, page=1, page_size=5)
        recent_orders = [OrderResponse.model_validate(o) for o in recent_orders_list]

        return CustomerDashboardResponse(
            total_orders=total_orders,
            active_orders=active_orders,
            completed_orders=completed_orders,
            cancelled_orders=cancelled_orders,
            total_spending=total_spending,
            recent_orders=recent_orders,
        )
