"""
Integration tests for health check endpoints.

Tests health checks with real database connections and tenant context.
"""

import time
from typing import Any

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.database
class TestHealthIntegration:
    """Integration tests for health check endpoint."""

    async def test_health_check_basic(
        self,
        integration_client: AsyncClient,
        performance_threshold_ms: int,
        timing_validator,
    ) -> None:
        """Test basic health check with performance validation."""
        start_time = time.time()
        
        response = await integration_client.get("/health")
        
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000

        # Validate response
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "database" in data
        assert data["database"]["status"] == "healthy"
        
        # Validate performance
        assert timing_validator(response_time_ms, performance_threshold_ms)

    async def test_health_check_with_database_verification(
        self,
        integration_client: AsyncClient,
        database_health_check,
        integration_db_session,
    ) -> None:
        """Test health check with detailed database verification."""
        # Perform database health check
        health_status = await database_health_check(integration_db_session)
        
        # Verify database is healthy
        assert health_status["database_connected"] is True
        assert health_status["rls_enabled"] is True
        assert health_status["functions_available"] is True
        assert health_status["tenant_table_exists"] is True
        assert health_status["error"] is None
        
        # Test API health endpoint
        response = await integration_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "healthy"
        assert "test_value" in data["database"]
        assert data["database"]["test_value"] == 1

    async def test_health_check_tenant_model_component(
        self,
        integration_client: AsyncClient,
        hsbc_parent_tenant,  # Ensures tenant data exists
        hsbc_hk_subsidiary,
        barclays_parent_tenant,
    ) -> None:
        """Test tenant model health check component."""
        response = await integration_client.get("/health/tenant-model")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["component"] == "tenant_model"
        assert "response_time_ms" in data
        assert isinstance(data["response_time_ms"], (int, float))
        assert data["response_time_ms"] < 1000  # Should be fast
        
        # Validate details
        details = data["details"]
        assert details["tenant_count"] >= 3  # We created 3 tenants
        assert details["rls_enabled"] is True
        assert details["rls_functions_available"] is True
        assert details["crud_operations"] == "working"

    async def test_health_check_performance_under_load(
        self,
        integration_client: AsyncClient,
        performance_threshold_ms: int,
    ) -> None:
        """Test health check performance under concurrent requests."""
        # Make multiple concurrent requests
        import asyncio
        
        async def make_request() -> tuple[int, float]:
            start_time = time.time()
            response = await integration_client.get("/health")
            end_time = time.time()
            return response.status_code, (end_time - start_time) * 1000
        
        # Execute 10 concurrent requests
        tasks = [make_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Validate all requests succeeded within threshold
        for status_code, response_time_ms in results:
            assert status_code == 200
            assert response_time_ms <= performance_threshold_ms * 2  # Allow 2x threshold for concurrent load

    @pytest.mark.slow
    async def test_health_check_extended_monitoring(
        self,
        integration_client: AsyncClient,
    ) -> None:
        """Test health check over extended period to detect issues."""
        # Monitor health over 10 requests with delays
        response_times = []
        
        for i in range(10):
            start_time = time.time()
            response = await integration_client.get("/health")
            end_time = time.time()
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            
            response_time = (end_time - start_time) * 1000
            response_times.append(response_time)
            
            # Small delay between requests
            await asyncio.sleep(0.1)
        
        # Validate response times are consistent (no major spikes)
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        
        # Max should not be more than 3x average (indicating potential issues)
        assert max_response_time <= avg_response_time * 3
        assert avg_response_time <= 100  # Should be very fast for health checks

    async def test_health_check_database_recovery(
        self,
        integration_client: AsyncClient,
        integration_db_session,
    ) -> None:
        """Test health check behavior during database stress."""
        # Test health before any operations
        response = await integration_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        
        # Perform some database operations to simulate load
        from sqlalchemy import text
        
        # Execute some queries to simulate database activity
        for i in range(5):
            await integration_db_session.execute(
                text("SELECT pg_sleep(0.01)")  # 10ms sleep
            )
        
        # Health should still be good after database activity
        response = await integration_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_health_check_response_structure(
        self,
        integration_client: AsyncClient,
    ) -> None:
        """Test that health check response has correct structure."""
        response = await integration_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        
        # Validate top-level structure
        required_fields = {"status", "timestamp", "database"}
        assert set(data.keys()) >= required_fields
        
        # Validate database section structure
        db_data = data["database"]
        db_required_fields = {"status", "test_value", "server_time"}
        assert set(db_data.keys()) >= db_required_fields
        
        # Validate data types
        assert isinstance(data["status"], str)
        assert isinstance(data["timestamp"], str)
        assert isinstance(db_data["status"], str)
        assert isinstance(db_data["test_value"], int)
        assert isinstance(db_data["server_time"], str)
        
        # Validate specific values
        assert data["status"] in ["healthy", "unhealthy"]
        assert db_data["status"] in ["healthy", "unhealthy"]
        assert db_data["test_value"] == 1

    async def test_health_check_tenant_model_detailed_response(
        self,
        integration_client: AsyncClient,
    ) -> None:
        """Test tenant model health check detailed response structure."""
        response = await integration_client.get("/health/tenant-model")
        assert response.status_code == 200
        
        data = response.json()
        
        # Validate top-level structure
        required_fields = {"status", "timestamp", "component", "response_time_ms", "details"}
        assert set(data.keys()) >= required_fields
        
        # Validate details section
        details = data["details"]
        details_required_fields = {
            "tenant_count", 
            "rls_enabled", 
            "rls_functions_available", 
            "crud_operations"
        }
        assert set(details.keys()) >= details_required_fields
        
        # Validate data types and values
        assert isinstance(data["component"], str)
        assert data["component"] == "tenant_model"
        assert isinstance(data["response_time_ms"], (int, float))
        assert data["response_time_ms"] >= 0
        
        assert isinstance(details["tenant_count"], int)
        assert details["tenant_count"] >= 0
        assert isinstance(details["rls_enabled"], bool)
        assert isinstance(details["rls_functions_available"], bool)
        assert isinstance(details["crud_operations"], str)
        assert details["crud_operations"] in ["working", "error"]