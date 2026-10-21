from typing import Optional, List
from fastapi import APIRouter, Depends, Request, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.dependencies.auth import get_current_user, require_role
from app.api.dependencies.pagination import PaginationParams
from app.models.user import User, UserRole
from app.models.warehouse import WarehouseStatus
from app.services.warehouse_service import WarehouseService
from app.schemas.warehouse import (
    WarehouseCreate,
    WarehouseUpdate,
    WarehouseResponse,
    WarehouseUserAssignment,
)
from app.schemas.common import SuccessResponse, PaginatedResponse, MessageResponse

router = APIRouter(prefix="/warehouses", tags=["Warehouse Management"])


@router.post("", response_model=SuccessResponse[WarehouseResponse], status_code=status.HTTP_201_CREATED)
def create_warehouse(
    req: WarehouseCreate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: Create a new warehouse."""
    service = WarehouseService(db)
    client_ip = request.client.host if request.client else None
    wh = service.create_warehouse(req, user_id=current_user.id, ip_address=client_ip)
    return SuccessResponse(data=WarehouseResponse.model_validate(wh), message="Warehouse created successfully")


@router.get("", response_model=PaginatedResponse[WarehouseResponse])
def list_warehouses(
    status: Optional[WarehouseStatus] = Query(None, description="Filter by status (ACTIVE / INACTIVE)"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List warehouses scoped to user's authorization level."""
    service = WarehouseService(db)
    items, meta = service.list_warehouses(
        current_user=current_user,
        status=status,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse(
        data=[WarehouseResponse.model_validate(w) for w in items],
        pagination=meta,
    )


@router.get("/{id}", response_model=SuccessResponse[WarehouseResponse])
def get_warehouse(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get warehouse details by ID with authorization verification."""
    service = WarehouseService(db)
    wh = service.get_warehouse(id, current_user=current_user)
    return SuccessResponse(data=WarehouseResponse.model_validate(wh))


@router.put("/{id}", response_model=SuccessResponse[WarehouseResponse])
def update_warehouse(
    id: int,
    req: WarehouseUpdate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
    db: Session = Depends(get_db),
):
    """Update warehouse details (Admin or authorized Warehouse Manager)."""
    service = WarehouseService(db)
    client_ip = request.client.host if request.client else None
    wh = service.update_warehouse(id, req, current_user=current_user, ip_address=client_ip)
    return SuccessResponse(data=WarehouseResponse.model_validate(wh), message="Warehouse updated successfully")


@router.patch("/{id}/activate", response_model=SuccessResponse[WarehouseResponse])
def activate_warehouse(
    id: int,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: Activate warehouse."""
    service = WarehouseService(db)
    client_ip = request.client.host if request.client else None
    wh = service.activate_warehouse(id, current_user=current_user, ip_address=client_ip)
    return SuccessResponse(data=WarehouseResponse.model_validate(wh), message="Warehouse activated successfully")


@router.patch("/{id}/deactivate", response_model=SuccessResponse[WarehouseResponse])
def deactivate_warehouse(
    id: int,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: Deactivate warehouse."""
    service = WarehouseService(db)
    client_ip = request.client.host if request.client else None
    wh = service.deactivate_warehouse(id, current_user=current_user, ip_address=client_ip)
    return SuccessResponse(data=WarehouseResponse.model_validate(wh), message="Warehouse deactivated successfully")


@router.post("/{id}/users", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def assign_user_to_warehouse(
    id: int,
    req: WarehouseUserAssignment,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: Assign a manager or fulfillment agent to a warehouse."""
    service = WarehouseService(db)
    service.assign_user(warehouse_id=id, target_user_id=req.user_id, current_user=current_user)
    return MessageResponse(message=f"User {req.user_id} assigned to warehouse {id} successfully")


@router.delete("/{id}/users/{user_id}", response_model=MessageResponse)
def unassign_user_from_warehouse(
    id: int,
    user_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: Remove a user's authorization assignment from a warehouse."""
    service = WarehouseService(db)
    service.unassign_user(warehouse_id=id, target_user_id=user_id, current_user=current_user)
    return MessageResponse(message=f"User {user_id} unassigned from warehouse {id} successfully")
