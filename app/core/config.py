import os
from typing import List, Optional
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    PROJECT_NAME: str = "Order Fulfillment & Inventory Management Platform"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api"

    # Security & JWT
    SECRET_KEY: str = "supersecretjwtkeyfororderfulfillmentandinventorymanagementplatform2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "sqlite:///./order_fulfillment.db"
    POSTGRES_SERVER: Optional[str] = "localhost"
    POSTGRES_USER: Optional[str] = "postgres"
    POSTGRES_PASSWORD: Optional[str] = "postgres"
    POSTGRES_DB: Optional[str] = "order_fulfillment_db"
    POSTGRES_PORT: Optional[int] = 5432

    # Redis (optional bonus)
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Idempotency cache duration in hours
    IDEMPOTENCY_EXPIRE_HOURS: int = 24


settings = Settings()
