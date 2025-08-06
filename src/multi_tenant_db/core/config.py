"""
Application configuration management.

Handles environment variables, database settings, and application configuration
for the multi-tenant FastAPI application.
"""

from functools import lru_cache
from typing import Any

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors_origins(v: Any) -> list[str]:
    """Parse CORS origins from string or list."""
    if isinstance(v, str):
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    return v if isinstance(v, list) else [v] if v else []


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application settings
    app_name: str = "Multi-Tenant Database API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    # Database settings
    database_url: PostgresDsn

    # Database connection pool settings
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    # Security settings
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_token_expire_minutes: int = 30

    # CORS settings
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # API settings
    api_v1_prefix: str = "/api/v1"
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str | None = "/openapi.json"

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Multi-tenant settings
    default_tenant_id: str = "default"
    tenant_header_name: str = "X-Tenant-ID"
    tenant_cookie_name: str = "tenant_id"
    require_tenant_header: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
        env_parse_none_str="None",
        env_prefix_separator="",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v if isinstance(v, list) else [v] if v else []

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of allowed values."""
        allowed = {"development", "staging", "production", "testing"}
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is supported."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"Log level must be one of: {allowed}")
        return v_upper

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.environment == "testing"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Uses LRU cache to avoid re-parsing environment variables
    on every function call.

    Returns:
        Settings: Application settings instance
    """
    return Settings()
