from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.repositories.audit_repository import AuditRepository
from app.models.audit import AuditLog


class AuditService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AuditRepository(db)

    def log(
        self,
        action: str,
        entity: str,
        entity_id: Optional[str] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        return self.repo.log_event(
            action=action,
            entity=entity,
            entity_id=entity_id,
            user_id=user_id,
            ip_address=ip_address,
            metadata_json=metadata_json,
        )

    def list_logs(self, **kwargs):
        return self.repo.list_audit_logs(**kwargs)
