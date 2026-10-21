from typing import Optional, List
from sqlalchemy.orm import Session
from app.core.exceptions import ConflictError, ResourceNotFoundError
from app.models.product import Product, ProductStatus, Category
from app.repositories.product_repository import ProductRepository
from app.services.audit_service import AuditService
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    CategoryCreate,
    CategoryResponse,
)


class ProductService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ProductRepository(db)
        self.audit_service = AuditService(db)

    def create_product(self, req: ProductCreate, user_id: int, ip_address: Optional[str] = None) -> Product:
        # SKU uniqueness
        if self.repo.get_by_sku(req.sku):
            raise ConflictError(f"A product with SKU '{req.sku}' already exists")

        if req.category_id:
            category = self.repo.get_category_by_id(req.category_id)
            if not category:
                raise ResourceNotFoundError(f"Category with ID {req.category_id} not found")

        product = Product(
            sku=req.sku.upper().strip(),
            name=req.name.strip(),
            description=req.description,
            category_id=req.category_id,
            price=req.price,
            cost_price=req.cost_price,
            status=req.status,
        )
        self.repo.create(product)
        self.db.commit()
        self.db.refresh(product)

        self.audit_service.log(
            action="PRODUCT_CREATED",
            entity="PRODUCT",
            entity_id=str(product.id),
            user_id=user_id,
            ip_address=ip_address,
            metadata_json={"sku": product.sku, "name": product.name, "price": str(product.price)},
        )
        self.db.commit()

        return self.repo.get_by_id_with_category(product.id) or product

    def get_product(self, product_id: int) -> Product:
        product = self.repo.get_by_id_with_category(product_id)
        if not product:
            raise ResourceNotFoundError(f"Product with ID {product_id} not found")
        return product

    def update_product(
        self,
        product_id: int,
        req: ProductUpdate,
        user_id: int,
        ip_address: Optional[str] = None,
    ) -> Product:
        product = self.get_product(product_id)

        if req.name is not None:
            product.name = req.name.strip()
        if req.description is not None:
            product.description = req.description
        if req.category_id is not None:
            if req.category_id != 0:
                cat = self.repo.get_category_by_id(req.category_id)
                if not cat:
                    raise ResourceNotFoundError(f"Category with ID {req.category_id} not found")
                product.category_id = req.category_id
            else:
                product.category_id = None
        if req.price is not None:
            product.price = req.price
        if req.cost_price is not None:
            product.cost_price = req.cost_price
        if req.status is not None:
            product.status = req.status

        self.db.commit()
        self.db.refresh(product)

        self.audit_service.log(
            action="PRODUCT_UPDATED",
            entity="PRODUCT",
            entity_id=str(product.id),
            user_id=user_id,
            ip_address=ip_address,
            metadata_json={"status": product.status.value, "price": str(product.price)},
        )
        self.db.commit()

        return product

    def activate_product(self, product_id: int, user_id: int, ip_address: Optional[str] = None) -> Product:
        product = self.get_product(product_id)
        product.status = ProductStatus.ACTIVE
        self.db.commit()
        self.db.refresh(product)

        self.audit_service.log(
            action="PRODUCT_ACTIVATED",
            entity="PRODUCT",
            entity_id=str(product.id),
            user_id=user_id,
            ip_address=ip_address,
        )
        self.db.commit()
        return product

    def deactivate_product(self, product_id: int, user_id: int, ip_address: Optional[str] = None) -> Product:
        product = self.get_product(product_id)
        product.status = ProductStatus.INACTIVE
        self.db.commit()
        self.db.refresh(product)

        self.audit_service.log(
            action="PRODUCT_DEACTIVATED",
            entity="PRODUCT",
            entity_id=str(product.id),
            user_id=user_id,
            ip_address=ip_address,
        )
        self.db.commit()
        return product

    def list_products(self, **kwargs):
        return self.repo.list_products(**kwargs)

    # Category operations
    def create_category(self, req: CategoryCreate) -> Category:
        if self.repo.get_category_by_name(req.name):
            raise ConflictError(f"Category with name '{req.name}' already exists")
        cat = Category(name=req.name.strip(), description=req.description)
        self.repo.create_category(cat)
        self.db.commit()
        self.db.refresh(cat)
        return cat

    def list_categories(self) -> List[Category]:
        return self.repo.list_categories()
