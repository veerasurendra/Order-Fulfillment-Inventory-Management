import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.core.database import get_db
from app.core.security import hash_password, create_access_token
from app.models.user import User, UserRole
from app.models.warehouse import Warehouse, WarehouseStatus, WarehouseUser
from app.models.product import Product, ProductStatus, Category
from app.models.inventory import Inventory
from app.main import create_application

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    # Fresh schema per test function for complete test isolation
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    app = create_application()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seed_data(db_session):
    """Seed test users, warehouses, categories, products, and inventory."""
    # 1. Users
    admin_user = User(
        email="admin@test.com",
        username="admin_user",
        hashed_password=hash_password("adminpass123"),
        full_name="Admin Test",
        role=UserRole.ADMIN,
        is_active=True,
    )
    manager_user = User(
        email="manager@test.com",
        username="manager_user",
        hashed_password=hash_password("managerpass123"),
        full_name="Warehouse Manager",
        role=UserRole.WAREHOUSE_MANAGER,
        is_active=True,
    )
    agent_user = User(
        email="agent@test.com",
        username="agent_user",
        hashed_password=hash_password("agentpass123"),
        full_name="Fulfillment Agent",
        role=UserRole.FULFILLMENT_AGENT,
        is_active=True,
    )
    inactive_agent = User(
        email="inactive_agent@test.com",
        username="inactive_agent",
        hashed_password=hash_password("agentpass123"),
        full_name="Inactive Agent",
        role=UserRole.FULFILLMENT_AGENT,
        is_active=False,
    )
    customer_user = User(
        email="customer@test.com",
        username="customer_user",
        hashed_password=hash_password("customerpass123"),
        full_name="Customer Test",
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    inactive_user = User(
        email="inactive@test.com",
        username="inactive_user",
        hashed_password=hash_password("inactive123"),
        full_name="Inactive User",
        role=UserRole.CUSTOMER,
        is_active=False,
    )

    db_session.add_all([admin_user, manager_user, agent_user, inactive_agent, customer_user, inactive_user])
    db_session.commit()

    # 2. Warehouses
    wh1 = Warehouse(name="North Central Warehouse", location="Chicago, IL", status=WarehouseStatus.ACTIVE, capacity=20000)
    wh2 = Warehouse(name="South Distribution Hub", location="Dallas, TX", status=WarehouseStatus.ACTIVE, capacity=15000)
    wh_inactive = Warehouse(name="Closed Facility", location="Detroit, MI", status=WarehouseStatus.INACTIVE, capacity=5000)
    db_session.add_all([wh1, wh2, wh_inactive])
    db_session.commit()

    # 3. Warehouse User Assignments
    wh_user1 = WarehouseUser(warehouse_id=wh1.id, user_id=manager_user.id)
    wh_user2 = WarehouseUser(warehouse_id=wh1.id, user_id=agent_user.id)
    db_session.add_all([wh_user1, wh_user2])
    db_session.commit()

    # 4. Categories & Products
    cat1 = Category(name="Electronics", description="Consumer electronics and devices")
    cat2 = Category(name="Home Goods", description="Household goods and appliances")
    db_session.add_all([cat1, cat2])
    db_session.commit()

    prod1 = Product(
        sku="SKU-PHONE-01",
        name="Smart Phone X",
        description="Flagship smartphone",
        category_id=cat1.id,
        price=799.99,
        cost_price=450.00,
        status=ProductStatus.ACTIVE,
    )
    prod2 = Product(
        sku="SKU-LAPTOP-02",
        name="Ultra Laptop Pro",
        description="Powerful laptop",
        category_id=cat1.id,
        price=1299.99,
        cost_price=800.00,
        status=ProductStatus.ACTIVE,
    )
    prod_inactive = Product(
        sku="SKU-DISCONTINUED-99",
        name="Legacy MP3 Player",
        description="Discontinued product",
        category_id=cat1.id,
        price=49.99,
        cost_price=20.00,
        status=ProductStatus.INACTIVE,
    )
    db_session.add_all([prod1, prod2, prod_inactive])
    db_session.commit()

    # 5. Inventory
    inv1 = Inventory(
        product_id=prod1.id,
        warehouse_id=wh1.id,
        available_quantity=100,
        reserved_quantity=20,
        damaged_quantity=0,
        reorder_level=15,
    )
    inv2 = Inventory(
        product_id=prod2.id,
        warehouse_id=wh1.id,
        available_quantity=5,  # Low stock
        reserved_quantity=0,
        damaged_quantity=0,
        reorder_level=10,
    )
    inv3 = Inventory(
        product_id=prod1.id,
        warehouse_id=wh2.id,
        available_quantity=50,
        reserved_quantity=0,
        damaged_quantity=0,
        reorder_level=10,
    )
    db_session.add_all([inv1, inv2, inv3])
    db_session.commit()

    return {
        "admin": admin_user,
        "manager": manager_user,
        "agent": agent_user,
        "inactive_agent": inactive_agent,
        "customer": customer_user,
        "inactive_user": inactive_user,
        "wh1": wh1,
        "wh2": wh2,
        "wh_inactive": wh_inactive,
        "prod1": prod1,
        "prod2": prod2,
        "prod_inactive": prod_inactive,
        "inv1": inv1,
        "inv2": inv2,
        "inv3": inv3,
    }


def get_auth_headers(user: User) -> dict:
    token = create_access_token(subject=user.id, role=user.role.value, email=user.email)
    return {"Authorization": f"Bearer {token}"}
