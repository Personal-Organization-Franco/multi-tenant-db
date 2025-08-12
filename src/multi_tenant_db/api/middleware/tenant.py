"""
Multi-tenant middleware for FastAPI.

Handles tenant identification from headers, cookies, or JWT tokens,
and sets up tenant context for database queries with Row Level Security.
"""

import logging
from collections.abc import Callable

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from ...core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and set tenant context for multi-tenant requests.

    Extracts tenant ID from:
    1. X-Tenant-ID header (primary)
    2. tenant_id cookie (fallback)
    3. JWT token claims (future implementation)

    Sets the tenant context in the request state for use by other components.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and set tenant context.

        Args:
            request: FastAPI request object
            call_next: Next middleware in chain

        Returns:
            Response: HTTP response

        Raises:
            HTTPException: If tenant ID is required but not provided
        """
        tenant_id = await self._extract_tenant_id(request)

        # Set tenant context in request state
        request.state.tenant_id = tenant_id

        # Log tenant context for debugging
        if settings.debug:
            logger.debug(f"Request {request.url.path} - Tenant: {tenant_id}")

        try:
            response = await call_next(request)
            return response
        except HTTPException:
            # Re-raise HTTPException without logging to preserve status codes
            # HTTPExceptions should be handled by FastAPI's built-in exception handlers
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error processing request for tenant {tenant_id}: {str(e)}",
                extra={
                    "tenant_id": tenant_id,
                    "path": request.url.path,
                    "method": request.method,
                },
            )
            raise

    async def _extract_tenant_id(self, request: Request) -> str:
        """
        Extract tenant ID from request headers, cookies, or JWT.

        Args:
            request: FastAPI request object

        Returns:
            str: Tenant identifier

        Raises:
            HTTPException: If tenant ID is required but not found
        """
        # Try to get tenant ID from header (primary method)
        tenant_id = request.headers.get(settings.tenant_header_name)

        if not tenant_id:
            # Try to get from cookie (fallback method)
            tenant_id = request.cookies.get(settings.tenant_cookie_name)

        if not tenant_id:
            # Try to extract from JWT token (future implementation)
            tenant_id = await self._extract_from_jwt(request)

        # Check if tenant ID is required
        if not tenant_id and settings.require_tenant_header:
            # Debug logging to see what we're getting
            if settings.debug:
                logger.debug(
                    f"No tenant_id found. Method: {request.method}, "
                    f"Path: {request.url.path}"
                )
            
            # Skip requirement for health and docs endpoints
            skip_paths = [
                "/health",
                "/docs",
                "/redoc",
                "/openapi.json",
                "/api/v1/health",
            ]
            
            # Allow tenant management operations without tenant ID
            # POST /api/v1/tenants - tenant creation
            # GET /api/v1/tenants - list all tenants (administrative function)
            is_tenant_admin_operation = (
                (request.method in ["POST", "GET"]) and 
                (
                    request.url.path == "/api/v1/tenants" or
                    request.url.path == "/api/v1/tenants/"
                )
            )
            
            # Debug logging for tenant admin operations
            if settings.debug:
                logger.debug(f"is_tenant_admin_operation: {is_tenant_admin_operation}")
            
            should_skip = (
                any(request.url.path.startswith(path) for path in skip_paths) 
                or is_tenant_admin_operation
            )
            
            if settings.debug:
                logger.debug(f"should_skip: {should_skip}")
                
            if not should_skip:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing tenant identifier. "
                    f"Provide {settings.tenant_header_name} header "
                    f"or {settings.tenant_cookie_name} cookie.",
                )

        # Use default tenant if none provided and not required
        if not tenant_id:
            tenant_id = settings.default_tenant_id

        return tenant_id

    async def _extract_from_jwt(self, _: Request) -> str | None:
        """
        Extract tenant ID from JWT token claims.

        This is a placeholder for future JWT-based tenant identification.

        Args:
            request: FastAPI request object

        Returns:
            str | None: Tenant ID from JWT or None if not found
        """
        # TODO: Implement JWT token parsing when authentication is added
        # authorization = request.headers.get("Authorization")
        # if authorization and authorization.startswith("Bearer "):
        #     token = authorization.split(" ")[1]
        #     # Parse JWT and extract tenant_id claim
        #     pass

        return None


def get_current_tenant_id(request: Request) -> str:
    """
    Get current tenant ID from request state.

    This function should be used in route handlers to get the tenant ID
    that was set by the TenantContextMiddleware.

    Args:
        request: FastAPI request object

    Returns:
        str: Current tenant identifier

    Raises:
        HTTPException: If tenant ID is not set in request state
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Tenant context not set. Ensure TenantContextMiddleware is configured."
            ),
        )

    return tenant_id


class DatabaseTenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to set tenant context in database sessions.

    This middleware works in conjunction with TenantContextMiddleware
    to ensure that database sessions have the proper tenant context
    set for Row Level Security policies.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Set tenant context in database sessions.

        Args:
            request: FastAPI request object
            call_next: Next middleware in chain

        Returns:
            Response: HTTP response
        """
        # Get tenant ID from request state (set by TenantContextMiddleware)
        tenant_id = getattr(request.state, "tenant_id", None)

        if tenant_id:
            # Store tenant ID for database session injection
            request.state.db_tenant_id = tenant_id

        response = await call_next(request)
        return response
