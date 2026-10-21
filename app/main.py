from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.core.error_handlers import register_exception_handlers
from app.core.database import engine, Base
import app.models  # Ensure all models are registered with Base.metadata
from app.api.v1.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize structured logging
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} in {settings.ENVIRONMENT} mode...")

    # Create tables on startup for quick local development / sqlite
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schemas verified/created successfully.")
    except Exception as e:
        logger.error(f"Error initializing database schemas: {e}")

    yield

    logger.info(f"Shutting down {settings.PROJECT_NAME}...")


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="""
# Enterprise Order Fulfillment & Inventory Management Platform

### Key Architectural Capabilities:
- **Concurrency & Row-Level Locking:** High-concurrency safe inventory reservation using PostgreSQL `SELECT ... FOR UPDATE` row locks preventing overselling or negative quantities.
- **Order State Machine:** Deterministic workflow from `PENDING` -> `CONFIRMED` -> `PROCESSING` -> `PACKED` -> `SHIPPED` -> `DELIVERED`, with transactional rollback and stock release on cancellation.
- **Idempotency Guarantees:** Dual-check caching via `Idempotency-Key` header on order creation, payments, adjustments, and inter-warehouse transfers.
- **Granular RBAC & Resource Scoping:** Role-based (Admin, Warehouse Manager, Fulfillment Agent, Customer) and warehouse-scoped data isolation.
- **Immutable Audit Trail:** Comprehensive event logging (`audit_logs`) and immutable stock ledger (`inventory_transactions`).
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Centralized exception handling
    register_exception_handlers(app)

    # Mount API routers
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/health", tags=["Health"])
    def health_check():
        return {
            "status": "healthy",
            "service": settings.PROJECT_NAME,
            "environment": settings.ENVIRONMENT,
        }

    @app.get("/", tags=["Root"])
    def root():
        return {
            "message": f"Welcome to {settings.PROJECT_NAME}",
            "documentation": "/docs",
            "redoc": "/redoc",
            "api_version": "v1",
        }

    return app


app = create_application()
