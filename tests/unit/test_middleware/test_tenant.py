"""
Comprehensive unit tests for tenant middleware.

Tests tenant context extraction, middleware functionality,
request processing, and error handling.
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.multi_tenant_db.api.middleware.tenant import (
    DatabaseTenantMiddleware,
    TenantContextMiddleware,
    get_current_tenant_id,
)


class TestTenantContextMiddleware:
    """Test TenantContextMiddleware functionality."""

    @pytest.fixture
    def middleware(self, mock_settings):
        """Create TenantContextMiddleware instance for testing."""
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            return TenantContextMiddleware(Mock())

    @pytest.fixture
    def mock_call_next(self):
        """Create mock call_next function."""
        mock_response = Response("OK", status_code=200)
        return AsyncMock(return_value=mock_response)

    @pytest.mark.asyncio
    async def test_dispatch_with_header_tenant_id(self, middleware, mock_call_next):
        """Test middleware dispatch with tenant ID in header."""
        # Create mock request with tenant header
        request = Mock(spec=Request)
        request.headers = {"X-Tenant-ID": str(uuid4())}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/tenants/123"
        request.method = "GET"
        
        # Execute middleware
        response = await middleware.dispatch(request, mock_call_next)
        
        # Verify tenant ID was set in request state
        assert hasattr(request.state, "tenant_id")
        assert request.state.tenant_id == request.headers["X-Tenant-ID"]
        
        # Verify call_next was called
        mock_call_next.assert_called_once_with(request)
        
        # Verify response
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_with_cookie_tenant_id(self, middleware, mock_call_next):
        """Test middleware dispatch with tenant ID in cookie."""
        tenant_id = str(uuid4())
        
        # Create mock request with tenant cookie (no header)
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {"tenant_id": tenant_id}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/tenants/123"
        request.method = "GET"
        
        # Execute middleware
        response = await middleware.dispatch(request, mock_call_next)
        
        # Verify tenant ID from cookie was used
        assert request.state.tenant_id == tenant_id
        mock_call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_with_default_tenant_id(self, mock_settings, mock_call_next):
        """Test middleware dispatch uses default tenant ID when none provided."""
        # Configure settings to not require tenant header
        mock_settings.require_tenant_header = False
        mock_settings.default_tenant_id = "default-tenant-123"
        
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            middleware = TenantContextMiddleware(Mock())
        
        # Create mock request without tenant info
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/tenants/123"
        request.method = "GET"
        
        # Execute middleware
        response = await middleware.dispatch(request, mock_call_next)
        
        # Verify default tenant ID was used
        assert request.state.tenant_id == mock_settings.default_tenant_id
        mock_call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_health_endpoint_skip(self, mock_settings, mock_call_next):
        """Test middleware skips tenant requirement for health endpoints."""
        # Configure settings to require tenant header
        mock_settings.require_tenant_header = True
        mock_settings.default_tenant_id = "default-tenant"
        
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            middleware = TenantContextMiddleware(Mock())
        
        # Create mock request to health endpoint without tenant info
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/health"
        request.method = "GET"
        
        # Execute middleware - should not raise exception
        response = await middleware.dispatch(request, mock_call_next)
        
        # Verify default tenant was used and call succeeded
        assert request.state.tenant_id == mock_settings.default_tenant_id
        mock_call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_tenant_admin_operations_skip(self, mock_settings, mock_call_next):
        """Test middleware skips tenant requirement for tenant admin operations."""
        # Configure settings to require tenant header
        mock_settings.require_tenant_header = True
        mock_settings.default_tenant_id = "default-tenant"
        
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            middleware = TenantContextMiddleware(Mock())
        
        # Test POST to create tenant
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/tenants"
        request.method = "POST"
        
        # Execute middleware - should not raise exception
        response = await middleware.dispatch(request, mock_call_next)
        
        assert request.state.tenant_id == mock_settings.default_tenant_id
        mock_call_next.assert_called_once_with(request)
        
        # Test GET to list tenants
        mock_call_next.reset_mock()
        request.method = "GET"
        
        response = await middleware.dispatch(request, mock_call_next)
        
        assert request.state.tenant_id == mock_settings.default_tenant_id
        mock_call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_missing_tenant_required(self, mock_settings, mock_call_next):
        """Test middleware raises error when tenant required but missing."""
        # Configure settings to require tenant header
        mock_settings.require_tenant_header = True
        mock_settings.tenant_header_name = "X-Tenant-ID"
        mock_settings.tenant_cookie_name = "tenant_id"
        
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            middleware = TenantContextMiddleware(Mock())
        
        # Create mock request without tenant info to protected endpoint
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/tenants/123/update"
        request.method = "PUT"
        
        # Execute middleware - should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, mock_call_next)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Missing tenant identifier" in str(exc_info.value.detail)
        assert mock_settings.tenant_header_name in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_dispatch_http_exception_passthrough(self, middleware):
        """Test middleware passes through HTTPExceptions without logging."""
        # Create mock call_next that raises HTTPException
        http_exception = HTTPException(status_code=404, detail="Not found")
        mock_call_next = AsyncMock(side_effect=http_exception)
        
        # Create mock request
        request = Mock(spec=Request)
        request.headers = {"X-Tenant-ID": str(uuid4())}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/test"
        request.method = "GET"
        
        # Execute middleware - should re-raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, mock_call_next)
        
        assert exc_info.value == http_exception

    @pytest.mark.asyncio
    async def test_dispatch_unexpected_exception_logging(self, middleware):
        """Test middleware logs unexpected exceptions."""
        # Create mock call_next that raises unexpected exception
        unexpected_error = RuntimeError("Unexpected error")
        mock_call_next = AsyncMock(side_effect=unexpected_error)
        
        # Create mock request
        request = Mock(spec=Request)
        request.headers = {"X-Tenant-ID": str(uuid4())}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/test"
        request.method = "GET"
        
        # Execute middleware - should re-raise exception after logging
        with patch("src.multi_tenant_db.api.middleware.tenant.logger") as mock_logger:
            with pytest.raises(RuntimeError) as exc_info:
                await middleware.dispatch(request, mock_call_next)
            
            assert exc_info.value == unexpected_error
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_debug_logging(self, mock_settings, mock_call_next):
        """Test middleware debug logging when debug is enabled."""
        # Enable debug logging
        mock_settings.debug = True
        
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            middleware = TenantContextMiddleware(Mock())
        
        tenant_id = str(uuid4())
        
        # Create mock request
        request = Mock(spec=Request)
        request.headers = {"X-Tenant-ID": tenant_id}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/test"
        request.method = "GET"
        
        # Execute middleware with debug logging
        with patch("src.multi_tenant_db.api.middleware.tenant.logger") as mock_logger:
            await middleware.dispatch(request, mock_call_next)
            
            # Verify debug logging occurred
            mock_logger.debug.assert_called_once()
            debug_call = mock_logger.debug.call_args[0][0]
            assert tenant_id in debug_call
            assert request.url.path in debug_call


class TestTenantContextExtractionMethods:
    """Test private methods for tenant context extraction."""

    @pytest.fixture
    def middleware(self, mock_settings):
        """Create TenantContextMiddleware instance for testing."""
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            return TenantContextMiddleware(Mock())

    @pytest.mark.asyncio
    async def test_extract_tenant_id_priority_order(self, middleware):
        """Test tenant ID extraction priority (header > cookie > JWT)."""
        header_tenant = str(uuid4())
        cookie_tenant = str(uuid4())
        
        # Create request with both header and cookie
        request = Mock(spec=Request)
        request.headers = {"X-Tenant-ID": header_tenant}
        request.cookies = {"tenant_id": cookie_tenant}
        request.url = Mock()
        request.url.path = "/api/v1/test"
        request.method = "GET"
        
        # Execute extraction
        result = await middleware._extract_tenant_id(request)
        
        # Header should take priority
        assert result == header_tenant

    @pytest.mark.asyncio
    async def test_extract_tenant_id_fallback_to_cookie(self, middleware):
        """Test tenant ID extraction falls back to cookie when header missing."""
        cookie_tenant = str(uuid4())
        
        # Create request with only cookie
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {"tenant_id": cookie_tenant}
        request.url = Mock()
        request.url.path = "/api/v1/test"
        request.method = "GET"
        
        # Execute extraction
        result = await middleware._extract_tenant_id(request)
        
        # Cookie should be used
        assert result == cookie_tenant

    @pytest.mark.asyncio
    async def test_extract_from_jwt_placeholder(self, middleware):
        """Test JWT extraction method (placeholder implementation)."""
        request = Mock(spec=Request)
        
        # Execute JWT extraction
        result = await middleware._extract_from_jwt(request)
        
        # Should return None (placeholder implementation)
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_tenant_id_docs_endpoints(self, mock_settings, mock_call_next):
        """Test tenant ID extraction skips docs endpoints."""
        # Configure to require tenant
        mock_settings.require_tenant_header = True
        mock_settings.default_tenant_id = "default-tenant"
        
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            middleware = TenantContextMiddleware(Mock())
        
        docs_endpoints = ["/docs", "/redoc", "/openapi.json"]
        
        for endpoint in docs_endpoints:
            request = Mock(spec=Request)
            request.headers = {}
            request.cookies = {}
            request.state = Mock()
            request.url = Mock()
            request.url.path = endpoint
            request.method = "GET"
            
            # Should not raise exception
            response = await middleware.dispatch(request, mock_call_next)
            assert request.state.tenant_id == mock_settings.default_tenant_id

    @pytest.mark.asyncio
    async def test_extract_tenant_id_debug_logging_scenarios(self, mock_settings, mock_call_next):
        """Test debug logging in various tenant extraction scenarios."""
        mock_settings.debug = True
        mock_settings.require_tenant_header = True
        
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            middleware = TenantContextMiddleware(Mock())
        
        # Test debug logging when no tenant found
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/protected"
        request.method = "GET"
        
        with patch("src.multi_tenant_db.api.middleware.tenant.logger") as mock_logger:
            with pytest.raises(HTTPException):
                await middleware.dispatch(request, mock_call_next)
            
            # Should log debug info about missing tenant
            assert mock_logger.debug.call_count >= 1


class TestDatabaseTenantMiddleware:
    """Test DatabaseTenantMiddleware functionality."""

    @pytest.fixture
    def middleware(self):
        """Create DatabaseTenantMiddleware instance for testing."""
        return DatabaseTenantMiddleware(Mock())

    @pytest.mark.asyncio
    async def test_dispatch_with_tenant_id(self, middleware):
        """Test middleware sets database tenant ID when tenant context exists."""
        tenant_id = str(uuid4())
        
        # Create mock request with tenant state
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.tenant_id = tenant_id
        
        # Create mock call_next
        mock_response = Response("OK", status_code=200)
        mock_call_next = AsyncMock(return_value=mock_response)
        
        # Execute middleware
        response = await middleware.dispatch(request, mock_call_next)
        
        # Verify database tenant ID was set
        assert hasattr(request.state, "db_tenant_id")
        assert request.state.db_tenant_id == tenant_id
        
        # Verify call_next was called
        mock_call_next.assert_called_once_with(request)
        assert response == mock_response

    @pytest.mark.asyncio
    async def test_dispatch_without_tenant_id(self, middleware):
        """Test middleware handles missing tenant context gracefully."""
        # Create mock request without tenant state
        request = Mock(spec=Request)
        request.state = Mock()
        # No tenant_id attribute
        
        # Create mock call_next
        mock_response = Response("OK", status_code=200)
        mock_call_next = AsyncMock(return_value=mock_response)
        
        # Execute middleware
        response = await middleware.dispatch(request, mock_call_next)
        
        # Verify no database tenant ID was set
        assert not hasattr(request.state, "db_tenant_id")
        
        # Verify call_next was still called
        mock_call_next.assert_called_once_with(request)
        assert response == mock_response

    @pytest.mark.asyncio
    async def test_dispatch_getattr_returns_none(self, middleware):
        """Test middleware handles getattr returning None."""
        # Create mock request where getattr returns None
        request = Mock(spec=Request)
        request.state = Mock()
        
        # Mock getattr to return None
        with patch("src.multi_tenant_db.api.middleware.tenant.getattr", return_value=None):
            # Create mock call_next
            mock_response = Response("OK", status_code=200)
            mock_call_next = AsyncMock(return_value=mock_response)
            
            # Execute middleware
            response = await middleware.dispatch(request, mock_call_next)
            
            # Verify no database tenant ID was set
            assert not hasattr(request.state, "db_tenant_id")
            mock_call_next.assert_called_once_with(request)


class TestGetCurrentTenantId:
    """Test get_current_tenant_id utility function."""

    def test_get_current_tenant_id_success(self):
        """Test successful tenant ID retrieval from request state."""
        tenant_id = str(uuid4())
        
        # Create mock request with tenant ID in state
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.tenant_id = tenant_id
        
        # Execute function
        result = get_current_tenant_id(request)
        
        # Verify result
        assert result == tenant_id

    def test_get_current_tenant_id_missing_attribute(self):
        """Test tenant ID retrieval when attribute is missing."""
        # Create mock request without tenant_id attribute
        request = Mock(spec=Request)
        request.state = Mock()
        # No tenant_id attribute
        
        # Execute function - should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_current_tenant_id(request)
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Tenant context not set" in str(exc_info.value.detail)
        assert "TenantContextMiddleware" in str(exc_info.value.detail)

    def test_get_current_tenant_id_none_value(self):
        """Test tenant ID retrieval when value is None."""
        # Create mock request with None tenant_id
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.tenant_id = None
        
        # Execute function - should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_current_tenant_id(request)
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_current_tenant_id_empty_string(self):
        """Test tenant ID retrieval when value is empty string."""
        # Create mock request with empty string tenant_id
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.tenant_id = ""
        
        # Execute function - should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_current_tenant_id(request)
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_current_tenant_id_no_state(self):
        """Test tenant ID retrieval when request has no state."""
        # Create mock request without state
        request = Mock(spec=Request)
        # No state attribute
        
        # Execute function - should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_current_tenant_id(request)
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestMiddlewareIntegration:
    """Test middleware integration scenarios."""

    @pytest.mark.asyncio
    async def test_middleware_chain_tenant_to_database(self, mock_settings):
        """Test complete middleware chain from tenant extraction to database context."""
        # Configure settings
        mock_settings.require_tenant_header = False
        mock_settings.default_tenant_id = "test-tenant"
        
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            # Create both middlewares
            tenant_middleware = TenantContextMiddleware(Mock())
            db_middleware = DatabaseTenantMiddleware(Mock())
        
        tenant_id = str(uuid4())
        
        # Create mock request
        request = Mock(spec=Request)
        request.headers = {"X-Tenant-ID": tenant_id}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/test"
        request.method = "GET"
        
        # Create final response
        final_response = Response("Final", status_code=200)
        
        # Create call_next chain
        async def final_handler(req):
            return final_response
        
        async def db_handler(req):
            return await db_middleware.dispatch(req, final_handler)
        
        # Execute tenant middleware first
        response = await tenant_middleware.dispatch(request, db_handler)
        
        # Verify tenant context was set
        assert request.state.tenant_id == tenant_id
        
        # Verify database tenant context was set
        assert request.state.db_tenant_id == tenant_id
        
        # Verify final response
        assert response == final_response

    @pytest.mark.asyncio
    async def test_middleware_error_handling_in_chain(self, mock_settings):
        """Test error handling when middleware chain has errors."""
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            tenant_middleware = TenantContextMiddleware(Mock())
            db_middleware = DatabaseTenantMiddleware(Mock())
        
        tenant_id = str(uuid4())
        
        # Create mock request
        request = Mock(spec=Request)
        request.headers = {"X-Tenant-ID": tenant_id}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/test"
        request.method = "GET"
        
        # Create error in downstream handler
        async def error_handler(req):
            raise HTTPException(status_code=500, detail="Downstream error")
        
        async def db_handler(req):
            return await db_middleware.dispatch(req, error_handler)
        
        # Execute middleware chain - should propagate error
        with pytest.raises(HTTPException) as exc_info:
            await tenant_middleware.dispatch(request, db_handler)
        
        assert exc_info.value.status_code == 500
        assert "Downstream error" in str(exc_info.value.detail)
        
        # Verify tenant context was still set despite error
        assert request.state.tenant_id == tenant_id


class TestMiddlewareConfigurationScenarios:
    """Test different middleware configuration scenarios."""

    @pytest.mark.asyncio
    async def test_different_header_cookie_names(self):
        """Test middleware with custom header and cookie names."""
        # Create custom settings
        mock_settings = Mock()
        mock_settings.tenant_header_name = "X-Custom-Tenant"
        mock_settings.tenant_cookie_name = "custom_tenant"
        mock_settings.require_tenant_header = False
        mock_settings.default_tenant_id = "default"
        mock_settings.debug = False
        
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            middleware = TenantContextMiddleware(Mock())
        
        tenant_id = str(uuid4())
        
        # Test custom header
        request = Mock(spec=Request)
        request.headers = {"X-Custom-Tenant": tenant_id}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/test"
        request.method = "GET"
        
        mock_response = Response("OK")
        mock_call_next = AsyncMock(return_value=mock_response)
        
        await middleware.dispatch(request, mock_call_next)
        assert request.state.tenant_id == tenant_id
        
        # Test custom cookie
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {"custom_tenant": tenant_id}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/test"
        request.method = "GET"
        
        await middleware.dispatch(request, mock_call_next)
        assert request.state.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_strict_tenant_requirement_mode(self):
        """Test middleware in strict tenant requirement mode."""
        # Configure strict mode
        mock_settings = Mock()
        mock_settings.require_tenant_header = True
        mock_settings.tenant_header_name = "X-Tenant-ID"
        mock_settings.tenant_cookie_name = "tenant_id"
        mock_settings.debug = False
        
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            middleware = TenantContextMiddleware(Mock())
        
        # Test request without tenant to protected endpoint
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/protected-resource"
        request.method = "GET"
        
        mock_call_next = AsyncMock()
        
        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, mock_call_next)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        mock_call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_permissive_tenant_mode(self):
        """Test middleware in permissive mode (no tenant required)."""
        # Configure permissive mode
        mock_settings = Mock()
        mock_settings.require_tenant_header = False
        mock_settings.default_tenant_id = "system-default"
        mock_settings.debug = False
        
        with patch("src.multi_tenant_db.api.middleware.tenant.get_settings", return_value=mock_settings):
            middleware = TenantContextMiddleware(Mock())
        
        # Test request without tenant
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {}
        request.state = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/any-resource"
        request.method = "GET"
        
        mock_response = Response("OK")
        mock_call_next = AsyncMock(return_value=mock_response)
        
        # Should succeed with default tenant
        response = await middleware.dispatch(request, mock_call_next)
        
        assert request.state.tenant_id == mock_settings.default_tenant_id
        assert response == mock_response
        mock_call_next.assert_called_once()