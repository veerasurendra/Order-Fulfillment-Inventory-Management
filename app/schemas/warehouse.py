from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.warehouse import WarehouseStatus


class WarehouseBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    location: str = Field(..., min_length=2, max_length=255)
    capacity: int = Field(default=10000, gt=0)
    status: WarehouseStatus = WarehouseStatus.ACTIVE


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    location: Optional[str] = Field(None, min_length=2, max_length=255)
    capacity: Optional[int] = Field(None, gt=0)
    status: Optional[WarehouseStatus] = None


class WarehouseUserAssignment(BaseModel):
    user_id: int


class WarehouseResponse(WarehouseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
