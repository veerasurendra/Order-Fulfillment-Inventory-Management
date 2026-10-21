from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel
from app.schemas.order import OrderResponse
from app.schemas.inventory import LowStockResponse


class AdminDashboardResponse(BaseModel):
    total_orders: int
    pending_orders: int
    processing_orders: int
    completed_orders: int
    cancelled_orders: int
    total_revenue: Decimal
    low_stock_products_count: int
    out_of_stock_products_count: int
    recent_orders: List[OrderResponse] = []


class WarehouseDashboardResponse(BaseModel):
    warehouse_id: int
    warehouse_name: str
    total_inventory_items: int
    total_units_available: int
    total_units_reserved: int
    pending_fulfillment: int
    processing_orders: int
    low_stock_items: List[LowStockResponse] = []
    todays_shipments_count: int


class CustomerDashboardResponse(BaseModel):
    total_orders: int
    active_orders: int
    completed_orders: int
    cancelled_orders: int
    total_spending: Decimal
    recent_orders: List[OrderResponse] = []
