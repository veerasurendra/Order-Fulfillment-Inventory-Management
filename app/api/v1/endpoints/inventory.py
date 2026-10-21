import json
from typing import Optional, List
from fastapi import APIRouter, Depends, Request, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.dependencies.auth import get_current_user, require_role
from app.api.dependencies.pagination import PaginationParams
from app.api.dependencies.idempotency import get_idempotency_key
from app.models.user import User, UserRole
from app.models.inventory import TransactionType
from app.services.inventory_service import InventoryService
from app.services.idempotency_service import IdempotencyService
from app.schemas.inventory import (
    InventoryResponse,
    InventoryAdjustRequest,
    InventoryAdjustResponse,
    InventoryTransferRequest,
    InventoryTransferResponse,
    InventoryTransactionResponse,
    LowStockResponse,
)
from app.schemas.common import SuccessResponse, PaginatedResponse

router = APIRouter(prefix="/inventory", tags=["Inventory Management"])


@router.get("", response_model=PaginatedResponse[InventoryResponse])
def list_inventory(
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    low_stock: Optional[bool] = Query(None, description="Filter items at or below reorder level"),
    out_of_stock: Optional[bool] = Query(None, description="Filter items with zero available quantity"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List inventory records across warehouses with filters."""
    service = InventoryService(db)
    items, meta = service.list_inventory(
        current_user=current_user,
        warehouse_id=warehouse_id,
        product_id=product_id,
        low_stock=low_stock,
        out_of_stock=out_of_stock,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse(
        data=[InventoryResponse.model_validate(i) for i in items],
        pagination=meta,
    )


@router.get("/low-stock", response_model=SuccessResponse[List[LowStockResponse]])
def get_low_stock(
    warehouse_id: Optional[int] = Query(None, description="Optional warehouse filter"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all products where available_quantity <= reorder_level."""
    service = InventoryService(db)
    items = service.get_low_stock(current_user=current_user, warehouse_id=warehouse_id)
    return SuccessResponse(data=items)


@router.get("/transactions", response_model=PaginatedResponse[InventoryTransactionResponse])
def list_inventory_transactions(
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    transaction_type: Optional[TransactionType] = Query(None, description="Filter by transaction type"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
    db: Session = Depends(get_db),
):
    """View immutable inventory movement audit trail."""
    service = InventoryService(db)
    items, meta = service.repo.list_transactions(
        product_id=product_id,
        warehouse_id=warehouse_id,
        transaction_type=transaction_type,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse(
        data=[InventoryTransactionResponse.model_validate(tx) for tx in items],
        pagination=meta,
    )


@router.get("/{product_id}", response_model=SuccessResponse[List[InventoryResponse]])
def get_product_inventory(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get inventory distribution for a product across all warehouses."""
    service = InventoryService(db)
    items = service.get_product_inventory(product_id)
    return SuccessResponse(data=[InventoryResponse.model_validate(i) for i in items])


@router.post("/adjust", response_model=SuccessResponse[InventoryAdjustResponse])
async def adjust_inventory(
    req: InventoryAdjustRequest,
    request: Request,
    idempotency_key: Optional[str] = Depends(get_idempotency_key),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
    db: Session = Depends(get_db),
):
    """
    Adjust inventory stock level with row-locking and immutable transaction creation.
    Supports idempotency via 'Idempotency-Key' header.
    """
    idem_service = IdempotencyService(db)
    endpoint = "/api/inventory/adjust"
    req_body_bytes = await request.body()
    req_hash = idem_service.calculate_hash(endpoint, req_body_bytes)

    if idempotency_key:
        cached = idem_service.check_key(idempotency_key, endpoint, req_hash)
        if cached:
            status_code, body_str = cached
            return JSONResponse(status_code=status_code, content=json.loads(body_str))

    service = InventoryService(db)
    client_ip = request.client.host if request.client else None
    result = service.adjust_inventory(req, current_user=current_user, ip_address=client_ip)

    response_payload = {
        "success": True,
        "data": result.model_dump(mode="json"),
        "message": "Inventory successfully adjusted",
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

    return SuccessResponse(data=result, message="Inventory successfully adjusted")


@router.post("/transfer", response_model=SuccessResponse[InventoryTransferResponse])
async def transfer_inventory(
    req: InventoryTransferRequest,
    request: Request,
    idempotency_key: Optional[str] = Depends(get_idempotency_key),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
    db: Session = Depends(get_db),
):
    """
    Transfer inventory between warehouses with atomic row-locking and dual transaction logs.
    Supports idempotency via 'Idempotency-Key' header.
    """
    idem_service = IdempotencyService(db)
    endpoint = "/api/inventory/transfer"
    req_body_bytes = await request.body()
    req_hash = idem_service.calculate_hash(endpoint, req_body_bytes)

    if idempotency_key:
        cached = idem_service.check_key(idempotency_key, endpoint, req_hash)
        if cached:
            status_code, body_str = cached
            return JSONResponse(status_code=status_code, content=json.loads(body_str))

    service = InventoryService(db)
    client_ip = request.client.host if request.client else None
    result = service.transfer_inventory(req, current_user=current_user, ip_address=client_ip)

    response_payload = {
        "success": True,
        "data": result.model_dump(mode="json"),
        "message": "Inventory transferred successfully",
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

    return SuccessResponse(data=result, message="Inventory transferred successfully")
