"""
Custom exceptions for the multi-tenant application.

Defines application-specific exceptions with proper HTTP status codes
and error messages for API responses.
"""

from fastapi import HTTPException, status


class MultiTenantException(Exception):
    """Base exception for multi-tenant application."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class TenantNotFoundException(MultiTenantException):
    """Raised when a tenant is not found."""

    pass


class TenantContextMissingException(MultiTenantException):
    """Raised when tenant context is missing from request."""

    pass


class DatabaseConnectionException(MultiTenantException):
    """Raised when database connection fails."""

    pass


class InvalidConfigurationException(MultiTenantException):
    """Raised when application configuration is invalid."""

    pass


# HTTP Exception helpers
def tenant_not_found_exception(tenant_id: str) -> HTTPException:
    """Create HTTP exception for tenant not found."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Tenant '{tenant_id}' not found",
    )


def tenant_context_missing_exception() -> HTTPException:
    """Create HTTP exception for missing tenant context."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Tenant context is required but not provided",
    )


def database_connection_exception() -> HTTPException:
    """Create HTTP exception for database connection failure."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database service is temporarily unavailable",
    )


def invalid_configuration_exception(detail: str) -> HTTPException:
    """Create HTTP exception for invalid configuration."""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Configuration error: {detail}",
    )
