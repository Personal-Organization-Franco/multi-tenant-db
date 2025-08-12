"""
Tenant API endpoints for multi-tenant database management.

Implements RESTful CRUD operations for tenant entities with proper
validation, hierarchical relationships, and RLS integration.
"""

from uuid import UUID

from fastapi import APIRouter, Query, status

from ...core.deps import DBSession, TenantDBSession
from ...models.tenant import TenantType
from ...schemas.tenant import (
    TenantCreate,
    TenantDeleteResponse,
    TenantListResponse,
    TenantResponse,
    TenantUpdate,
)
from ...services.tenant import TenantService

# Query parameter definitions
TENANT_TYPE_QUERY = Query(
    default=None,
    description="Filter by tenant type: 'parent' or 'subsidiary'"
)

# Create router instance
router = APIRouter(
    prefix="/tenants",
    tags=["tenants"],
    responses={
        404: {"description": "Tenant not found"},
        403: {"description": "Access denied"},
        409: {"description": "Conflict - constraint violation"},
    },
)


@router.post(
    "/",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new tenant",
    description=(
        "Create a new tenant organization with validation and hierarchical support. "
        "Parent tenants can only be created at root level, subsidiaries require "
        "a parent."
    )
)
async def create_tenant(
    tenant_data: TenantCreate,
    db: DBSession,
) -> TenantResponse:
    """
    Create a new tenant with comprehensive validation.
    
    - **name**: Unique tenant name within parent hierarchy
    - **tenant_type**: 'parent' for top-level, 'subsidiary' for child tenants  
    - **parent_tenant_id**: Required for subsidiaries, null for parent tenants
    - **metadata**: Optional JSON object for additional tenant information
    
    Returns the created tenant with generated ID and timestamps.
    """
    
    service = TenantService(db)
    return await service.create_tenant(tenant_data)


@router.get(
    "/",
    response_model=TenantListResponse,
    summary="List tenants with pagination",
    description=(
        "Retrieve paginated list of tenants with optional filtering. "
        "Results respect tenant access control via Row Level Security."
    )
)
async def list_tenants(
    db: DBSession,
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of tenants to return"
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of tenants to skip for pagination"
    ),
    tenant_type: TenantType | None = TENANT_TYPE_QUERY,
) -> TenantListResponse:
    """
    List tenants with pagination and optional filtering.
    
    - **limit**: Number of results per page (1-1000, default 100)
    - **offset**: Number of results to skip (default 0)  
    - **tenant_type**: Optional filter by 'parent' or 'subsidiary'
    
    Returns paginated list with total count for proper pagination handling.
    """
    service = TenantService(db)
    return await service.list_tenants(
        limit=limit,
        offset=offset,
        tenant_type=tenant_type
    )


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get tenant by ID",
    description=(
        "Retrieve detailed information for a specific tenant. "
        "Access is controlled by Row Level Security policies."
    )
)
async def get_tenant(
    tenant_id: UUID,
    db: TenantDBSession,
) -> TenantResponse:
    """
    Get tenant details by UUID.
    
    Returns complete tenant information including metadata, 
    hierarchical relationships, and timestamps.
    
    Raises 404 if tenant not found or access denied.
    """
    service = TenantService(db)
    return await service.get_tenant_by_id(tenant_id)


@router.put(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Update tenant information",
    description=(
        "Update tenant name and metadata. Tenant type and parent relationships "
        "cannot be modified after creation for data integrity."
    )
)
async def update_tenant(
    tenant_id: UUID,
    tenant_data: TenantUpdate,
    db: TenantDBSession,
) -> TenantResponse:
    """
    Update tenant information with validation.
    
    - **name**: Updated tenant name (must be unique within parent hierarchy)
    - **metadata**: Updated metadata object (completely replaces existing)
    
    Returns updated tenant information with new timestamps.
    
    Note: tenant_type and parent_tenant_id cannot be changed after creation.
    """
    service = TenantService(db)
    return await service.update_tenant(tenant_id, tenant_data)


@router.delete(
    "/{tenant_id}",
    response_model=TenantDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete tenant",
    description=(
        "Delete a tenant with cascading validation. Parent tenants with active "
        "subsidiaries cannot be deleted - subsidiaries must be removed first."
    )
)
async def delete_tenant(
    tenant_id: UUID,
    db: TenantDBSession,
) -> TenantDeleteResponse:
    """
    Delete tenant with validation and cascading checks.
    
    Validates that:
    - Tenant exists and is accessible
    - No active subsidiaries exist (for parent tenants)
    - No data relationships prevent deletion
    
    Returns confirmation message with deleted tenant ID.
    
    Raises 409 if tenant has dependencies that prevent deletion.
    """
    service = TenantService(db)
    return await service.delete_tenant(tenant_id)


@router.get(
    "/{tenant_id}/hierarchy",
    response_model=list[TenantResponse],
    summary="Get tenant hierarchy",
    description=(
        "Retrieve complete tenant hierarchy including parent and all subsidiaries. "
        "Useful for organization structure visualization and management."
    )
)
async def get_tenant_hierarchy(
    tenant_id: UUID,
    db: TenantDBSession,
) -> list[TenantResponse]:
    """
    Get complete tenant hierarchy.
    
    For parent tenants: Returns the tenant and all its subsidiaries
    For subsidiary tenants: Returns the parent and all sibling subsidiaries
    
    Provides complete organizational context for the requested tenant.
    """
    service = TenantService(db)
    return await service.get_tenant_hierarchy(tenant_id)