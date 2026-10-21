import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Any
from sqlalchemy.orm import Session
from app.core.exceptions import DuplicateIdempotencyKeyError
from app.repositories.idempotency_repository import IdempotencyRepository
from app.core.config import settings


class IdempotencyService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = IdempotencyRepository(db)

    @staticmethod
    def calculate_hash(endpoint: str, body_bytes: bytes) -> str:
        h = hashlib.sha256()
        h.update(endpoint.encode("utf-8"))
        h.update(b":")
        h.update(body_bytes)
        return h.hexdigest()

    def check_key(
        self,
        key: str,
        endpoint: str,
        request_hash: str,
    ) -> Optional[Tuple[int, str]]:
        """
        Check if an idempotency key was previously processed.
        Returns (response_code, response_body_json_str) if found and matches.
        Raises DuplicateIdempotencyKeyError if payload hash differs.
        """
        record = self.repo.get_by_key(key)
        if not record:
            return None

        # Verify not expired
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return None

        # Check payload consistency
        if record.request_hash != request_hash:
            raise DuplicateIdempotencyKeyError(
                f"Idempotency key '{key}' was already used with a different request payload"
            )

        return record.response_code, record.response_body

    def save_response(
        self,
        key: str,
        endpoint: str,
        request_hash: str,
        response_code: int,
        response_data: Any,
        user_id: Optional[int] = None,
    ) -> None:
        """Store the response to guarantee idempotency on retries."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.IDEMPOTENCY_EXPIRE_HOURS)
        if isinstance(response_data, str):
            body_str = response_data
        else:
            body_str = json.dumps(response_data, default=str)

        self.repo.save_key(
            key=key,
            endpoint=endpoint,
            request_hash=request_hash,
            response_code=response_code,
            response_body=body_str,
            expires_at=expires_at,
            user_id=user_id,
        )
        self.db.commit()
