"""
Tenant service layer with business logic for CRUD operations.

Implements comprehensive tenant management with proper validation,
hierarchical relationships, and integration with RLS policies.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.tenant import Tenant, TenantType
from ..schemas.tenant import (
    TenantCreate,
    TenantDeleteResponse,
    TenantListResponse,
    TenantResponse,
    TenantUpdate,
)


class TenantService:
    """Service class for tenant CRUD operations and business logic."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize tenant service with database session.
        
        Args:
            session: Database session with tenant context already set
        """
        self.session = session

    async def create_tenant(self, tenant_data: TenantCreate) -> TenantResponse:
        """
        Create a new tenant with validation and business logic.
        
        Args:
            tenant_data: Tenant creation data
            
        Returns:
            TenantResponse: Created tenant information
            
        Raises:
            HTTPException: For validation errors or constraint violations
        """
        # Validate parent tenant exists if specified
        if tenant_data.parent_tenant_id:
            parent = await self._get_tenant_by_id(tenant_data.parent_tenant_id)
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent tenant '{tenant_data.parent_tenant_id}' not found"
                )
            
            # Ensure parent is actually a parent tenant
            if parent.tenant_type != TenantType.PARENT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent tenant must be of type 'parent'"
                )
        
        # Check for unique name within parent hierarchy
        await self._validate_unique_name(
            tenant_data.name, 
            tenant_data.parent_tenant_id
        )
        
        # Create tenant entity
        tenant = Tenant(
            name=tenant_data.name.strip(),
            parent_tenant_id=tenant_data.parent_tenant_id,
            tenant_type=tenant_data.tenant_type,
            tenant_metadata=tenant_data.metadata or {}
        )
        
        try:
            self.session.add(tenant)
            await self.session.commit()
            await self.session.refresh(tenant)
        except IntegrityError as e:
            await self.session.rollback()
            if "uq_tenant_name_per_parent" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Tenant name must be unique within parent hierarchy"
                ) from None
            elif "ck_tenant_parent_logic" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tenant type and parent relationship are inconsistent"
                ) from None
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Database constraint violation: {str(e)}"
                ) from None
        
        return TenantResponse.model_validate(tenant)

    async def get_tenant_by_id(self, tenant_id: UUID) -> TenantResponse:
        """
        Get tenant by ID with access control validation.
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            TenantResponse: Tenant information
            
        Raises:
            HTTPException: If tenant not found or access denied
        """
        tenant = await self._get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_id}' not found or access denied"
            )
        
        return TenantResponse.model_validate(tenant)

    async def list_tenants(
        self,
        limit: int = 100,
        offset: int = 0,
        tenant_type: TenantType | None = None,
    ) -> TenantListResponse:
        """
        List tenants with pagination and filtering.
        
        Args:
            limit: Maximum number of results (1-1000)
            offset: Number of results to skip  
            tenant_type: Filter by tenant type
            
        Returns:
            TenantListResponse: Paginated list of tenants
        """
        # Validate pagination parameters
        if limit < 1 or limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be between 1 and 1000"
            )
        
        if offset < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Offset must be non-negative"
            )
        
        # Build query with filters
        query = select(Tenant)
        
        if tenant_type:
            query = query.where(Tenant.tenant_type == tenant_type)
        
        # Order by created_at descending for consistent pagination
        query = query.order_by(Tenant.created_at.desc())
        
        # Count query for total
        count_query = select(func.count(Tenant.tenant_id))
        if tenant_type:
            count_query = count_query.where(Tenant.tenant_type == tenant_type)
        
        # Execute queries
        total_result = await self.session.execute(count_query)
        total_count = total_result.scalar() or 0
        
        paginated_query = query.offset(offset).limit(limit)
        result = await self.session.execute(paginated_query)
        tenants = result.scalars().all()
        
        return TenantListResponse(
            tenants=tenants,
            total_count=total_count,
            limit=limit,
            offset=offset
        )

    async def update_tenant(
        self, 
        tenant_id: UUID, 
        tenant_data: TenantUpdate
    ) -> TenantResponse:
        """
        Update tenant information with validation.
        
        Args:
            tenant_id: Tenant UUID
            tenant_data: Update data
            
        Returns:
            TenantResponse: Updated tenant information
            
        Raises:
            HTTPException: If tenant not found or validation fails
        """
        tenant = await self._get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_id}' not found or access denied"
            )
        
        # Update fields if provided
        if tenant_data.name is not None:
            name = tenant_data.name.strip()
            # Check unique name constraint if name is changing
            if name != tenant.name:
                await self._validate_unique_name(
                    name, tenant.parent_tenant_id, tenant_id
                )
            tenant.name = name
        
        if tenant_data.metadata is not None:
            tenant.tenant_metadata = tenant_data.metadata
        
        try:
            await self.session.commit()
            await self.session.refresh(tenant)
        except IntegrityError as e:
            await self.session.rollback()
            if "uq_tenant_name_per_parent" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Tenant name must be unique within parent hierarchy"
                ) from None
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Database constraint violation: {str(e)}"
                ) from None
        
        return TenantResponse.model_validate(tenant)

    async def delete_tenant(self, tenant_id: UUID) -> TenantDeleteResponse:
        """
        Delete tenant with validation and cascading checks.
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            TenantDeleteResponse: Deletion confirmation
            
        Raises:
            HTTPException: If tenant not found, has subsidiaries, or access denied
        """
        tenant = await self._get_tenant_by_id_with_subsidiaries(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_id}' not found or access denied"
            )
        
        # Check if tenant has subsidiaries
        if tenant.has_subsidiaries:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot delete tenant with active subsidiaries. "
                    "Delete subsidiaries first."
                )
            )
        
        try:
            await self.session.delete(tenant)
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete tenant due to existing relationships: {str(e)}"
            ) from None
        
        return TenantDeleteResponse(
            message="Tenant successfully deleted",
            tenant_id=tenant_id
        )

    async def get_tenant_hierarchy(self, tenant_id: UUID) -> list[TenantResponse]:
        """
        Get tenant hierarchy (parent and all subsidiaries).
        
        Args:
            tenant_id: Root tenant UUID
            
        Returns:
            list[TenantResponse]: List of tenants in hierarchy
        """
        tenant = await self._get_tenant_by_id_with_subsidiaries(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_id}' not found or access denied"
            )
        
        hierarchy = [tenant]
        if tenant.is_parent:
            hierarchy.extend(tenant.subsidiaries)
        elif tenant.parent:
            # If requesting subsidiary, return parent and all siblings
            hierarchy.insert(0, tenant.parent)
            hierarchy.extend([
                s for s in tenant.parent.subsidiaries 
                if s.tenant_id != tenant_id
            ])
        
        return [TenantResponse.model_validate(t) for t in hierarchy]

    # Private helper methods
    
    async def _get_tenant_by_id(self, tenant_id: UUID) -> Tenant | None:
        """Get tenant by ID (respects RLS)."""
        query = select(Tenant).where(Tenant.tenant_id == tenant_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_tenant_by_id_with_subsidiaries(
        self, tenant_id: UUID
    ) -> Tenant | None:
        """Get tenant by ID with subsidiaries loaded (respects RLS)."""
        query = (
            select(Tenant)
            .where(Tenant.tenant_id == tenant_id)
            .options(selectinload(Tenant.subsidiaries), selectinload(Tenant.parent))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def _validate_unique_name(
        self, 
        name: str, 
        parent_tenant_id: UUID | None, 
        exclude_id: UUID | None = None
    ) -> None:
        """
        Validate tenant name is unique within parent hierarchy.
        
        Args:
            name: Tenant name to validate
            parent_tenant_id: Parent tenant ID (None for parent tenants)
            exclude_id: Tenant ID to exclude from uniqueness check (for updates)
            
        Raises:
            HTTPException: If name is not unique
        """
        query = select(Tenant).where(
            and_(
                Tenant.name == name,
                Tenant.parent_tenant_id == parent_tenant_id
            )
        )
        
        if exclude_id:
            query = query.where(Tenant.tenant_id != exclude_id)
        
        result = await self.session.execute(query)
        existing_tenant = result.scalar_one_or_none()
        
        if existing_tenant:
            parent_context = (
                f"parent '{parent_tenant_id}'"
                if parent_tenant_id
                else "root level"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tenant name '{name}' already exists under {parent_context}"
            )