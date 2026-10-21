from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, Request, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.dependencies.auth import get_current_user, require_role
from app.api.dependencies.pagination import PaginationParams
from app.models.user import User, UserRole
from app.models.product import ProductStatus
from app.services.product_service import ProductService
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    CategoryCreate,
    CategoryResponse,
)
from app.schemas.common import SuccessResponse, PaginatedResponse

router = APIRouter(prefix="/products", tags=["Product Management"])


@router.post("", response_model=SuccessResponse[ProductResponse], status_code=status.HTTP_201_CREATED)
def create_product(
    req: ProductCreate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: Create a new product with unique SKU."""
    service = ProductService(db)
    client_ip = request.client.host if request.client else None
    product = service.create_product(req, user_id=current_user.id, ip_address=client_ip)
    return SuccessResponse(data=ProductResponse.model_validate(product), message="Product created successfully")


@router.get("", response_model=PaginatedResponse[ProductResponse])
def list_products(
    search: Optional[str] = Query(None, description="Search by name, SKU, or description"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    status: Optional[ProductStatus] = Query(None, description="Filter by status (ACTIVE / INACTIVE)"),
    min_price: Optional[Decimal] = Query(None, description="Minimum price filter"),
    max_price: Optional[Decimal] = Query(None, description="Maximum price filter"),
    sort_by: str = Query("id", description="Sort field (id, name, price, created_at)"),
    sort_order: str = Query("asc", description="Sort order (asc / desc)"),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """List products with server-side pagination, searching, and filtering."""
    service = ProductService(db)
    items, meta = service.list_products(
        search=search,
        category_id=category_id,
        status=status,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        sort_order=sort_order,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse(
        data=[ProductResponse.model_validate(p) for p in items],
        pagination=meta,
    )


@router.get("/categories", response_model=SuccessResponse[List[CategoryResponse]])
def list_categories(db: Session = Depends(get_db)):
    """List all product categories."""
    service = ProductService(db)
    categories = service.list_categories()
    return SuccessResponse(data=[CategoryResponse.model_validate(c) for c in categories])


@router.post("/categories", response_model=SuccessResponse[CategoryResponse], status_code=status.HTTP_201_CREATED)
def create_category(
    req: CategoryCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: Create a new category."""
    service = ProductService(db)
    cat = service.create_category(req)
    return SuccessResponse(data=CategoryResponse.model_validate(cat), message="Category created successfully")


@router.get("/{id}", response_model=SuccessResponse[ProductResponse])
def get_product(
    id: int,
    db: Session = Depends(get_db),
):
    """Get single product details by ID."""
    service = ProductService(db)
    product = service.get_product(id)
    return SuccessResponse(data=ProductResponse.model_validate(product))


@router.put("/{id}", response_model=SuccessResponse[ProductResponse])
def update_product(
    id: int,
    req: ProductUpdate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: Update product details."""
    service = ProductService(db)
    client_ip = request.client.host if request.client else None
    product = service.update_product(id, req, user_id=current_user.id, ip_address=client_ip)
    return SuccessResponse(data=ProductResponse.model_validate(product), message="Product updated successfully")


@router.patch("/{id}/activate", response_model=SuccessResponse[ProductResponse])
def activate_product(
    id: int,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: Activate product to allow new orders."""
    service = ProductService(db)
    client_ip = request.client.host if request.client else None
    product = service.activate_product(id, user_id=current_user.id, ip_address=client_ip)
    return SuccessResponse(data=ProductResponse.model_validate(product), message="Product activated successfully")


@router.patch("/{id}/deactivate", response_model=SuccessResponse[ProductResponse])
def deactivate_product(
    id: int,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: Deactivate product to prevent addition to new orders."""
    service = ProductService(db)
    client_ip = request.client.host if request.client else None
    product = service.deactivate_product(id, user_id=current_user.id, ip_address=client_ip)
    return SuccessResponse(data=ProductResponse.model_validate(product), message="Product deactivated successfully")
