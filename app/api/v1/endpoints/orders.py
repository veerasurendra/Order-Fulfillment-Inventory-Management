import json
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, Request, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.dependencies.auth import get_current_user, require_role
from app.api.dependencies.pagination import PaginationParams
from app.api.dependencies.idempotency import get_idempotency_key
from app.models.user import User, UserRole
from app.models.order import OrderStatus, PaymentStatus
from app.services.order_service import OrderService
from app.services.idempotency_service import IdempotencyService
from app.schemas.order import (
    OrderCreate,
    OrderResponse,
    OrderStatusUpdateRequest,
    OrderAssignRequest,
    OrderCancelRequest,
    PaymentProcessRequest,
)
from app.schemas.common import SuccessResponse, PaginatedResponse

router = APIRouter(prefix="/orders", tags=["Order Fulfillment & Processing"])


@router.post("", response_model=SuccessResponse[OrderResponse], status_code=status.HTTP_201_CREATED)
async def create_order(
    req: OrderCreate,
    request: Request,
    idempotency_key: Optional[str] = Depends(get_idempotency_key),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new order and reserve inventory under concurrency control.
    Supports idempotency via 'Idempotency-Key' header.
    """
    idem_service = IdempotencyService(db)
    endpoint = "/api/orders"
    req_body_bytes = await request.body()
    req_hash = idem_service.calculate_hash(endpoint, req_body_bytes)

    if idempotency_key:
        cached = idem_service.check_key(idempotency_key, endpoint, req_hash)
        if cached:
            status_code, body_str = cached
            return JSONResponse(status_code=status_code, content=json.loads(body_str))

    service = OrderService(db)
    client_ip = request.client.host if request.client else None
    order = service.create_order(req, customer=current_user, ip_address=client_ip)

    response_data = OrderResponse.model_validate(order)
    response_payload = {
        "success": True,
        "data": response_data.model_dump(mode="json"),
        "message": "Order created successfully and inventory reserved",
    }

    if idempotency_key:
        idem_service.save_response(
            key=idempotency_key,
            endpoint=endpoint,
            request_hash=req_hash,
            response_code=201,
            response_data=response_payload,
            user_id=current_user.id,
        )

    return SuccessResponse(data=response_data, message="Order created successfully and inventory reserved")


@router.get("", response_model=PaginatedResponse[OrderResponse])
def list_orders(
    status: Optional[OrderStatus] = Query(None, description="Filter by order status"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    payment_status: Optional[PaymentStatus] = Query(None, description="Filter by payment status"),
    date_from: Optional[datetime] = Query(None, description="Start date filter"),
    date_to: Optional[datetime] = Query(None, description="End date filter"),
    min_amount: Optional[Decimal] = Query(None, description="Minimum total amount"),
    max_amount: Optional[Decimal] = Query(None, description="Maximum total amount"),
    sort_by: str = Query("created_at", description="Sort field (created_at, total_amount)"),
    sort_order: str = Query("desc", description="Sort order (asc / desc)"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List orders with filtering, sorting, and authorization scoping."""
    service = OrderService(db)
    items, meta = service.list_orders(
        current_user=current_user,
        status=status,
        warehouse_id=warehouse_id,
        payment_status=payment_status,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        sort_by=sort_by,
        sort_order=sort_order,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse(
        data=[OrderResponse.model_validate(o) for o in items],
        pagination=meta,
    )


@router.get("/{id}", response_model=SuccessResponse[OrderResponse])
def get_order(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve complete order details including items, history, and assignments."""
    service = OrderService(db)
    order = service.get_order(id, current_user=current_user)
    return SuccessResponse(data=OrderResponse.model_validate(order))


@router.patch("/{id}/status", response_model=SuccessResponse[OrderResponse])
def update_order_status(
    id: int,
    req: OrderStatusUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update order status following the strict state machine rules."""
    service = OrderService(db)
    client_ip = request.client.host if request.client else None
    order = service.update_order_status(id, req, current_user=current_user, ip_address=client_ip)
    return SuccessResponse(data=OrderResponse.model_validate(order), message="Order status updated successfully")


@router.post("/{id}/cancel", response_model=SuccessResponse[OrderResponse])
def cancel_order(
    id: int,
    req: OrderCancelRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel order and automatically release reserved inventory within a transaction."""
    service = OrderService(db)
    client_ip = request.client.host if request.client else None
    order = service.cancel_order(id, req, current_user=current_user, ip_address=client_ip)
    return SuccessResponse(data=OrderResponse.model_validate(order), message="Order cancelled and inventory released")


@router.post("/{id}/assign", response_model=SuccessResponse[OrderResponse])
def assign_order(
    id: int,
    req: OrderAssignRequest,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
    db: Session = Depends(get_db),
):
    """Assign an order to a warehouse fulfillment agent."""
    service = OrderService(db)
    client_ip = request.client.host if request.client else None
    order = service.assign_order(id, req, current_user=current_user, ip_address=client_ip)
    return SuccessResponse(data=OrderResponse.model_validate(order), message="Order assigned successfully")


@router.post("/{id}/payment", response_model=SuccessResponse[OrderResponse])
async def process_payment(
    id: int,
    req: PaymentProcessRequest,
    request: Request,
    idempotency_key: Optional[str] = Depends(get_idempotency_key),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process payment confirmation idempotently."""
    idem_service = IdempotencyService(db)
    endpoint = f"/api/orders/{id}/payment"
    req_body_bytes = await request.body()
    req_hash = idem_service.calculate_hash(endpoint, req_body_bytes)

    if idempotency_key:
        cached = idem_service.check_key(idempotency_key, endpoint, req_hash)
        if cached:
            status_code, body_str = cached
            return JSONResponse(status_code=status_code, content=json.loads(body_str))

    service = OrderService(db)
    client_ip = request.client.host if request.client else None
    order = service.process_payment(id, req, current_user=current_user, ip_address=client_ip)

    response_data = OrderResponse.model_validate(order)
    response_payload = {
        "success": True,
        "data": response_data.model_dump(mode="json"),
        "message": "Payment confirmed and order marked as paid",
    }

    if idempotency_key:
        idem_service.save_response(
            key=idempotency_key,
            endpoint=endpoint,
            request_hash=req_hash,
            response_code=200,
            response_data=response_payload,
            user_id=current_user.id,
        )

    return SuccessResponse(data=response_data, message="Payment confirmed and order marked as paid")


# Fulfillment Workflow Shortcuts for Agents
@router.post("/{id}/start-processing", response_model=SuccessResponse[OrderResponse])
def start_processing(
    id: int,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT)),
    db: Session = Depends(get_db),
):
    """Transition Confirmed -> Processing."""
    service = OrderService(db)
    req = OrderStatusUpdateRequest(status=OrderStatus.PROCESSING, notes="Started order processing")
    order = service.update_order_status(id, req, current_user=current_user, ip_address=request.client.host if request.client else None)
    return SuccessResponse(data=OrderResponse.model_validate(order), message="Order processing started")


@router.post("/{id}/pack", response_model=SuccessResponse[OrderResponse])
def pack_order(
    id: int,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT)),
    db: Session = Depends(get_db),
):
    """Transition Processing -> Packed."""
    service = OrderService(db)
    req = OrderStatusUpdateRequest(status=OrderStatus.PACKED, notes="Order packed and verified")
    order = service.update_order_status(id, req, current_user=current_user, ip_address=request.client.host if request.client else None)
    return SuccessResponse(data=OrderResponse.model_validate(order), message="Order packed successfully")


@router.post("/{id}/ship", response_model=SuccessResponse[OrderResponse])
def ship_order(
    id: int,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT)),
    db: Session = Depends(get_db),
):
    """Transition Packed -> Shipped (deducts reserved inventory, creates SALE transaction)."""
    service = OrderService(db)
    req = OrderStatusUpdateRequest(status=OrderStatus.SHIPPED, notes="Order dispatched and shipped")
    order = service.update_order_status(id, req, current_user=current_user, ip_address=request.client.host if request.client else None)
    return SuccessResponse(data=OrderResponse.model_validate(order), message="Order shipped successfully")


@router.post("/{id}/deliver", response_model=SuccessResponse[OrderResponse])
def deliver_order(
    id: int,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT)),
    db: Session = Depends(get_db),
):
    """Transition Shipped -> Delivered."""
    service = OrderService(db)
    req = OrderStatusUpdateRequest(status=OrderStatus.DELIVERED, notes="Order delivered to customer")
    order = service.update_order_status(id, req, current_user=current_user, ip_address=request.client.host if request.client else None)
    return SuccessResponse(data=OrderResponse.model_validate(order), message="Order delivered successfully")
