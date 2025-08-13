"""
Integration tests for tenant API endpoints.

Tests complete tenant CRUD workflows with real database operations,
tenant isolation, and business scenarios.
"""

import time
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.multi_tenant_db.models.tenant import Tenant, TenantType


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.tenant
class TestTenantCRUDIntegration:
    """Integration tests for tenant CRUD operations."""

    async def test_create_parent_tenant_full_workflow(
        self,
        integration_client: AsyncClient,
        hsbc_headers: dict[str, str],
        validate_tenant_response,
        tenant_response_fields: set[str],
        performance_threshold_ms: int,
    ) -> None:
        """Test complete parent tenant creation workflow."""
        tenant_data = {
            "name": "Goldman Sachs Group Inc",
            "tenant_type": "parent",
            "metadata": {
                "country": "United States",
                "headquarters": "New York",
                "business_type": "investment_bank",
                "founded_year": 1869,
                "employee_count": 45000,
                "regulatory_licenses": [
                    "SEC_registration",
                    "FINRA_membership",
                    "FDIC_insurance"
                ],
                "primary_currency": "USD",
                "market_cap_billion_usd": 120.8
            }
        }

        start_time = time.time()
        response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=tenant_data
        )
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000

        # Validate response
        assert response.status_code == 201
        
        response_data = response.json()
        assert validate_tenant_response(response_data, tenant_response_fields)
        
        # Validate response content
        assert response_data["name"] == tenant_data["name"]
        assert response_data["tenant_type"] == "parent"
        assert response_data["parent_tenant_id"] is None
        assert "tenant_id" in response_data
        assert UUID(response_data["tenant_id"])  # Valid UUID
        
        # Validate metadata
        assert response_data["metadata"] == tenant_data["metadata"]
        
        # Validate timestamps
        assert "created_at" in response_data
        assert "updated_at" in response_data
        
        # Validate performance
        assert response_time_ms <= performance_threshold_ms

    async def test_create_subsidiary_tenant_with_parent(
        self,
        integration_client: AsyncClient,
        hsbc_parent_tenant: Tenant,
        hsbc_headers: dict[str, str],
        validate_tenant_response,
        tenant_response_fields: set[str],
    ) -> None:
        """Test subsidiary tenant creation with existing parent."""
        subsidiary_data = {
            "name": "HSBC Bank Middle East Limited",
            "tenant_type": "subsidiary",
            "parent_tenant_id": str(hsbc_parent_tenant.tenant_id),
            "metadata": {
                "country": "United Arab Emirates",
                "region": "Middle East",
                "business_unit": "retail_banking",
                "local_currency": "AED",
                "employee_count": 3500,
                "local_licenses": [
                    "CBUAE_banking_license",
                    "DFSA_authorization"
                ],
                "established_year": 1946,
                "branches": 28
            }
        }

        response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=subsidiary_data
        )

        assert response.status_code == 201
        
        response_data = response.json()
        assert validate_tenant_response(response_data, tenant_response_fields)
        
        # Validate subsidiary-specific fields
        assert response_data["name"] == subsidiary_data["name"]
        assert response_data["tenant_type"] == "subsidiary"
        assert response_data["parent_tenant_id"] == subsidiary_data["parent_tenant_id"]
        assert response_data["metadata"] == subsidiary_data["metadata"]

    async def test_get_tenant_with_rls_context(
        self,
        integration_client: AsyncClient,
        hsbc_parent_tenant: Tenant,
        hsbc_hk_subsidiary: Tenant,
        hsbc_headers: dict[str, str],
        hsbc_hk_headers: dict[str, str],
    ) -> None:
        """Test tenant retrieval with RLS context."""
        # Parent should be able to access its own data
        response = await integration_client.get(
            f"/api/v1/tenants/{hsbc_parent_tenant.tenant_id}",
            headers=hsbc_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["tenant_id"] == str(hsbc_parent_tenant.tenant_id)
        assert data["name"] == hsbc_parent_tenant.name

        # Parent should be able to access subsidiary data
        response = await integration_client.get(
            f"/api/v1/tenants/{hsbc_hk_subsidiary.tenant_id}",
            headers=hsbc_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["tenant_id"] == str(hsbc_hk_subsidiary.tenant_id)
        assert data["name"] == hsbc_hk_subsidiary.name

        # Subsidiary should be able to access its own data
        response = await integration_client.get(
            f"/api/v1/tenants/{hsbc_hk_subsidiary.tenant_id}",
            headers=hsbc_hk_headers
        )
        assert response.status_code == 200

    async def test_update_tenant_full_workflow(
        self,
        integration_client: AsyncClient,
        hsbc_hk_subsidiary: Tenant,
        hsbc_headers: dict[str, str],
        validate_tenant_response,
        tenant_response_fields: set[str],
    ) -> None:
        """Test complete tenant update workflow."""
        update_data = {
            "name": "HSBC Bank (Hong Kong) Limited - Updated",
            "metadata": {
                "country": "Hong Kong",
                "region": "Asia Pacific",
                "business_unit": "retail_banking",
                "local_currency": "HKD",
                "employee_count": 16000,  # Updated
                "local_licenses": [
                    "HKMA_banking_license",
                    "SFC_type_1_license",
                    "MPF_registration",
                    "AMLO_license"  # New license
                ],
                "established_year": 1865,
                "branches": 135,  # Updated
                "parent_company": "HSBC Holdings plc",
                "last_audit": "2025-08-01",  # New field
                "compliance_status": "excellent"  # New field
            }
        }

        response = await integration_client.put(
            f"/api/v1/tenants/{hsbc_hk_subsidiary.tenant_id}",
            headers=hsbc_headers,
            json=update_data
        )

        assert response.status_code == 200
        
        response_data = response.json()
        assert validate_tenant_response(response_data, tenant_response_fields)
        
        # Validate updated fields
        assert response_data["name"] == update_data["name"]
        assert response_data["metadata"]["employee_count"] == 16000
        assert response_data["metadata"]["branches"] == 135
        assert "AMLO_license" in response_data["metadata"]["local_licenses"]
        assert response_data["metadata"]["last_audit"] == "2025-08-01"
        assert response_data["metadata"]["compliance_status"] == "excellent"
        
        # Validate unchanged fields
        assert response_data["tenant_type"] == "subsidiary"
        assert response_data["parent_tenant_id"] == str(hsbc_hk_subsidiary.parent_tenant_id)

    async def test_delete_tenant_cascade_workflow(
        self,
        integration_client: AsyncClient,
        integration_db_session: AsyncSession,
        hsbc_headers: dict[str, str],
    ) -> None:
        """Test tenant deletion workflow."""
        # Create a new tenant for deletion (avoid affecting other tests)
        create_data = {
            "name": "Test Tenant for Deletion",
            "tenant_type": "parent",
            "metadata": {
                "country": "Test Country",
                "status": "test"
            }
        }

        create_response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=create_data
        )
        assert create_response.status_code == 201
        
        tenant_id = create_response.json()["tenant_id"]

        # Delete the tenant
        delete_response = await integration_client.delete(
            f"/api/v1/tenants/{tenant_id}",
            headers=hsbc_headers
        )
        assert delete_response.status_code == 204

        # Verify tenant is deleted
        get_response = await integration_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=hsbc_headers
        )
        assert get_response.status_code == 404

    async def test_list_tenants_with_pagination(
        self,
        integration_client: AsyncClient,
        hsbc_parent_tenant: Tenant,
        hsbc_hk_subsidiary: Tenant,
        hsbc_london_subsidiary: Tenant,
        hsbc_headers: dict[str, str],
    ) -> None:
        """Test tenant listing with pagination and filtering."""
        # Test basic listing
        response = await integration_client.get(
            "/api/v1/tenants/",
            headers=hsbc_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data
        
        # Should see at least our test tenants
        assert data["total"] >= 3
        assert len(data["items"]) >= 3

        # Test pagination
        response = await integration_client.get(
            "/api/v1/tenants/?page=1&size=2",
            headers=hsbc_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["page"] == 1
        assert data["size"] == 2
        assert len(data["items"]) <= 2

        # Test filtering by tenant type
        response = await integration_client.get(
            "/api/v1/tenants/?tenant_type=parent",
            headers=hsbc_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        for item in data["items"]:
            assert item["tenant_type"] == "parent"


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.tenant
class TestTenantIsolationIntegration:
    """Integration tests for tenant data isolation."""

    async def test_cross_tenant_access_denial(
        self,
        integration_client: AsyncClient,
        hsbc_parent_tenant: Tenant,
        barclays_parent_tenant: Tenant,
        hsbc_headers: dict[str, str],
        barclays_headers: dict[str, str],
    ) -> None:
        """Test that tenants cannot access each other's data."""
        # HSBC should not be able to see Barclays tenant
        response = await integration_client.get(
            f"/api/v1/tenants/{barclays_parent_tenant.tenant_id}",
            headers=hsbc_headers
        )
        assert response.status_code == 404

        # Barclays should not be able to see HSBC tenant
        response = await integration_client.get(
            f"/api/v1/tenants/{hsbc_parent_tenant.tenant_id}",
            headers=barclays_headers
        )
        assert response.status_code == 404

        # Each should only see their own tenant in listings
        hsbc_response = await integration_client.get(
            "/api/v1/tenants/",
            headers=hsbc_headers
        )
        assert hsbc_response.status_code == 200
        hsbc_data = hsbc_response.json()
        
        barclays_response = await integration_client.get(
            "/api/v1/tenants/",
            headers=barclays_headers
        )
        assert barclays_response.status_code == 200
        barclays_data = barclays_response.json()

        # Verify no overlap in visible tenants
        hsbc_tenant_ids = {item["tenant_id"] for item in hsbc_data["items"]}
        barclays_tenant_ids = {item["tenant_id"] for item in barclays_data["items"]}
        
        assert len(hsbc_tenant_ids.intersection(barclays_tenant_ids)) == 0

    async def test_subsidiary_parent_access_patterns(
        self,
        integration_client: AsyncClient,
        hsbc_parent_tenant: Tenant,
        hsbc_hk_subsidiary: Tenant,
        hsbc_london_subsidiary: Tenant,
        hsbc_headers: dict[str, str],
        hsbc_hk_headers: dict[str, str],
        hsbc_london_headers: dict[str, str],
    ) -> None:
        """Test parent-subsidiary access patterns."""
        # Parent should access all subsidiaries
        hk_response = await integration_client.get(
            f"/api/v1/tenants/{hsbc_hk_subsidiary.tenant_id}",
            headers=hsbc_headers
        )
        assert hk_response.status_code == 200

        london_response = await integration_client.get(
            f"/api/v1/tenants/{hsbc_london_subsidiary.tenant_id}",
            headers=hsbc_headers
        )
        assert london_response.status_code == 200

        # Subsidiary should NOT access sibling subsidiaries
        hk_access_london_response = await integration_client.get(
            f"/api/v1/tenants/{hsbc_london_subsidiary.tenant_id}",
            headers=hsbc_hk_headers
        )
        assert hk_access_london_response.status_code == 404

        london_access_hk_response = await integration_client.get(
            f"/api/v1/tenants/{hsbc_hk_subsidiary.tenant_id}",
            headers=hsbc_london_headers
        )
        assert london_access_hk_response.status_code == 404

        # Subsidiary should NOT access parent
        hk_access_parent_response = await integration_client.get(
            f"/api/v1/tenants/{hsbc_parent_tenant.tenant_id}",
            headers=hsbc_hk_headers
        )
        assert hk_access_parent_response.status_code == 404

    async def test_unauthorized_operations_cross_tenant(
        self,
        integration_client: AsyncClient,
        hsbc_parent_tenant: Tenant,
        barclays_parent_tenant: Tenant,
        hsbc_headers: dict[str, str],
        barclays_headers: dict[str, str],
    ) -> None:
        """Test unauthorized operations across tenant boundaries."""
        # HSBC should not be able to update Barclays tenant
        update_data = {
            "name": "Malicious Update Attempt",
            "metadata": {"hacked": True}
        }
        
        response = await integration_client.put(
            f"/api/v1/tenants/{barclays_parent_tenant.tenant_id}",
            headers=hsbc_headers,
            json=update_data
        )
        assert response.status_code == 404

        # HSBC should not be able to delete Barclays tenant
        response = await integration_client.delete(
            f"/api/v1/tenants/{barclays_parent_tenant.tenant_id}",
            headers=hsbc_headers
        )
        assert response.status_code == 404

        # Verify Barclays tenant is unchanged
        response = await integration_client.get(
            f"/api/v1/tenants/{barclays_parent_tenant.tenant_id}",
            headers=barclays_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Barclays plc"  # Original name
        assert "hacked" not in data["metadata"]


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.tenant
class TestTenantValidationIntegration:
    """Integration tests for tenant data validation and constraints."""

    async def test_duplicate_tenant_name_within_context(
        self,
        integration_client: AsyncClient,
        hsbc_parent_tenant: Tenant,
        hsbc_headers: dict[str, str],
    ) -> None:
        """Test that duplicate tenant names are handled properly."""
        # Try to create tenant with existing name in same context
        duplicate_data = {
            "name": hsbc_parent_tenant.name,  # Same name
            "tenant_type": "parent",
            "metadata": {"duplicate": "test"}
        }

        response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=duplicate_data
        )
        
        # Should fail with conflict error
        assert response.status_code == 409
        error_data = response.json()
        assert "already exists" in error_data["detail"].lower()

    async def test_invalid_parent_tenant_reference(
        self,
        integration_client: AsyncClient,
        hsbc_headers: dict[str, str],
    ) -> None:
        """Test subsidiary creation with invalid parent reference."""
        invalid_parent_id = str(uuid4())
        
        subsidiary_data = {
            "name": "Invalid Subsidiary",
            "tenant_type": "subsidiary",
            "parent_tenant_id": invalid_parent_id,
            "metadata": {"test": "invalid_parent"}
        }

        response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=subsidiary_data
        )
        
        assert response.status_code == 400
        error_data = response.json()
        assert "parent" in error_data["detail"].lower()

    async def test_invalid_tenant_data_validation(
        self,
        integration_client: AsyncClient,
        hsbc_headers: dict[str, str],
    ) -> None:
        """Test various invalid tenant data scenarios."""
        # Empty name
        invalid_data = {
            "name": "",
            "tenant_type": "parent",
            "metadata": {}
        }
        
        response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=invalid_data
        )
        assert response.status_code == 422

        # Invalid tenant type
        invalid_data = {
            "name": "Valid Name",
            "tenant_type": "invalid_type",
            "metadata": {}
        }
        
        response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=invalid_data
        )
        assert response.status_code == 422

        # Missing required fields
        invalid_data = {
            "metadata": {}
        }
        
        response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=invalid_data
        )
        assert response.status_code == 422

    async def test_business_rule_validation(
        self,
        integration_client: AsyncClient,
        hsbc_headers: dict[str, str],
    ) -> None:
        """Test business rule validation in tenant operations."""
        # Parent tenant cannot have parent_tenant_id
        invalid_parent_data = {
            "name": "Invalid Parent",
            "tenant_type": "parent",
            "parent_tenant_id": str(uuid4()),  # Invalid for parent
            "metadata": {}
        }
        
        response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=invalid_parent_data
        )
        assert response.status_code == 422

        # Subsidiary must have parent_tenant_id
        invalid_subsidiary_data = {
            "name": "Invalid Subsidiary",
            "tenant_type": "subsidiary",
            "parent_tenant_id": None,  # Invalid for subsidiary
            "metadata": {}
        }
        
        response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=invalid_subsidiary_data
        )
        assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.slow
class TestTenantPerformanceIntegration:
    """Integration tests for tenant API performance."""

    async def test_bulk_tenant_operations_performance(
        self,
        integration_client: AsyncClient,
        hsbc_headers: dict[str, str],
        performance_threshold_ms: int,
    ) -> None:
        """Test performance of bulk tenant operations."""
        import asyncio
        
        # Create multiple tenants concurrently
        async def create_tenant(index: int) -> tuple[int, float]:
            tenant_data = {
                "name": f"Performance Test Tenant {index}",
                "tenant_type": "parent",
                "metadata": {
                    "index": index,
                    "test": "performance"
                }
            }
            
            start_time = time.time()
            response = await integration_client.post(
                "/api/v1/tenants/",
                headers=hsbc_headers,
                json=tenant_data
            )
            end_time = time.time()
            
            return response.status_code, (end_time - start_time) * 1000
        
        # Create 5 tenants concurrently
        tasks = [create_tenant(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Validate all operations succeeded within threshold
        for status_code, response_time_ms in results:
            assert status_code == 201
            assert response_time_ms <= performance_threshold_ms * 2  # Allow 2x for concurrent load

    async def test_large_metadata_handling(
        self,
        integration_client: AsyncClient,
        hsbc_headers: dict[str, str],
        performance_threshold_ms: int,
    ) -> None:
        """Test handling of tenants with large metadata."""
        # Create tenant with extensive metadata
        large_metadata = {
            "country": "United States",
            "business_units": [f"unit_{i}" for i in range(50)],
            "regulatory_compliance": {
                f"regulation_{i}": {
                    "status": "compliant",
                    "last_check": "2025-08-01",
                    "next_review": "2026-08-01",
                    "details": f"Compliance details for regulation {i}" * 10
                }
                for i in range(20)
            },
            "financial_data": {
                f"metric_{i}": round(i * 1.5, 2) for i in range(100)
            },
            "audit_trail": [
                {
                    "date": f"2025-0{(i % 9) + 1}-01",
                    "auditor": f"Auditor {i}",
                    "findings": f"Audit findings {i}" * 20,
                    "score": i % 5 + 1
                }
                for i in range(25)
            ]
        }

        tenant_data = {
            "name": "Large Metadata Test Tenant",
            "tenant_type": "parent",
            "metadata": large_metadata
        }

        start_time = time.time()
        response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=tenant_data
        )
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000

        assert response.status_code == 201
        assert response_time_ms <= performance_threshold_ms * 3  # Allow 3x for large data

        # Test retrieval performance
        tenant_id = response.json()["tenant_id"]
        
        start_time = time.time()
        get_response = await integration_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=hsbc_headers
        )
        end_time = time.time()
        get_response_time_ms = (end_time - start_time) * 1000

        assert get_response.status_code == 200
        assert get_response_time_ms <= performance_threshold_ms * 2
        
        # Validate metadata was stored correctly
        response_data = get_response.json()
        assert len(response_data["metadata"]["business_units"]) == 50
        assert len(response_data["metadata"]["regulatory_compliance"]) == 20