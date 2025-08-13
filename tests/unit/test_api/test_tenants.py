"""
Comprehensive unit tests for tenant API endpoints.

Tests all tenant CRUD endpoints with various scenarios including
success cases, error handling, validation, and request/response patterns.
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from src.multi_tenant_db.models.tenant import TenantType
from src.multi_tenant_db.schemas.tenant import (
    TenantDeleteResponse,
    TenantListResponse,
    TenantResponse,
)
from src.multi_tenant_db.services.tenant import TenantService


class TestCreateTenant:
    """Test POST /api/v1/tenants endpoint."""

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_create_parent_tenant_success(
        self, mock_service_class, client, tenant_create_parent
    ):
        """Test successful parent tenant creation."""
        # Create appropriate mock response based on input
        from src.multi_tenant_db.schemas.tenant import TenantResponse
        from uuid import uuid4
        from datetime import datetime, timezone
        
        mock_response = TenantResponse(
            tenant_id=uuid4(),
            name=tenant_create_parent.name,
            tenant_type=tenant_create_parent.tenant_type,
            parent_tenant_id=tenant_create_parent.parent_tenant_id,
            tenant_metadata=tenant_create_parent.metadata,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Setup mock service
        mock_service = AsyncMock(spec=TenantService)
        mock_service.create_tenant.return_value = mock_response
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.post(
            "/api/v1/tenants",
            json=tenant_create_parent.model_dump(mode='json')
        )
        
        # Verify response
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "tenant_id" in data
        assert data["name"] == tenant_create_parent.name
        assert data["tenant_type"] == tenant_create_parent.tenant_type.value
        assert data["parent_tenant_id"] is None
        
        # Verify service was called
        mock_service.create_tenant.assert_called_once()

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_create_subsidiary_tenant_success(
        self, mock_service_class, client, tenant_create_subsidiary
    ):
        """Test successful subsidiary tenant creation."""
        # Create appropriate mock response based on input
        from src.multi_tenant_db.schemas.tenant import TenantResponse
        from uuid import uuid4
        from datetime import datetime, timezone
        
        mock_response = TenantResponse(
            tenant_id=uuid4(),
            name=tenant_create_subsidiary.name,
            tenant_type=tenant_create_subsidiary.tenant_type,
            parent_tenant_id=tenant_create_subsidiary.parent_tenant_id,
            tenant_metadata=tenant_create_subsidiary.metadata,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Setup mock service
        mock_service = AsyncMock(spec=TenantService)
        mock_service.create_tenant.return_value = mock_response
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.post(
            "/api/v1/tenants",
            json=tenant_create_subsidiary.model_dump(mode='json')
        )
        
        # Verify response
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "tenant_id" in data
        assert data["name"] == tenant_create_subsidiary.name
        assert data["tenant_type"] == tenant_create_subsidiary.tenant_type.value
        assert data["parent_tenant_id"] is not None
        
        # Verify service was called
        mock_service.create_tenant.assert_called_once()

    def test_create_tenant_invalid_data(self, client):
        """Test tenant creation with invalid data."""
        invalid_data = {
            "name": "",  # Empty name
            "tenant_type": "invalid_type",  # Invalid enum value
            "parent_tenant_id": "not-a-uuid"  # Invalid UUID
        }
        
        response = client.post("/api/v1/tenants", json=invalid_data)
        
        # Should return 422 for validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_tenant_missing_required_fields(self, client):
        """Test tenant creation with missing required fields."""
        incomplete_data = {
            "name": "Test Tenant"
            # Missing tenant_type
        }
        
        response = client.post("/api/v1/tenants", json=incomplete_data)
        
        # Should return 422 for validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_create_tenant_service_error(self, mock_service_class, client, tenant_create_parent):
        """Test tenant creation when service raises error."""
        # Setup mock service to raise HTTPException
        mock_service = AsyncMock(spec=TenantService)
        mock_service.create_tenant.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant name already exists"
        )
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.post(
            "/api/v1/tenants",
            json=tenant_create_parent.model_dump()
        )
        
        # Verify error response
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]


class TestListTenants:
    """Test GET /api/v1/tenants endpoint."""

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_list_tenants_success(self, mock_service_class, client, multiple_tenant_models):
        """Test successful tenant listing."""
        # Create expected response
        tenant_list_response = TenantListResponse(
            tenants=multiple_tenant_models[:2],
            total_count=len(multiple_tenant_models),
            limit=100,
            offset=0
        )
        
        # Setup mock service
        mock_service = AsyncMock(spec=TenantService)
        mock_service.list_tenants.return_value = tenant_list_response
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.get("/api/v1/tenants")
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tenants" in data
        assert "total_count" in data
        assert "limit" in data
        assert "offset" in data
        assert data["total_count"] == len(multiple_tenant_models)
        assert data["limit"] == 100
        assert data["offset"] == 0
        
        # Verify service was called with defaults
        mock_service.list_tenants.assert_called_once_with(
            limit=100, offset=0, tenant_type=None
        )

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_list_tenants_with_pagination(self, mock_service_class, client, multiple_tenant_models):
        """Test tenant listing with pagination parameters."""
        # Create expected response
        tenant_list_response = TenantListResponse(
            tenants=multiple_tenant_models[1:3],
            total_count=len(multiple_tenant_models),
            limit=2,
            offset=1
        )
        
        # Setup mock service
        mock_service = AsyncMock(spec=TenantService)
        mock_service.list_tenants.return_value = tenant_list_response
        mock_service_class.return_value = mock_service
        
        # Execute request with pagination
        response = client.get("/api/v1/tenants?limit=2&offset=1")
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["limit"] == 2
        assert data["offset"] == 1
        
        # Verify service was called with correct params
        mock_service.list_tenants.assert_called_once_with(
            limit=2, offset=1, tenant_type=None
        )

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_list_tenants_with_type_filter(self, mock_service_class, client, multiple_tenant_models):
        """Test tenant listing with type filtering."""
        # Filter for subsidiaries
        subsidiary_tenants = [t for t in multiple_tenant_models if t.tenant_type == TenantType.SUBSIDIARY]
        tenant_list_response = TenantListResponse(
            tenants=subsidiary_tenants,
            total_count=len(subsidiary_tenants),
            limit=100,
            offset=0
        )
        
        # Setup mock service
        mock_service = AsyncMock(spec=TenantService)
        mock_service.list_tenants.return_value = tenant_list_response
        mock_service_class.return_value = mock_service
        
        # Execute request with type filter
        response = client.get("/api/v1/tenants?tenant_type=subsidiary")
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == len(subsidiary_tenants)
        
        # Verify service was called with type filter
        mock_service.list_tenants.assert_called_once_with(
            limit=100, offset=0, tenant_type=TenantType.SUBSIDIARY
        )

    def test_list_tenants_invalid_limit(self, client):
        """Test tenant listing with invalid limit."""
        # Test limit too high
        response = client.get("/api/v1/tenants?limit=1001")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test limit too low
        response = client.get("/api/v1/tenants?limit=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_tenants_invalid_offset(self, client):
        """Test tenant listing with invalid offset."""
        response = client.get("/api/v1/tenants?offset=-1")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_tenants_invalid_tenant_type(self, client):
        """Test tenant listing with invalid tenant type."""
        response = client.get("/api/v1/tenants?tenant_type=invalid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetTenant:
    """Test GET /api/v1/tenants/{tenant_id} endpoint."""

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_get_tenant_success(
        self, mock_service_class, client, parent_tenant_id, tenant_response, tenant_headers
    ):
        """Test successful tenant retrieval."""
        # Setup mock service
        mock_service = AsyncMock(spec=TenantService)
        mock_service.get_tenant_by_id.return_value = tenant_response
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.get(
            f"/api/v1/tenants/{parent_tenant_id}",
            headers=tenant_headers
        )
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tenant_id" in data
        assert "name" in data
        assert "tenant_type" in data
        assert "created_at" in data
        assert "updated_at" in data
        
        # Verify service was called
        mock_service.get_tenant_by_id.assert_called_once_with(parent_tenant_id)

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_get_tenant_not_found(
        self, mock_service_class, client, non_existent_tenant_id, tenant_headers
    ):
        """Test tenant retrieval when tenant not found."""
        # Setup mock service to raise 404
        mock_service = AsyncMock(spec=TenantService)
        mock_service.get_tenant_by_id.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found or access denied"
        )
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.get(
            f"/api/v1/tenants/{non_existent_tenant_id}",
            headers=tenant_headers
        )
        
        # Verify error response
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]

    def test_get_tenant_invalid_uuid(self, client, tenant_headers):
        """Test tenant retrieval with invalid UUID."""
        response = client.get(
            "/api/v1/tenants/invalid-uuid",
            headers=tenant_headers
        )
        
        # Should return 422 for validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestUpdateTenant:
    """Test PUT /api/v1/tenants/{tenant_id} endpoint."""

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_update_tenant_success(
        self, mock_service_class, client, parent_tenant_id, tenant_update, tenant_response, tenant_headers
    ):
        """Test successful tenant update."""
        # Setup mock service
        mock_service = AsyncMock(spec=TenantService)
        mock_service.update_tenant.return_value = tenant_response
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.put(
            f"/api/v1/tenants/{parent_tenant_id}",
            json=tenant_update.model_dump(exclude_unset=True),
            headers=tenant_headers
        )
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tenant_id" in data
        assert "name" in data
        assert "updated_at" in data
        
        # Verify service was called
        mock_service.update_tenant.assert_called_once()
        args = mock_service.update_tenant.call_args[0]
        assert args[0] == parent_tenant_id
        assert isinstance(args[1], type(tenant_update))

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_update_tenant_not_found(
        self, mock_service_class, client, non_existent_tenant_id, tenant_update, tenant_headers
    ):
        """Test tenant update when tenant not found."""
        # Setup mock service to raise 404
        mock_service = AsyncMock(spec=TenantService)
        mock_service.update_tenant.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found or access denied"
        )
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.put(
            f"/api/v1/tenants/{non_existent_tenant_id}",
            json=tenant_update.model_dump(exclude_unset=True),
            headers=tenant_headers
        )
        
        # Verify error response
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_update_tenant_name_conflict(
        self, mock_service_class, client, parent_tenant_id, tenant_update, tenant_headers
    ):
        """Test tenant update with name conflict."""
        # Setup mock service to raise 409
        mock_service = AsyncMock(spec=TenantService)
        mock_service.update_tenant.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant name must be unique within parent hierarchy"
        )
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.put(
            f"/api/v1/tenants/{parent_tenant_id}",
            json=tenant_update.model_dump(exclude_unset=True),
            headers=tenant_headers
        )
        
        # Verify error response
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "unique" in response.json()["detail"]

    def test_update_tenant_invalid_data(self, client, parent_tenant_id, tenant_headers):
        """Test tenant update with invalid data."""
        invalid_update = {
            "name": "",  # Empty name
            "metadata": "not-a-dict"  # Invalid metadata type
        }
        
        response = client.put(
            f"/api/v1/tenants/{parent_tenant_id}",
            json=invalid_update,
            headers=tenant_headers
        )
        
        # Should return 422 for validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_update_tenant_empty_request(self, client, parent_tenant_id, tenant_headers):
        """Test tenant update with empty request body."""
        response = client.put(
            f"/api/v1/tenants/{parent_tenant_id}",
            json={},  # Empty update
            headers=tenant_headers
        )
        
        # Empty update should still be valid (no fields to update)
        # This will depend on service implementation
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]


class TestDeleteTenant:
    """Test DELETE /api/v1/tenants/{tenant_id} endpoint."""

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_delete_tenant_success(
        self, mock_service_class, client, subsidiary_tenant_id, tenant_headers
    ):
        """Test successful tenant deletion."""
        # Create expected response
        delete_response = TenantDeleteResponse(
            message="Tenant successfully deleted",
            tenant_id=subsidiary_tenant_id
        )
        
        # Setup mock service
        mock_service = AsyncMock(spec=TenantService)
        mock_service.delete_tenant.return_value = delete_response
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.delete(
            f"/api/v1/tenants/{subsidiary_tenant_id}",
            headers=tenant_headers
        )
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "tenant_id" in data
        assert data["tenant_id"] == str(subsidiary_tenant_id)
        assert "successfully deleted" in data["message"]
        
        # Verify service was called
        mock_service.delete_tenant.assert_called_once_with(subsidiary_tenant_id)

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_delete_tenant_not_found(
        self, mock_service_class, client, non_existent_tenant_id, tenant_headers
    ):
        """Test tenant deletion when tenant not found."""
        # Setup mock service to raise 404
        mock_service = AsyncMock(spec=TenantService)
        mock_service.delete_tenant.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found or access denied"
        )
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.delete(
            f"/api/v1/tenants/{non_existent_tenant_id}",
            headers=tenant_headers
        )
        
        # Verify error response
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_delete_tenant_has_subsidiaries(
        self, mock_service_class, client, parent_tenant_id, tenant_headers
    ):
        """Test tenant deletion when tenant has subsidiaries."""
        # Setup mock service to raise 409
        mock_service = AsyncMock(spec=TenantService)
        mock_service.delete_tenant.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete tenant with active subsidiaries. Delete subsidiaries first."
        )
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.delete(
            f"/api/v1/tenants/{parent_tenant_id}",
            headers=tenant_headers
        )
        
        # Verify error response
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "subsidiaries" in response.json()["detail"]

    def test_delete_tenant_invalid_uuid(self, client, tenant_headers):
        """Test tenant deletion with invalid UUID."""
        response = client.delete(
            "/api/v1/tenants/invalid-uuid",
            headers=tenant_headers
        )
        
        # Should return 422 for validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetTenantHierarchy:
    """Test GET /api/v1/tenants/{tenant_id}/hierarchy endpoint."""

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_get_hierarchy_success(
        self, mock_service_class, client, parent_tenant_id, multiple_tenant_models, tenant_headers
    ):
        """Test successful hierarchy retrieval."""
        # Create expected hierarchy response (parent + subsidiaries)
        hierarchy_response = [
            TenantResponse.model_validate(tenant) for tenant in multiple_tenant_models
        ]
        
        # Setup mock service
        mock_service = AsyncMock(spec=TenantService)
        mock_service.get_tenant_hierarchy.return_value = hierarchy_response
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.get(
            f"/api/v1/tenants/{parent_tenant_id}/hierarchy",
            headers=tenant_headers
        )
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == len(hierarchy_response)
        
        # Verify each item has tenant structure
        for tenant in data:
            assert "tenant_id" in tenant
            assert "name" in tenant
            assert "tenant_type" in tenant
        
        # Verify service was called
        mock_service.get_tenant_hierarchy.assert_called_once_with(parent_tenant_id)

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_get_hierarchy_tenant_not_found(
        self, mock_service_class, client, non_existent_tenant_id, tenant_headers
    ):
        """Test hierarchy retrieval when tenant not found."""
        # Setup mock service to raise 404
        mock_service = AsyncMock(spec=TenantService)
        mock_service.get_tenant_hierarchy.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found or access denied"
        )
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.get(
            f"/api/v1/tenants/{non_existent_tenant_id}/hierarchy",
            headers=tenant_headers
        )
        
        # Verify error response
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_get_hierarchy_single_tenant(
        self, mock_service_class, client, subsidiary_tenant_id, subsidiary_tenant_model, tenant_headers
    ):
        """Test hierarchy retrieval for tenant without subsidiaries."""
        # Create expected response (just the tenant itself)
        hierarchy_response = [TenantResponse.model_validate(subsidiary_tenant_model)]
        
        # Setup mock service
        mock_service = AsyncMock(spec=TenantService)
        mock_service.get_tenant_hierarchy.return_value = hierarchy_response
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.get(
            f"/api/v1/tenants/{subsidiary_tenant_id}/hierarchy",
            headers=tenant_headers
        )
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["tenant_id"] == str(subsidiary_tenant_id)

    def test_get_hierarchy_invalid_uuid(self, client, tenant_headers):
        """Test hierarchy retrieval with invalid UUID."""
        response = client.get(
            "/api/v1/tenants/invalid-uuid/hierarchy",
            headers=tenant_headers
        )
        
        # Should return 422 for validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestTenantAPIErrorHandling:
    """Test error handling across all tenant endpoints."""

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_service_initialization_error(self, mock_service_class, client, parent_tenant_id, tenant_headers):
        """Test handling when service initialization fails."""
        # Mock service class to raise exception
        mock_service_class.side_effect = Exception("Service initialization failed")
        
        # Execute request
        response = client.get(
            f"/api/v1/tenants/{parent_tenant_id}",
            headers=tenant_headers
        )
        
        # Should return 500 for internal server error
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("src.multi_tenant_db.api.v1.tenants.TenantService")
    def test_unexpected_service_error(self, mock_service_class, client, parent_tenant_id, tenant_headers):
        """Test handling of unexpected service errors."""
        # Setup mock service to raise unexpected exception
        mock_service = AsyncMock(spec=TenantService)
        mock_service.get_tenant_by_id.side_effect = Exception("Unexpected error")
        mock_service_class.return_value = mock_service
        
        # Execute request
        response = client.get(
            f"/api/v1/tenants/{parent_tenant_id}",
            headers=tenant_headers
        )
        
        # Should return 500 for internal server error
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestTenantAPIValidation:
    """Test request validation across tenant endpoints."""

    def test_create_tenant_schema_validation(self, client):
        """Test comprehensive schema validation for tenant creation."""
        test_cases = [
            # Invalid tenant type
            {
                "data": {"name": "Test", "tenant_type": "invalid"},
                "expected_error": "tenant_type"
            },
            # Parent with parent_tenant_id
            {
                "data": {
                    "name": "Test", 
                    "tenant_type": "parent", 
                    "parent_tenant_id": "550e8400-e29b-41d4-a716-446655440000"
                },
                "expected_error": "Parent tenants cannot have a parent tenant"
            },
            # Subsidiary without parent_tenant_id
            {
                "data": {"name": "Test", "tenant_type": "subsidiary"},
                "expected_error": "Subsidiary tenants must have a parent tenant"
            },
            # Name too long
            {
                "data": {
                    "name": "x" * 201, 
                    "tenant_type": "parent"
                },
                "expected_error": "name"
            },
            # Invalid metadata
            {
                "data": {
                    "name": "Test",
                    "tenant_type": "parent", 
                    "metadata": "not-a-dict"
                },
                "expected_error": "metadata"
            }
        ]
        
        for case in test_cases:
            response = client.post("/api/v1/tenants", json=case["data"])
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            # Additional validation of error message could be added here

    def test_update_tenant_schema_validation(self, client, parent_tenant_id, tenant_headers):
        """Test schema validation for tenant updates."""
        test_cases = [
            # Name too long
            {
                "data": {"name": "x" * 201},
                "expected_field": "name"
            },
            # Invalid metadata type
            {
                "data": {"metadata": "not-a-dict"},
                "expected_field": "metadata"
            },
            # Empty name (whitespace only)
            {
                "data": {"name": "   "},
                "expected_field": "name"
            }
        ]
        
        for case in test_cases:
            response = client.put(
                f"/api/v1/tenants/{parent_tenant_id}",
                json=case["data"],
                headers=tenant_headers
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY