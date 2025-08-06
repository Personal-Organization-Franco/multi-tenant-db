"""
Dependency injection for FastAPI routes.

Provides reusable dependencies for database sessions, tenant context,
and other common requirements for API endpoints.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.middleware.tenant import get_current_tenant_id
from ..db.session import get_db_session, set_tenant_context


async def get_tenant_db_session(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncSession:
    """
    Get database session with tenant context set.

    This dependency combines database session creation with tenant context
    setting for Row Level Security. It should be used in API endpoints
    that need database access with proper tenant isolation.

    Args:
        request: FastAPI request object (contains tenant context)
        session: Database session from dependency injection

    Returns:
        AsyncSession: Database session with tenant context set

    Example:
        @router.get("/users")
        async def get_users(
            db: AsyncSession = Depends(get_tenant_db_session)
        ) -> list[UserResponse]:
            # All queries will be filtered by tenant automatically
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    # Get tenant ID from request state (set by middleware)
    tenant_id = get_current_tenant_id(request)

    # Set tenant context in database session for RLS
    await set_tenant_context(session, tenant_id)

    return session


async def get_current_tenant(request: Request) -> str:
    """
    Get current tenant ID from request.

    This dependency extracts the tenant ID that was set by the
    TenantContextMiddleware for use in route handlers.

    Args:
        request: FastAPI request object

    Returns:
        str: Current tenant identifier

    Example:
        @router.get("/tenant-info")
        async def get_tenant_info(
            tenant_id: str = Depends(get_current_tenant)
        ) -> TenantInfoResponse:
            return TenantInfoResponse(tenant_id=tenant_id)
    """
    return get_current_tenant_id(request)


# Type aliases for commonly used dependencies
TenantDBSession = Annotated[AsyncSession, Depends(get_tenant_db_session)]
CurrentTenant = Annotated[str, Depends(get_current_tenant)]
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
