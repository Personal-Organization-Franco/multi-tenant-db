"""
Comprehensive unit tests for TenantService.

Tests all business logic, CRUD operations, validation methods,
and error handling in the tenant service layer.
"""

from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from src.multi_tenant_db.models.tenant import Tenant, TenantType
from src.multi_tenant_db.schemas.tenant import (
    TenantCreate,
    TenantDeleteResponse,
    TenantListResponse,
    TenantResponse,
    TenantUpdate,
)
from src.multi_tenant_db.services.tenant import TenantService


class TestTenantServiceInit:
    """Test TenantService initialization."""

    def test_tenant_service_init(self, mock_db_session):
        """Test TenantService initializes correctly with session."""
        service = TenantService(mock_db_session)
        assert service.session == mock_db_session


class TestTenantServiceCreateTenant:
    """Test tenant creation functionality."""

    @pytest.mark.asyncio
    async def test_create_parent_tenant_success(
        self, mock_db_session, tenant_create_parent, mock_execute_result, parent_tenant_model
    ):
        """Test successful parent tenant creation."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = None  # No existing tenant
        
        # Mock the refresh to populate the tenant with required fields
        def mock_refresh(tenant):
            tenant.tenant_id = parent_tenant_model.tenant_id
            tenant.created_at = parent_tenant_model.created_at
            tenant.updated_at = parent_tenant_model.updated_at
        
        mock_db_session.refresh.side_effect = mock_refresh
        
        service = TenantService(mock_db_session)
        
        # Execute
        result = await service.create_tenant(tenant_create_parent)
        
        # Verify
        assert isinstance(result, TenantResponse)
        assert result.name == tenant_create_parent.name
        assert result.tenant_type == tenant_create_parent.tenant_type
        assert result.parent_tenant_id is None
        assert result.tenant_id == parent_tenant_model.tenant_id
        
        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subsidiary_tenant_success(
        self, mock_db_session, tenant_create_subsidiary, parent_tenant_model, subsidiary_tenant_model, mock_execute_result
    ):
        """Test successful subsidiary tenant creation."""
        # Setup mocks - parent exists
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.side_effect = [
            parent_tenant_model,  # Parent exists
            None  # No existing tenant with same name
        ]
        
        # Mock the refresh to populate the tenant with required fields
        def mock_refresh(tenant):
            tenant.tenant_id = subsidiary_tenant_model.tenant_id
            tenant.created_at = subsidiary_tenant_model.created_at
            tenant.updated_at = subsidiary_tenant_model.updated_at
        
        mock_db_session.refresh.side_effect = mock_refresh
        
        service = TenantService(mock_db_session)
        
        # Execute
        result = await service.create_tenant(tenant_create_subsidiary)
        
        # Verify
        assert isinstance(result, TenantResponse)
        assert result.name == tenant_create_subsidiary.name
        assert result.tenant_type == tenant_create_subsidiary.tenant_type
        assert result.parent_tenant_id == tenant_create_subsidiary.parent_tenant_id
        assert result.tenant_id == subsidiary_tenant_model.tenant_id
        
        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_tenant_parent_not_found(
        self, mock_db_session, tenant_create_subsidiary, mock_execute_result
    ):
        """Test tenant creation fails when parent not found."""
        # Setup mocks - parent doesn't exist
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = None
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.create_tenant(tenant_create_subsidiary)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Parent tenant" in str(exc_info.value.detail)
        assert "not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_tenant_parent_not_parent_type(
        self, mock_db_session, tenant_create_subsidiary, subsidiary_tenant_model, mock_execute_result
    ):
        """Test tenant creation fails when parent is not parent type."""
        # Setup mocks - parent exists but is subsidiary type
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.side_effect = [
            subsidiary_tenant_model,  # Parent exists but wrong type
        ]
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.create_tenant(tenant_create_subsidiary)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Parent tenant must be of type 'parent'" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_tenant_name_not_unique(
        self, mock_db_session, tenant_create_parent, parent_tenant_model, mock_execute_result
    ):
        """Test tenant creation fails when name not unique."""
        # Setup mocks - existing tenant with same name
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = parent_tenant_model
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.create_tenant(tenant_create_parent)
        
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert "Tenant name already exists" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_tenant_integrity_error_unique_constraint(
        self, mock_db_session, tenant_create_parent, mock_execute_result
    ):
        """Test tenant creation handles unique constraint violation."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = None
        
        # Mock IntegrityError on commit
        integrity_error = IntegrityError("uq_tenant_name_per_parent", None, None)
        mock_db_session.commit.side_effect = integrity_error
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.create_tenant(tenant_create_parent)
        
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert "unique within parent hierarchy" in str(exc_info.value.detail)
        mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_tenant_integrity_error_parent_logic(
        self, mock_db_session, tenant_create_parent, mock_execute_result
    ):
        """Test tenant creation handles parent logic constraint violation."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = None
        
        # Mock IntegrityError on commit
        integrity_error = IntegrityError("ck_tenant_parent_logic", None, None)
        mock_db_session.commit.side_effect = integrity_error
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.create_tenant(tenant_create_parent)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "inconsistent" in str(exc_info.value.detail)
        mock_db_session.rollback.assert_called_once()


class TestTenantServiceGetTenant:
    """Test tenant retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_tenant_by_id_success(
        self, mock_db_session, parent_tenant_model, parent_tenant_id, mock_execute_result
    ):
        """Test successful tenant retrieval by ID."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = parent_tenant_model
        
        service = TenantService(mock_db_session)
        
        # Execute
        result = await service.get_tenant_by_id(parent_tenant_id)
        
        # Verify
        assert isinstance(result, TenantResponse)
        assert result.tenant_id == parent_tenant_id
        assert result.name == parent_tenant_model.name

    @pytest.mark.asyncio
    async def test_get_tenant_by_id_not_found(
        self, mock_db_session, non_existent_tenant_id, mock_execute_result
    ):
        """Test tenant retrieval fails when tenant not found."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = None
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.get_tenant_by_id(non_existent_tenant_id)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found or access denied" in str(exc_info.value.detail)


class TestTenantServiceListTenants:
    """Test tenant listing functionality."""

    @pytest.mark.asyncio
    async def test_list_tenants_success(
        self, mock_db_session, multiple_tenant_models, mock_execute_result
    ):
        """Test successful tenant listing with pagination."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        
        # Mock count query result
        count_result = Mock()
        count_result.scalar.return_value = len(multiple_tenant_models)
        
        # Mock pagination query result
        list_result = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = multiple_tenant_models[:2]  # Simulate pagination
        list_result.scalars.return_value = mock_scalars
        
        mock_db_session.execute.side_effect = [count_result, list_result]
        
        service = TenantService(mock_db_session)
        
        # Execute
        result = await service.list_tenants(limit=2, offset=0)
        
        # Verify
        assert isinstance(result, TenantListResponse)
        assert result.total_count == len(multiple_tenant_models)
        assert result.limit == 2
        assert result.offset == 0
        assert len(result.tenants) == 2

    @pytest.mark.asyncio
    async def test_list_tenants_with_type_filter(
        self, mock_db_session, multiple_tenant_models, mock_execute_result
    ):
        """Test tenant listing with type filtering."""
        # Filter for subsidiaries only
        subsidiary_tenants = [t for t in multiple_tenant_models if t.tenant_type == TenantType.SUBSIDIARY]
        
        # Setup mocks
        count_result = Mock()
        count_result.scalar.return_value = len(subsidiary_tenants)
        
        list_result = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = subsidiary_tenants
        list_result.scalars.return_value = mock_scalars
        
        mock_db_session.execute.side_effect = [count_result, list_result]
        
        service = TenantService(mock_db_session)
        
        # Execute
        result = await service.list_tenants(tenant_type=TenantType.SUBSIDIARY)
        
        # Verify
        assert result.total_count == len(subsidiary_tenants)
        assert len(result.tenants) == len(subsidiary_tenants)

    @pytest.mark.asyncio
    async def test_list_tenants_invalid_limit(self, mock_db_session):
        """Test tenant listing fails with invalid limit."""
        service = TenantService(mock_db_session)
        
        # Test limit too low
        with pytest.raises(HTTPException) as exc_info:
            await service.list_tenants(limit=0)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "between 1 and 1000" in str(exc_info.value.detail)
        
        # Test limit too high
        with pytest.raises(HTTPException) as exc_info:
            await service.list_tenants(limit=1001)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_list_tenants_invalid_offset(self, mock_db_session):
        """Test tenant listing fails with invalid offset."""
        service = TenantService(mock_db_session)
        
        # Test negative offset
        with pytest.raises(HTTPException) as exc_info:
            await service.list_tenants(offset=-1)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "non-negative" in str(exc_info.value.detail)


class TestTenantServiceUpdateTenant:
    """Test tenant update functionality."""

    @pytest.mark.asyncio
    async def test_update_tenant_success(
        self, mock_db_session, parent_tenant_model, parent_tenant_id, tenant_update, mock_execute_result
    ):
        """Test successful tenant update."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.side_effect = [
            parent_tenant_model,  # Tenant exists
            None  # No name conflict
        ]
        
        # Mock the refresh to ensure updated_at is refreshed
        def mock_refresh(tenant):
            tenant.updated_at = parent_tenant_model.updated_at
        
        mock_db_session.refresh.side_effect = mock_refresh
        
        service = TenantService(mock_db_session)
        
        # Execute
        result = await service.update_tenant(parent_tenant_id, tenant_update)
        
        # Verify
        assert isinstance(result, TenantResponse)
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_tenant_not_found(
        self, mock_db_session, non_existent_tenant_id, tenant_update, mock_execute_result
    ):
        """Test tenant update fails when tenant not found."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = None
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.update_tenant(non_existent_tenant_id, tenant_update)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found or access denied" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_tenant_name_conflict(
        self, mock_db_session, parent_tenant_model, parent_tenant_id, tenant_update, mock_execute_result
    ):
        """Test tenant update fails when name conflicts."""
        # Create a different tenant with conflicting name
        conflicting_tenant = Tenant(
            tenant_id=uuid4(),
            name=tenant_update.name,
            tenant_type=TenantType.PARENT,
            parent_tenant_id=None
        )
        
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.side_effect = [
            parent_tenant_model,  # Tenant exists
            conflicting_tenant  # Name conflict exists
        ]
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.update_tenant(parent_tenant_id, tenant_update)
        
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_tenant_integrity_error(
        self, mock_db_session, parent_tenant_model, parent_tenant_id, tenant_update, mock_execute_result
    ):
        """Test tenant update handles integrity error."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.side_effect = [
            parent_tenant_model,  # Tenant exists
            None  # No name conflict initially
        ]
        
        # Mock IntegrityError on commit
        integrity_error = IntegrityError("uq_tenant_name_per_parent", None, None)
        mock_db_session.commit.side_effect = integrity_error
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.update_tenant(parent_tenant_id, tenant_update)
        
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        mock_db_session.rollback.assert_called_once()


class TestTenantServiceDeleteTenant:
    """Test tenant deletion functionality."""

    @pytest.mark.asyncio
    async def test_delete_tenant_success(
        self, mock_db_session, subsidiary_tenant_model, subsidiary_tenant_id, mock_execute_result
    ):
        """Test successful tenant deletion."""
        # Ensure tenant has no subsidiaries
        subsidiary_tenant_model.subsidiaries = []
        
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = subsidiary_tenant_model
        
        service = TenantService(mock_db_session)
        
        # Execute
        result = await service.delete_tenant(subsidiary_tenant_id)
        
        # Verify
        assert isinstance(result, TenantDeleteResponse)
        assert result.tenant_id == subsidiary_tenant_id
        assert "successfully deleted" in result.message
        
        mock_db_session.delete.assert_called_once_with(subsidiary_tenant_model)
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_tenant_not_found(
        self, mock_db_session, non_existent_tenant_id, mock_execute_result
    ):
        """Test tenant deletion fails when tenant not found."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = None
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_tenant(non_existent_tenant_id)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found or access denied" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_tenant_has_subsidiaries(
        self, mock_db_session, parent_tenant_model, parent_tenant_id, subsidiary_tenant_model, mock_execute_result
    ):
        """Test tenant deletion fails when tenant has subsidiaries."""
        # Ensure parent has subsidiaries
        parent_tenant_model.subsidiaries = [subsidiary_tenant_model]
        
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = parent_tenant_model
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_tenant(parent_tenant_id)
        
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert "active subsidiaries" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_tenant_integrity_error(
        self, mock_db_session, subsidiary_tenant_model, subsidiary_tenant_id, mock_execute_result
    ):
        """Test tenant deletion handles integrity error."""
        # Ensure tenant has no subsidiaries
        subsidiary_tenant_model.subsidiaries = []
        
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = subsidiary_tenant_model
        
        # Mock IntegrityError on commit
        integrity_error = IntegrityError("foreign key constraint", None, None)
        mock_db_session.commit.side_effect = integrity_error
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_tenant(subsidiary_tenant_id)
        
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert "existing relationships" in str(exc_info.value.detail)
        mock_db_session.rollback.assert_called_once()


class TestTenantServiceGetHierarchy:
    """Test tenant hierarchy functionality."""

    @pytest.mark.asyncio
    async def test_get_hierarchy_parent_tenant(
        self, mock_db_session, parent_tenant_model, parent_tenant_id, subsidiary_tenant_model, mock_execute_result
    ):
        """Test getting hierarchy for parent tenant."""
        # Setup parent with subsidiaries
        parent_tenant_model.subsidiaries = [subsidiary_tenant_model]
        
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = parent_tenant_model
        
        service = TenantService(mock_db_session)
        
        # Execute
        result = await service.get_tenant_hierarchy(parent_tenant_id)
        
        # Verify
        assert isinstance(result, list)
        assert len(result) == 2  # Parent + 1 subsidiary
        assert all(isinstance(tenant, TenantResponse) for tenant in result)

    @pytest.mark.asyncio
    async def test_get_hierarchy_subsidiary_tenant(
        self, mock_db_session, subsidiary_tenant_model, subsidiary_tenant_id, parent_tenant_model, mock_execute_result
    ):
        """Test getting hierarchy for subsidiary tenant."""
        # Setup subsidiary with parent
        subsidiary_tenant_model.parent = parent_tenant_model
        parent_tenant_model.subsidiaries = [subsidiary_tenant_model]
        
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = subsidiary_tenant_model
        
        service = TenantService(mock_db_session)
        
        # Execute
        result = await service.get_tenant_hierarchy(subsidiary_tenant_id)
        
        # Verify
        assert isinstance(result, list)
        assert len(result) >= 1  # At least the subsidiary itself
        assert all(isinstance(tenant, TenantResponse) for tenant in result)

    @pytest.mark.asyncio
    async def test_get_hierarchy_tenant_not_found(
        self, mock_db_session, non_existent_tenant_id, mock_execute_result
    ):
        """Test getting hierarchy fails when tenant not found."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = None
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service.get_tenant_hierarchy(non_existent_tenant_id)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found or access denied" in str(exc_info.value.detail)


class TestTenantServicePrivateHelpers:
    """Test private helper methods."""

    @pytest.mark.asyncio
    async def test_get_tenant_by_id_helper(
        self, mock_db_session, parent_tenant_model, parent_tenant_id, mock_execute_result
    ):
        """Test _get_tenant_by_id helper method."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = parent_tenant_model
        
        service = TenantService(mock_db_session)
        
        # Execute
        result = await service._get_tenant_by_id(parent_tenant_id)
        
        # Verify
        assert result == parent_tenant_model

    @pytest.mark.asyncio
    async def test_get_tenant_by_id_with_subsidiaries_helper(
        self, mock_db_session, parent_tenant_model, parent_tenant_id, mock_execute_result
    ):
        """Test _get_tenant_by_id_with_subsidiaries helper method."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = parent_tenant_model
        
        service = TenantService(mock_db_session)
        
        # Execute
        result = await service._get_tenant_by_id_with_subsidiaries(parent_tenant_id)
        
        # Verify
        assert result == parent_tenant_model

    @pytest.mark.asyncio
    async def test_validate_unique_name_success(
        self, mock_db_session, mock_execute_result
    ):
        """Test _validate_unique_name when name is unique."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = None  # No existing tenant
        
        service = TenantService(mock_db_session)
        
        # Execute - should not raise exception
        await service._validate_unique_name("Unique Name", None)
        
        # Verify query was executed
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_unique_name_conflict(
        self, mock_db_session, parent_tenant_model, mock_execute_result
    ):
        """Test _validate_unique_name when name conflicts."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = parent_tenant_model
        
        service = TenantService(mock_db_session)
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await service._validate_unique_name(parent_tenant_model.name, None)
        
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validate_unique_name_with_exclude(
        self, mock_db_session, parent_tenant_model, mock_execute_result
    ):
        """Test _validate_unique_name excludes specific tenant ID."""
        # Setup mocks
        mock_db_session.execute.return_value = mock_execute_result
        mock_execute_result.scalar_one_or_none.return_value = None  # No conflict after exclusion
        
        service = TenantService(mock_db_session)
        
        # Execute - should not raise exception when excluding the same tenant
        await service._validate_unique_name(
            parent_tenant_model.name, 
            None, 
            exclude_id=parent_tenant_model.tenant_id
        )
        
        # Verify query was executed
        mock_db_session.execute.assert_called_once()