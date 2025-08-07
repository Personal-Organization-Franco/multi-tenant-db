"""
FastAPI application factory and configuration.

Creates and configures the FastAPI application with middleware,
routers, and multi-tenant support.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from .api.middleware.tenant import DatabaseTenantMiddleware, TenantContextMiddleware
from .api.v1.router import api_router
from .core.config import get_settings
from .core.logging import setup_logging
from .db.session import close_db_connections

# Setup logging configuration
setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events for the FastAPI application.
    """
    # Startup
    logger.info("Starting up Multi-Tenant Database API")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    yield

    # Shutdown
    logger.info("Shutting down Multi-Tenant Database API")
    await close_db_connections()
    logger.info("Database connections closed")


def create_application() -> FastAPI:
    """
    Application factory function.

    Creates and configures the FastAPI application with all necessary
    middleware, routers, and settings.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Multi-tenant database API with Row Level Security",
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    # Add compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Add multi-tenant middleware (order matters!)
    # 1. Extract tenant context from request
    app.add_middleware(TenantContextMiddleware)

    # 2. Set tenant context in database sessions
    app.add_middleware(DatabaseTenantMiddleware)

    # Include API routers
    app.include_router(
        api_router,
        prefix=settings.api_v1_prefix,
    )

    # Add root health check endpoint (no prefix)
    @app.get("/health")
    async def root_health_check():
        """Root health check endpoint for load balancers."""
        return {"status": "healthy", "service": "Multi-Tenant Database API"}

    return app


# Create application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
