from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.dependencies.auth import get_current_user, require_role
from app.models.user import User, UserRole
from app.services.dashboard_service import DashboardService
from app.schemas.dashboard import (
    AdminDashboardResponse,
    WarehouseDashboardResponse,
    CustomerDashboardResponse,
)
from app.schemas.common import SuccessResponse
from app.core.exceptions import BadRequestError

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Reporting"])


@router.get("/admin", response_model=SuccessResponse[AdminDashboardResponse])
def get_admin_dashboard(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: Overview of total orders, revenue, and inventory alerts."""
    service = DashboardService(db)
    data = service.get_admin_dashboard()
    return SuccessResponse(data=data)


@router.get("/warehouse-manager", response_model=SuccessResponse[WarehouseDashboardResponse])
def get_warehouse_manager_dashboard(
    warehouse_id: int = Query(..., description="Target warehouse ID"),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
    db: Session = Depends(get_db),
):
    """Warehouse Manager: Inventory volume, pending fulfillment, and low stock metrics."""
    service = DashboardService(db)
    data = service.get_warehouse_dashboard(warehouse_id=warehouse_id, current_user=current_user)
    return SuccessResponse(data=data)


@router.get("/customer", response_model=SuccessResponse[CustomerDashboardResponse])
def get_customer_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Customer: Summary of active orders, completed orders, and total spending."""
    service = DashboardService(db)
    data = service.get_customer_dashboard(customer_id=current_user.id)
    return SuccessResponse(data=data)
