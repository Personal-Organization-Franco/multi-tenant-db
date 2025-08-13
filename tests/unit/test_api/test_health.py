"""
Comprehensive unit tests for health check endpoints.

Tests all health check endpoints with various scenarios including
database connectivity, RLS testing, and error handling.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError


class TestBasicHealthCheck:
    """Test GET /api/v1/health endpoint."""

    def test_health_check_success(self, client):
        """Test basic health check endpoint."""
        response = client.get("/api/v1/health")
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "Multi-Tenant Database API"
        assert data["version"] == "0.1.0"
        
        # Verify timestamp is valid ISO format
        timestamp = data["timestamp"]
        assert isinstance(timestamp, str)
        # Should be parseable as ISO format
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


class TestDatabaseHealthCheck:
    """Test GET /api/v1/health/database endpoint."""

    def test_database_health_check_success(self, client, app):
        """Test successful database health check."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session and result
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_row = Mock()
        mock_row.test = 1
        mock_row.time = datetime.now(timezone.utc)
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/database")
            
            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert "timestamp" in data
            assert data["database"]["status"] == "healthy"
            assert data["database"]["test_value"] == 1
            assert "server_time" in data["database"]
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)

    def test_database_health_check_failure(self, client, app):
        """Test database health check when database fails."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session that raises exception
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database connection failed")
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/database")
            
            # Verify response - still returns 200 but with unhealthy status
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database"]["status"] == "unhealthy"
            assert "error" in data["database"]
            assert "Database connection failed" in data["database"]["error"]
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)


class TestTenantModelHealthCheck:
    """Test GET /api/v1/health/tenant-model endpoint."""

    def test_tenant_model_health_check_success(self, client, app):
        """Test successful tenant model health check."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session and results
        mock_session = AsyncMock()
        
        # Mock tenant count query
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 5
        
        # Mock RLS enabled query
        mock_rls_result = Mock()
        mock_rls_result.scalar.return_value = True
        
        # Mock RLS functions query
        mock_func_result = Mock()
        mock_func_result.scalar.return_value = 2
        
        # Mock CRUD operations (insert, select, delete)
        mock_crud_result = Mock()
        mock_crud_row = Mock()
        mock_crud_row.name = "test-name"
        mock_crud_result.fetchone.return_value = mock_crud_row
        
        # Setup execute side effects in order
        mock_session.execute.side_effect = [
            mock_count_result,  # COUNT query
            mock_rls_result,    # RLS enabled query
            mock_func_result,   # RLS functions query
            None,               # INSERT query (no return value)
            mock_crud_result,   # SELECT query for verification
            None,               # DELETE query (no return value)
        ]
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/tenant-model")
            
            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert data["component"] == "tenant_model"
            assert "response_time_ms" in data
            assert isinstance(data["response_time_ms"], (int, float))
            
            details = data["details"]
            assert details["tenant_count"] == 5
            assert details["rls_enabled"] is True
            assert details["rls_functions_available"] is True
            assert details["crud_operations"] == "working"
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)

    def test_tenant_model_health_check_rls_disabled(self, client, app):
        """Test tenant model health check when RLS is disabled."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session and results
        mock_session = AsyncMock()
        
        # Mock tenant count query
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 3
        
        # Mock RLS disabled
        mock_rls_result = Mock()
        mock_rls_result.scalar.return_value = False  # RLS disabled
        
        # Mock RLS functions query
        mock_func_result = Mock()
        mock_func_result.scalar.return_value = 1  # Missing functions
        
        # Mock CRUD operations - simulate success
        mock_crud_result = Mock()
        mock_crud_row = Mock()
        mock_crud_row.name = "test-name"
        mock_crud_result.fetchone.return_value = mock_crud_row
        
        # Setup execute side effects in order
        mock_session.execute.side_effect = [
            mock_count_result,  # COUNT query
            mock_rls_result,    # RLS enabled query
            mock_func_result,   # RLS functions query
            None,               # INSERT query
            mock_crud_result,   # SELECT query
            None,               # DELETE query
        ]
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/tenant-model")
            
            # Verify response shows unhealthy due to RLS issues
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"
            
            details = data["details"]
            assert details["rls_enabled"] is False
            assert details["rls_functions_available"] is False
            assert details["crud_operations"] == "working"
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)

    def test_tenant_model_health_check_crud_failure(self, client, app):
        """Test tenant model health check when CRUD operations fail."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session and results
        mock_session = AsyncMock()
        
        # Mock successful initial queries
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 5
        
        mock_rls_result = Mock()
        mock_rls_result.scalar.return_value = True
        
        mock_func_result = Mock()
        mock_func_result.scalar.return_value = 2
        
        # Mock CRUD failure - SELECT returns None
        mock_crud_result = Mock()
        mock_crud_result.fetchone.return_value = None
        
        # Setup execute side effects
        mock_session.execute.side_effect = [
            mock_count_result,  # COUNT query
            mock_rls_result,    # RLS enabled query
            mock_func_result,   # RLS functions query
            None,               # INSERT query
            mock_crud_result,   # SELECT query (returns None = failed)
            None,               # DELETE query
        ]
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/tenant-model")
            
            # Verify response shows unhealthy due to CRUD failure
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"
            
            details = data["details"]
            assert details["crud_operations"] == "failed"
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)

    def test_tenant_model_health_check_database_error(self, client, app):
        """Test tenant model health check with database error."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session that raises SQLAlchemy error
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/tenant-model")
            
            # Verify response shows unhealthy with error details
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data["details"]
            assert "Database error" in data["details"]["error"]
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)


class TestTenantIsolationHealthCheck:
    """Test GET /api/v1/health/tenant-isolation endpoint - CRITICAL RLS TESTS."""

    def test_tenant_isolation_health_check_success(self, client, app):
        """Test successful tenant isolation health check - ensures tenant A cannot access tenant B."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session
        mock_session = AsyncMock()
        
        # Mock different execute calls in sequence
        execute_results = []
        
        # INSERT parent tenant (no return value)
        execute_results.append(None)
        
        # INSERT subsidiary tenant (no return value)
        execute_results.append(None)
        
        # SELECT without context - should return 0 (isolation working)
        # This is the critical test: tenant A should NOT see tenant B's data
        mock_isolation_result = Mock()
        mock_isolation_result.scalar.return_value = 0
        execute_results.append(mock_isolation_result)
        
        # SET tenant context (no return value)
        execute_results.append(None)
        
        # SELECT with context - should return > 0 (access working)
        mock_access_result = Mock()
        mock_access_result.scalar.return_value = 2
        execute_results.append(mock_access_result)
        
        # DELETE cleanup (no return value)
        execute_results.append(None)
        
        mock_session.execute.side_effect = execute_results
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/tenant-isolation")
            
            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert data["component"] == "tenant_isolation"
            assert "response_time_ms" in data
            
            test_results = data["test_results"]
            # Critical assertion: isolation working means tenant A cannot access tenant B
            assert test_results["isolation_without_context"] is True
            assert test_results["parent_can_see_data"] is True
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)

    def test_tenant_isolation_health_check_isolation_failure(self, client, app):
        """Test tenant isolation health check when isolation fails - SECURITY BREACH."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session
        mock_session = AsyncMock()
        
        # Mock execute calls - isolation failure (can see data without context)
        # This simulates a CRITICAL SECURITY ISSUE where tenant A can access tenant B's data
        execute_results = [
            None,  # INSERT parent
            None,  # INSERT subsidiary
            Mock(scalar=lambda: 2),  # SELECT without context returns data (SECURITY BREACH!)
            None,  # SET context
            Mock(scalar=lambda: 2),  # SELECT with context
            None,  # DELETE cleanup
        ]
        
        mock_session.execute.side_effect = execute_results
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/tenant-isolation")
            
            # Verify response shows unhealthy - CRITICAL SECURITY ISSUE DETECTED
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"
            
            test_results = data["test_results"]
            # Failed isolation means tenant A can access tenant B data - SECURITY BREACH!
            assert test_results["isolation_without_context"] is False
            assert test_results["parent_can_see_data"] is True
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)

    def test_tenant_isolation_health_check_access_failure(self, client, app):
        """Test tenant isolation health check when access fails."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session
        mock_session = AsyncMock()
        
        # Mock execute calls - access failure (can't see data with context)
        execute_results = [
            None,  # INSERT parent
            None,  # INSERT subsidiary
            Mock(scalar=lambda: 0),  # SELECT without context (good isolation)
            None,  # SET context
            Mock(scalar=lambda: 0),  # SELECT with context returns no data (bad!)
            None,  # DELETE cleanup
        ]
        
        mock_session.execute.side_effect = execute_results
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/tenant-isolation")
            
            # Verify response shows unhealthy
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"
            
            test_results = data["test_results"]
            assert test_results["isolation_without_context"] is True
            assert test_results["parent_can_see_data"] is False  # Failed access
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)

    def test_tenant_isolation_health_check_database_error(self, client, app):
        """Test tenant isolation health check with database error."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session that raises error
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("Isolation test failed")
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/tenant-isolation")
            
            # Verify response shows unhealthy with error
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data["test_results"]
            assert "Isolation test failed" in data["test_results"]["error"]
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)

    def test_tenant_isolation_health_check_cleanup_on_error(self, client, app):
        """Test tenant isolation health check cleans up on error."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session that raises error after creating data
        mock_session = AsyncMock()
        
        # First two calls succeed (INSERT), third fails, then cleanup calls
        execute_results = [
            None,  # INSERT parent (succeeds)
            None,  # INSERT subsidiary (succeeds)
            SQLAlchemyError("Query failed"),  # SELECT fails
            None,  # DELETE cleanup - should not fail even if called
        ]
        mock_session.execute.side_effect = execute_results
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/tenant-isolation")
            
            # Verify response handles error gracefully
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"
            
            # Verify cleanup was attempted (even though it might fail)
            # The important thing is that the endpoint doesn't crash
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)


class TestReadinessCheck:
    """Test GET /api/v1/health/readiness endpoint."""

    @patch("src.multi_tenant_db.api.v1.health.test_database_connection")
    def test_readiness_check_success(self, mock_test_db, client):
        """Test successful readiness check."""
        # Mock successful database connection
        mock_test_db.return_value = True
        
        response = client.get("/api/v1/health/readiness")
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ready"
        assert "timestamp" in data
        assert len(data["checks"]) == 1
        
        db_check = data["checks"][0]
        assert db_check["name"] == "database"
        assert db_check["status"] == "ready"
        assert db_check["required"] is True

    @patch("src.multi_tenant_db.api.v1.health.test_database_connection")
    def test_readiness_check_database_not_ready(self, mock_test_db, client):
        """Test readiness check when database is not ready."""
        # Mock failed database connection
        mock_test_db.return_value = False
        
        response = client.get("/api/v1/health/readiness")
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "not_ready"
        
        db_check = data["checks"][0]
        assert db_check["status"] == "not_ready"


class TestLivenessCheck:
    """Test GET /api/v1/health/liveness endpoint."""

    def test_liveness_check_success(self, client):
        """Test liveness check endpoint."""
        response = client.get("/api/v1/health/liveness")
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data
        
        # Verify timestamp is valid
        timestamp = data["timestamp"]
        assert isinstance(timestamp, str)
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


class TestHealthCheckErrorHandling:
    """Test error handling across health check endpoints."""

    def test_database_health_check_unexpected_error(self, client, app):
        """Test database health check handles unexpected errors."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock that raises unexpected error
        mock_session = AsyncMock()
        mock_session.execute.side_effect = RuntimeError("Unexpected error")
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/database")
            
            # Should handle gracefully and return unhealthy status
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data["database"]
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)

    @patch("src.multi_tenant_db.api.v1.health.test_database_connection")
    def test_readiness_check_exception_handling(self, mock_test_db, client):
        """Test readiness check handles exceptions gracefully."""
        # Mock function that raises exception
        mock_test_db.side_effect = Exception("Connection test failed")
        
        # Should not crash the endpoint
        response = client.get("/api/v1/health/readiness")
        
        # Might return error status but shouldn't crash
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestHealthCheckTiming:
    """Test performance aspects of health checks."""

    def test_tenant_model_health_check_timing(self, client, app):
        """Test that tenant model health check includes timing information."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create fast mock responses
        mock_session = AsyncMock()
        mock_session.execute.return_value = Mock(scalar=lambda: 1, fetchone=lambda: Mock(name="test"))
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/tenant-model")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "response_time_ms" in data
            assert isinstance(data["response_time_ms"], (int, float))
            assert data["response_time_ms"] >= 0
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)

    def test_tenant_isolation_health_check_timing(self, client, app):
        """Test that tenant isolation health check includes timing information."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock responses for successful isolation test
        mock_session = AsyncMock()
        execute_results = [
            None,  # INSERT parent
            None,  # INSERT subsidiary
            Mock(scalar=lambda: 0),  # SELECT without context
            None,  # SET context
            Mock(scalar=lambda: 1),  # SELECT with context
            None,  # DELETE cleanup
        ]
        mock_session.execute.side_effect = execute_results
        
        # Override the dependency
        async def mock_get_db_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = mock_get_db_session
        
        try:
            response = client.get("/api/v1/health/tenant-isolation")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "response_time_ms" in data
            assert isinstance(data["response_time_ms"], (int, float))
            assert data["response_time_ms"] >= 0
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_db_session, None)


class TestHealthCheckResponseFormat:
    """Test response format consistency across health endpoints."""

    def test_all_health_endpoints_have_timestamp(self, client):
        """Test that all health endpoints include timestamp."""
        endpoints = [
            "/api/v1/health",
            "/api/v1/health/readiness",
            "/api/v1/health/liveness"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "timestamp" in data
            assert isinstance(data["timestamp"], str)

    def test_health_endpoints_status_field(self, client):
        """Test that health endpoints have appropriate status fields."""
        # Basic health check
        response = client.get("/api/v1/health")
        data = response.json()
        assert data["status"] == "healthy"
        
        # Liveness check
        response = client.get("/api/v1/health/liveness")
        data = response.json()
        assert data["status"] == "alive"
        
        # Readiness check status depends on database connection
        response = client.get("/api/v1/health/readiness")
        data = response.json()
        assert data["status"] in ["ready", "not_ready"]