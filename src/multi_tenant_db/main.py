"""
FastAPI application factory and configuration.

Creates and configures the FastAPI application with middleware,
routers, and multi-tenant support.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


def add_exception_handlers(app: FastAPI) -> None:
    """
    Add global exception handlers for better error responses and logging.
    
    Args:
        app: FastAPI application instance
    """
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """
        Handle HTTPException with structured logging and clean response.
        
        Args:
            request: FastAPI request object
            exc: HTTPException instance
            
        Returns:
            JSONResponse: Structured error response
        """
        # Get tenant context if available
        tenant_id = getattr(request.state, "tenant_id", None)
        
        # Log the error with context
        logger.warning(
            f"HTTP {exc.status_code}: {exc.detail}",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "path": request.url.path,
                "method": request.method,
                "tenant_id": tenant_id,
            }
        )
        
        # Return clean JSON response
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": exc.detail,
                    "type": "HTTPException",
                    "status_code": exc.status_code,
                }
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Handle request validation errors with structured response.
        
        Args:
            request: FastAPI request object
            exc: RequestValidationError instance
            
        Returns:
            JSONResponse: Structured validation error response
        """
        tenant_id = getattr(request.state, "tenant_id", None)
        
        logger.warning(
            f"Validation error: {exc.errors()}",
            extra={
                "errors": exc.errors(),
                "body": exc.body,
                "path": request.url.path,
                "method": request.method,
                "tenant_id": tenant_id,
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "message": "Validation error",
                    "type": "ValidationError",
                    "status_code": 422,
                    "details": exc.errors(),
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Handle unexpected exceptions with logging and generic response.
        
        Args:
            request: FastAPI request object
            exc: Exception instance
            
        Returns:
            JSONResponse: Generic error response
        """
        tenant_id = getattr(request.state, "tenant_id", None)
        
        logger.error(
            f"Unexpected error: {str(exc)}",
            extra={
                "exception_type": exc.__class__.__name__,
                "path": request.url.path,
                "method": request.method,
                "tenant_id": tenant_id,
            },
            exc_info=True
        )
        
        # Don't expose internal error details in production
        error_message = (
            str(exc) if settings.debug 
            else "An internal server error occurred"
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "message": error_message,
                    "type": "InternalServerError",
                    "status_code": 500,
                }
            }
        )


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

    # Add global exception handlers
    add_exception_handlers(app)

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
