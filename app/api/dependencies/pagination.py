from fastapi import Query
from pydantic import BaseModel
from app.core.config import settings


class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size
