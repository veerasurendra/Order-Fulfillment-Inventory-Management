from typing import Optional, List
from decimal import Decimal
from sqlalchemy import select, or_
from sqlalchemy.orm import Session, joinedload
from app.models.product import Product, Category, ProductStatus
from app.repositories.base import BaseRepository
from app.schemas.common import PaginationMeta


class ProductRepository(BaseRepository[Product]):
    def __init__(self, db: Session):
        super().__init__(Product, db)

    def get_by_id_with_category(self, product_id: int) -> Optional[Product]:
        stmt = (
            select(Product)
            .options(joinedload(Product.category))
            .where(Product.id == product_id)
        )
        return self.db.scalar(stmt)

    def get_by_sku(self, sku: str) -> Optional[Product]:
        stmt = select(Product).where(Product.sku == sku.upper().strip())
        return self.db.scalar(stmt)

    def list_products(
        self,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        status: Optional[ProductStatus] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        sort_by: str = "id",
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Product], PaginationMeta]:
        stmt = select(Product).options(joinedload(Product.category))

        if search:
            search_pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Product.name.ilike(search_pattern),
                    Product.sku.ilike(search_pattern),
                    Product.description.ilike(search_pattern),
                )
            )

        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)

        if status:
            stmt = stmt.where(Product.status == status)

        if min_price is not None:
            stmt = stmt.where(Product.price >= min_price)

        if max_price is not None:
            stmt = stmt.where(Product.price <= max_price)

        # Sorting
        sort_column = getattr(Product, sort_by, Product.id)
        if sort_order.lower() == "desc":
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())

        return self.paginate(stmt, page=page, page_size=page_size)

    # Categories
    def get_category_by_id(self, category_id: int) -> Optional[Category]:
        return self.db.get(Category, category_id)

    def get_category_by_name(self, name: str) -> Optional[Category]:
        stmt = select(Category).where(Category.name == name.strip())
        return self.db.scalar(stmt)

    def create_category(self, category: Category) -> Category:
        self.db.add(category)
        self.db.flush()
        return category

    def list_categories(self) -> List[Category]:
        stmt = select(Category).order_by(Category.name.asc())
        return list(self.db.scalars(stmt).all())
