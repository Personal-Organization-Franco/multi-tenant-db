"""
API v1 router configuration.

Aggregates all v1 API endpoints and provides the main router
for the FastAPI application.
"""

from fastapi import APIRouter

from . import health, tenants

# Create main API v1 router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router)
api_router.include_router(tenants.router)

# Future endpoint routers will be added here:
# api_router.include_router(users.router)
# api_router.include_router(auth.router)
