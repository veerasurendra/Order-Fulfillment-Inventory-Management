from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session, joinedload
from app.models.inventory import Inventory, InventoryTransaction, TransactionType
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.repositories.base import BaseRepository
from app.schemas.common import PaginationMeta


class InventoryRepository(BaseRepository[Inventory]):
    def __init__(self, db: Session):
        super().__init__(Inventory, db)

    def get_inventory(
        self,
        product_id: int,
        warehouse_id: int,
        for_update: bool = False,
    ) -> Optional[Inventory]:
        """
        Fetch inventory record for product and warehouse.
        If for_update=True, applies row-level locking (SELECT ... FOR UPDATE)
        to prevent race conditions in concurrent transactions.
        """
        stmt = (
            select(Inventory)
            .options(joinedload(Inventory.product), joinedload(Inventory.warehouse))
            .where(
                Inventory.product_id == product_id,
                Inventory.warehouse_id == warehouse_id,
            )
        )
        if for_update:
            stmt = stmt.with_for_update()

        return self.db.scalar(stmt)

    def get_by_product_id(self, product_id: int) -> List[Inventory]:
        stmt = (
            select(Inventory)
            .options(joinedload(Inventory.product), joinedload(Inventory.warehouse))
            .where(Inventory.product_id == product_id)
        )
        return list(self.db.scalars(stmt).all())

    def list_inventory(
        self,
        warehouse_id: Optional[int] = None,
        product_id: Optional[int] = None,
        low_stock: Optional[bool] = None,
        out_of_stock: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Inventory], PaginationMeta]:
        stmt = (
            select(Inventory)
            .options(joinedload(Inventory.product), joinedload(Inventory.warehouse))
            .order_by(Inventory.id.asc())
        )

        if warehouse_id is not None:
            stmt = stmt.where(Inventory.warehouse_id == warehouse_id)

        if product_id is not None:
            stmt = stmt.where(Inventory.product_id == product_id)

        if low_stock is True:
            stmt = stmt.where(Inventory.available_quantity <= Inventory.reorder_level)

        if out_of_stock is True:
            stmt = stmt.where(Inventory.available_quantity == 0)

        return self.paginate(stmt, page=page, page_size=page_size)

    def get_low_stock_items(self, warehouse_id: Optional[int] = None) -> List[Inventory]:
        stmt = (
            select(Inventory)
            .options(joinedload(Inventory.product), joinedload(Inventory.warehouse))
            .where(Inventory.available_quantity <= Inventory.reorder_level)
        )
        if warehouse_id is not None:
            stmt = stmt.where(Inventory.warehouse_id == warehouse_id)
        return list(self.db.scalars(stmt).all())

    def create_transaction(
        self,
        product_id: int,
        warehouse_id: int,
        transaction_type: TransactionType,
        quantity: int,
        reference_entity: Optional[str] = None,
        reference_id: Optional[str] = None,
        user_id: Optional[int] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> InventoryTransaction:
        """Create an immutable inventory movement transaction."""
        tx = InventoryTransaction(
            product_id=product_id,
            warehouse_id=warehouse_id,
            transaction_type=transaction_type,
            quantity=quantity,
            reference_entity=reference_entity,
            reference_id=reference_id,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            metadata_json=metadata_json,
        )
        self.db.add(tx)
        self.db.flush()
        return tx

    def list_transactions(
        self,
        product_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        transaction_type: Optional[TransactionType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[InventoryTransaction], PaginationMeta]:
        stmt = (
            select(InventoryTransaction)
            .order_by(InventoryTransaction.timestamp.desc())
        )
        if product_id is not None:
            stmt = stmt.where(InventoryTransaction.product_id == product_id)
        if warehouse_id is not None:
            stmt = stmt.where(InventoryTransaction.warehouse_id == warehouse_id)
        if transaction_type is not None:
            stmt = stmt.where(InventoryTransaction.transaction_type == transaction_type)

        repo = BaseRepository[InventoryTransaction](InventoryTransaction, self.db)
        return repo.paginate(stmt, page=page, page_size=page_size)
