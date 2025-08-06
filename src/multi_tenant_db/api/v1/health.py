"""
Health check endpoints for monitoring and diagnostics.

Provides endpoints to check the health of the application,
database connectivity, and other system components.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, status

from ...core.deps import DBSession
from ...db.session import test_database_connection

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, Any]:
    """
    Basic health check endpoint.

    Returns basic application status and timestamp.
    This endpoint does not require authentication or tenant context.

    Returns:
        dict: Health status information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Multi-Tenant Database API",
        "version": "0.1.0",
    }


@router.get("/detailed", status_code=status.HTTP_200_OK)
async def detailed_health_check() -> dict[str, Any]:
    """
    Detailed health check with database connectivity test.

    Checks the health of various system components including
    database connectivity and provides detailed status information.

    Returns:
        dict: Detailed health status information
    """
    # Test database connectivity
    db_healthy = await test_database_connection()

    # Overall health status
    overall_status = "healthy" if db_healthy else "unhealthy"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Multi-Tenant Database API",
        "version": "0.1.0",
        "components": {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }


@router.get("/database", status_code=status.HTTP_200_OK)
async def database_health_check(db: DBSession) -> dict[str, Any]:
    """
    Database-specific health check with session test.

    Tests database connectivity using an actual session
    and provides database-specific health information.

    Args:
        db: Database session from dependency injection

    Returns:
        dict: Database health status information
    """
    try:
        # Test a simple query
        result = await db.execute("SELECT 1 as test_value, NOW() as current_time")
        row = result.fetchone()

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "status": "healthy",
                "test_query": "successful",
                "test_value": row.test_value,
                "server_time": row.current_time.isoformat(),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
        }


@router.get("/readiness", status_code=status.HTTP_200_OK)
async def readiness_check() -> dict[str, Any]:
    """
    Readiness check for Kubernetes/container orchestration.

    Indicates whether the service is ready to accept traffic.
    Checks critical dependencies that must be available for
    the service to function properly.

    Returns:
        dict: Readiness status information
    """
    checks = []

    # Database connectivity check
    db_ready = await test_database_connection()
    checks.append(
        {
            "name": "database",
            "status": "ready" if db_ready else "not_ready",
            "required": True,
        }
    )

    # Check if all required services are ready
    all_required_ready = all(
        check["status"] == "ready" for check in checks if check["required"]
    )

    return {
        "status": "ready" if all_required_ready else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("/liveness", status_code=status.HTTP_200_OK)
async def liveness_check() -> dict[str, Any]:
    """
    Liveness check for Kubernetes/container orchestration.

    Simple check to verify the application is running and responsive.
    This should be a lightweight check that doesn't depend on
    external services.

    Returns:
        dict: Liveness status information
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": "service_running",  # Could be enhanced with actual uptime
    }
