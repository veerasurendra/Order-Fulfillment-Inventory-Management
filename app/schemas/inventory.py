from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.models.inventory import TransactionType
from app.schemas.product import ProductResponse
from app.schemas.warehouse import WarehouseResponse


class InventoryResponse(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    available_quantity: int
    reserved_quantity: int
    damaged_quantity: int
    reorder_level: int
    updated_at: datetime
    product: Optional[ProductResponse] = None
    warehouse: Optional[WarehouseResponse] = None

    class Config:
        from_attributes = True


class InventoryAdjustRequest(BaseModel):
    product_id: int
    warehouse_id: int
    adjustment_type: str = Field("SET", description="SET, INCREASE, DECREASE, or DAMAGE")
    quantity: int = Field(..., description="Target quantity if SET, or quantity to add/remove")
    reason: str = Field(..., min_length=3, max_length=255)


class InventoryAdjustResponse(BaseModel):
    inventory: InventoryResponse
    previous_quantity: int
    new_quantity: int
    adjustment_amount: int
    reason: str
    user_id: Optional[int] = None
    timestamp: datetime


class InventoryTransferRequest(BaseModel):
    source_warehouse_id: int
    destination_warehouse_id: int
    product_id: int
    quantity: int = Field(..., gt=0)
    reason: Optional[str] = "Inter-warehouse inventory rebalancing"


class InventoryTransferResponse(BaseModel):
    product_id: int
    source_warehouse_id: int
    destination_warehouse_id: int
    quantity: int
    source_available_quantity: int
    destination_available_quantity: int
    message: str


class InventoryTransactionResponse(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    transaction_type: TransactionType
    quantity: int
    reference_entity: Optional[str] = None
    reference_id: Optional[str] = None
    user_id: Optional[int] = None
    timestamp: datetime
    metadata_json: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class LowStockResponse(BaseModel):
    inventory_id: int
    product_id: int
    product_sku: str
    product_name: str
    warehouse_id: int
    warehouse_name: str
    available_quantity: int
    reorder_level: int
    is_out_of_stock: bool
