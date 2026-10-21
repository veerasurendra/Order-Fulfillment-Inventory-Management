from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.idempotency import IdempotencyKey
from app.repositories.base import BaseRepository


class IdempotencyRepository(BaseRepository[IdempotencyKey]):
    def __init__(self, db: Session):
        super().__init__(IdempotencyKey, db)

    def get_by_key(self, key: str) -> Optional[IdempotencyKey]:
        stmt = select(IdempotencyKey).where(IdempotencyKey.key == key.strip())
        return self.db.scalar(stmt)

    def save_key(
        self,
        key: str,
        endpoint: str,
        request_hash: str,
        response_code: int,
        response_body: str,
        expires_at: datetime,
        user_id: Optional[int] = None,
    ) -> IdempotencyKey:
        record = IdempotencyKey(
            key=key.strip(),
            endpoint=endpoint,
            user_id=user_id,
            request_hash=request_hash,
            response_code=response_code,
            response_body=response_body,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.flush()
        return record
