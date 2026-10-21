from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.schemas.auth import UserResponse


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    entity: str
    entity_id: Optional[str] = None
    timestamp: datetime
    ip_address: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    user: Optional[UserResponse] = None

    class Config:
        from_attributes = True
