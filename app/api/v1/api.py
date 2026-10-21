from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    products,
    warehouses,
    inventory,
    orders,
    returns,
    notifications,
    audit_logs,
    dashboard,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(warehouses.router)
api_router.include_router(inventory.router)
api_router.include_router(orders.router)
api_router.include_router(returns.router)
api_router.include_router(notifications.router)
api_router.include_router(audit_logs.router)
api_router.include_router(dashboard.router)
