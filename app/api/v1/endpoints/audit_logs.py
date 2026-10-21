from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.dependencies.auth import require_role
from app.api.dependencies.pagination import PaginationParams
from app.models.user import User, UserRole
from app.services.audit_service import AuditService
from app.schemas.audit import AuditLogResponse
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit & Compliance"])


@router.get("", response_model=PaginatedResponse[AuditLogResponse])
def list_audit_logs(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by event action"),
    entity: Optional[str] = Query(None, description="Filter by entity type (ORDER, INVENTORY, USER, etc.)"),
    entity_id: Optional[str] = Query(None, description="Filter by specific entity ID"),
    date_from: Optional[datetime] = Query(None, description="Filter logs starting from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter logs up to this date"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin: View immutable system audit logs."""
    service = AuditService(db)
    items, meta = service.list_logs(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse(
        data=[AuditLogResponse.model_validate(log) for log in items],
        pagination=meta,
    )
