from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.models.audit import AuditLog
from app.repositories.base import BaseRepository
from app.schemas.common import PaginationMeta


class AuditRepository(BaseRepository[AuditLog]):
    def __init__(self, db: Session):
        super().__init__(AuditLog, db)

    def log_event(
        self,
        action: str,
        entity: str,
        entity_id: Optional[str] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        log = AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            ip_address=ip_address,
            metadata_json=metadata_json,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(log)
        self.db.flush()
        return log

    def list_audit_logs(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        entity: Optional[str] = None,
        entity_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[AuditLog], PaginationMeta]:
        stmt = (
            select(AuditLog)
            .options(joinedload(AuditLog.user))
            .order_by(AuditLog.timestamp.desc())
        )

        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if entity:
            stmt = stmt.where(AuditLog.entity == entity)
        if entity_id:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        if date_from:
            stmt = stmt.where(AuditLog.timestamp >= date_from)
        if date_to:
            stmt = stmt.where(AuditLog.timestamp <= date_to)

        return self.paginate(stmt, page=page, page_size=page_size)
