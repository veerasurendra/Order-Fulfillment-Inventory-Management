from typing import Optional
from fastapi import APIRouter, Depends, Request, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.dependencies.auth import get_current_user, require_role
from app.api.dependencies.pagination import PaginationParams
from app.models.user import User, UserRole
from app.models.return_order import ReturnStatus
from app.services.return_service import ReturnService
from app.schemas.return_order import (
    ReturnCreate,
    ReturnResponse,
    ReturnStatusUpdateRequest,
)
from app.schemas.common import SuccessResponse, PaginatedResponse

router = APIRouter(prefix="/returns", tags=["Returns Management"])


@router.post("", response_model=SuccessResponse[ReturnResponse], status_code=status.HTTP_201_CREATED)
def create_return(
    req: ReturnCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Customer: Request a return for an eligible (Delivered) order."""
    service = ReturnService(db)
    client_ip = request.client.host if request.client else None
    ret = service.create_return_request(req, current_user=current_user, ip_address=client_ip)
    return SuccessResponse(data=ReturnResponse.model_validate(ret), message="Return request submitted successfully")


@router.get("", response_model=PaginatedResponse[ReturnResponse])
def list_returns(
    status: Optional[ReturnStatus] = Query(None, description="Filter by return status"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List return requests with status and warehouse filters."""
    service = ReturnService(db)
    items, meta = service.list_returns(
        current_user=current_user,
        status=status,
        warehouse_id=warehouse_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse(
        data=[ReturnResponse.model_validate(r) for r in items],
        pagination=meta,
    )


@router.get("/{id}", response_model=SuccessResponse[ReturnResponse])
def get_return(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get single return request details."""
    service = ReturnService(db)
    ret = service.get_return(id, current_user=current_user)
    return SuccessResponse(data=ReturnResponse.model_validate(ret))


@router.patch("/{id}/status", response_model=SuccessResponse[ReturnResponse])
def update_return_status(
    id: int,
    req: ReturnStatusUpdateRequest,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
    db: Session = Depends(get_db),
):
    """Admin / Manager: Update return status (Approved, Rejected, Received & restocked, Refunded)."""
    service = ReturnService(db)
    client_ip = request.client.host if request.client else None
    ret = service.update_return_status(id, req, current_user=current_user, ip_address=client_ip)
    return SuccessResponse(data=ReturnResponse.model_validate(ret), message="Return status updated successfully")
