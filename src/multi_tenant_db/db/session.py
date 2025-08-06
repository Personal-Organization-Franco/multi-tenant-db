"""
Database session management with multi-tenant support.

Provides async database sessions with tenant context and Row Level Security (RLS)
integration for PostgreSQL.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from ..core.config import get_settings

settings = get_settings()

# Create async engine with connection pooling
engine: AsyncEngine = create_async_engine(
    str(settings.database_url),
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,  # Validate connections before use
    echo=settings.debug,  # Log SQL queries in debug mode
)

# Create session factory
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """
    Dependency to get database session.

    Creates a new database session for each request and ensures
    proper cleanup after the request is completed.

    Yields:
        AsyncSession: Database session
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_tenant_session(tenant_id: str) -> AsyncGenerator[AsyncSession]:
    """
    Create database session with tenant context for Row Level Security.

    Sets the tenant_id in the PostgreSQL session using SET LOCAL,
    which enables Row Level Security policies to filter data
    automatically for the specified tenant.

    Args:
        tenant_id: The tenant identifier to set in session context

    Yields:
        AsyncSession: Database session with tenant context

    Example:
        async with get_tenant_session("tenant123") as session:
            # All queries in this session will be filtered by tenant123
            result = await session.execute(select(User))
    """
    async with SessionLocal() as session:
        try:
            # Set tenant context for RLS
            await session.execute(
                text("SET LOCAL app.current_tenant_id = :tenant_id"),
                {"tenant_id": tenant_id},
            )
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """
    Set tenant context in existing session for Row Level Security.

    This function can be used to set tenant context in an existing
    session, typically in middleware or dependency injection.

    Args:
        session: Existing database session
        tenant_id: The tenant identifier to set in session context
    """
    await session.execute(
        text("SET LOCAL app.current_tenant_id = :tenant_id"), {"tenant_id": tenant_id}
    )


async def get_current_tenant_id(session: AsyncSession) -> str | None:
    """
    Get the current tenant ID from the database session.

    Args:
        session: Database session

    Returns:
        str | None: Current tenant ID or None if not set
    """
    result = await session.execute(
        text("SELECT current_setting('app.current_tenant_id', true)")
    )
    tenant_id = result.scalar()
    return tenant_id if tenant_id else None


async def test_database_connection() -> bool:
    """
    Test database connectivity.

    Returns:
        bool: True if database is accessible, False otherwise
    """
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


async def close_db_connections() -> None:
    """Close all database connections."""
    await engine.dispose()
