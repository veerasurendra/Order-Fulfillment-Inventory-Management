from typing import Optional
from fastapi import Header


def get_idempotency_key(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", description="Unique UUID to guarantee idempotent request execution"),
) -> Optional[str]:
    return idempotency_key
