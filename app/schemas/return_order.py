from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.return_order import ReturnStatus, ItemCondition
from app.schemas.auth import UserResponse
from app.schemas.product import ProductResponse


class ReturnItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)
    condition: ItemCondition = ItemCondition.GOOD


class ReturnCreate(BaseModel):
    order_id: int
    reason: str = Field(..., min_length=5, max_length=500)
    items: List[ReturnItemCreate] = Field(..., min_length=1)


class ReturnItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    condition: ItemCondition
    restocked: bool
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True


class ReturnStatusUpdateRequest(BaseModel):
    status: ReturnStatus
    admin_notes: Optional[str] = None


class ReturnResponse(BaseModel):
    id: int
    return_number: str
    order_id: int
    customer_id: int
    warehouse_id: int
    reason: str
    status: ReturnStatus
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[ReturnItemResponse] = []
    customer: Optional[UserResponse] = None

    class Config:
        from_attributes = True
