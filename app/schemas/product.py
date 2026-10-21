from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field
from app.models.product import ProductStatus


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    sku: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    category_id: Optional[int] = None
    price: Decimal = Field(..., gt=0, decimal_places=2)
    cost_price: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    status: ProductStatus = ProductStatus.ACTIVE


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    category_id: Optional[int] = None
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    cost_price: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    status: Optional[ProductStatus] = None


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    category: Optional[CategoryResponse] = None

    class Config:
        from_attributes = True
