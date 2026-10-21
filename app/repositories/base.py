import math
from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy import select, func, Select
from sqlalchemy.orm import Session
from app.schemas.common import PaginationMeta

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get_by_id(self, id: int) -> Optional[ModelType]:
        return self.db.get(self.model, id)

    def list_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        stmt = select(self.model).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def create(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(self, obj: ModelType) -> ModelType:
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelType) -> None:
        self.db.delete(obj)
        self.db.flush()

    def paginate(self, query: Select, page: int = 1, page_size: int = 20) -> tuple[List[Any], PaginationMeta]:
        """Apply pagination to a SQLAlchemy Select statement."""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        # Count total records
        count_query = select(func.count()).select_from(query.subquery())
        total_items = self.db.scalar(count_query) or 0

        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1
        offset = (page - 1) * page_size

        paginated_query = query.offset(offset).limit(page_size)
        items = list(self.db.scalars(paginated_query).all())

        pagination = PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )
        return items, pagination
