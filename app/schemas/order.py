from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.order import OrderStatus, PaymentStatus
from app.schemas.auth import UserResponse
from app.schemas.product import ProductResponse
from app.schemas.warehouse import WarehouseResponse


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)


class OrderCreate(BaseModel):
    warehouse_id: int
    items: List[OrderItemCreate] = Field(..., min_length=1)
    notes: Optional[str] = None
    expected_delivery_date: Optional[datetime] = None


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True


class OrderStatusHistoryResponse(BaseModel):
    id: int
    old_status: OrderStatus
    new_status: OrderStatus
    changed_by_id: Optional[int] = None
    notes: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class OrderAssignmentResponse(BaseModel):
    id: int
    agent_id: int
    assigned_by_id: Optional[int] = None
    notes: Optional[str] = None
    assigned_at: datetime
    agent: Optional[UserResponse] = None

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: int
    order_number: str
    customer_id: int
    warehouse_id: int
    assigned_agent_id: Optional[int] = None
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total_amount: Decimal
    status: OrderStatus
    payment_status: PaymentStatus
    expected_delivery_date: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse] = []
    customer: Optional[UserResponse] = None
    assigned_agent: Optional[UserResponse] = None
    warehouse: Optional[WarehouseResponse] = None
    status_history: Optional[List[OrderStatusHistoryResponse]] = []

    class Config:
        from_attributes = True


class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatus
    notes: Optional[str] = None


class OrderAssignRequest(BaseModel):
    agent_id: int
    notes: Optional[str] = None


class OrderCancelRequest(BaseModel):
    reason: Optional[str] = "Customer requested cancellation"


class PaymentProcessRequest(BaseModel):
    payment_method: str = "CREDIT_CARD"
    amount: Optional[Decimal] = None
