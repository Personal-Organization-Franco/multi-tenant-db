"""
Unit tests for custom exceptions module.

Tests custom exception classes, HTTP exception helpers, and proper
error handling patterns for the multi-tenant application.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from src.multi_tenant_db.core.exceptions import (
    MultiTenantException,
    TenantNotFoundException,
    TenantContextMissingException,
    DatabaseConnectionException,
    InvalidConfigurationException,
    tenant_not_found_exception,
    tenant_context_missing_exception,
    database_connection_exception,
    invalid_configuration_exception,
)


class TestMultiTenantException:
    """Test cases for MultiTenantException base class."""

    def test_multi_tenant_exception_creation(self):
        """Test creating MultiTenantException with message."""
        message = "Test error message"
        exception = MultiTenantException(message)
        
        assert str(exception) == message
        assert exception.message == message

    def test_multi_tenant_exception_inheritance(self):
        """Test MultiTenantException inherits from Exception."""
        exception = MultiTenantException("test")
        
        assert isinstance(exception, Exception)
        assert isinstance(exception, MultiTenantException)

    def test_multi_tenant_exception_with_various_messages(self):
        """Test MultiTenantException with various message types."""
        test_messages = [
            "Simple error message",
            "Error with numbers: 123",
            "Error with special chars: @#$%",
            "",  # Empty message
            "Very long error message " * 50,
            "Unicode error: 🏦 银行错误",
        ]
        
        for message in test_messages:
            exception = MultiTenantException(message)
            assert exception.message == message
            assert str(exception) == message

    def test_multi_tenant_exception_attributes(self):
        """Test MultiTenantException has expected attributes."""
        message = "Test message"
        exception = MultiTenantException(message)
        
        # Should have message attribute
        assert hasattr(exception, 'message')
        assert exception.message == message
        
        # Should have standard Exception attributes
        assert hasattr(exception, 'args')
        assert exception.args == (message,)

    def test_multi_tenant_exception_repr(self):
        """Test MultiTenantException string representation."""
        message = "Test error"
        exception = MultiTenantException(message)
        
        # Should be convertible to string
        str_repr = str(exception)
        assert str_repr == message
        
        # Should have proper repr
        repr_str = repr(exception)
        assert "MultiTenantException" in repr_str


class TestTenantNotFoundException:
    """Test cases for TenantNotFoundException."""

    def test_tenant_not_found_exception_creation(self):
        """Test creating TenantNotFoundException."""
        message = "Tenant not found"
        exception = TenantNotFoundException(message)
        
        assert str(exception) == message
        assert exception.message == message

    def test_tenant_not_found_exception_inheritance(self):
        """Test TenantNotFoundException inheritance."""
        exception = TenantNotFoundException("test")
        
        assert isinstance(exception, MultiTenantException)
        assert isinstance(exception, Exception)
        assert isinstance(exception, TenantNotFoundException)

    def test_tenant_not_found_exception_realistic_messages(self):
        """Test TenantNotFoundException with realistic messages."""
        tenant_ids = [
            str(uuid4()),
            "hsbc-holdings",
            "jpmorgan-chase",
            "invalid-tenant-123",
        ]
        
        for tenant_id in tenant_ids:
            message = f"Tenant '{tenant_id}' not found"
            exception = TenantNotFoundException(message)
            
            assert exception.message == message
            assert tenant_id in str(exception)

    def test_tenant_not_found_exception_empty_message(self):
        """Test TenantNotFoundException with empty message."""
        exception = TenantNotFoundException("")
        
        assert exception.message == ""
        assert str(exception) == ""


class TestTenantContextMissingException:
    """Test cases for TenantContextMissingException."""

    def test_tenant_context_missing_exception_creation(self):
        """Test creating TenantContextMissingException."""
        message = "Tenant context is missing"
        exception = TenantContextMissingException(message)
        
        assert str(exception) == message
        assert exception.message == message

    def test_tenant_context_missing_exception_inheritance(self):
        """Test TenantContextMissingException inheritance."""
        exception = TenantContextMissingException("test")
        
        assert isinstance(exception, MultiTenantException)
        assert isinstance(exception, Exception)
        assert isinstance(exception, TenantContextMissingException)

    def test_tenant_context_missing_exception_typical_scenarios(self):
        """Test TenantContextMissingException with typical scenarios."""
        scenarios = [
            "Tenant context not found in request",
            "Tenant header missing from request",
            "Invalid tenant context format",
            "Tenant context expired",
        ]
        
        for message in scenarios:
            exception = TenantContextMissingException(message)
            assert exception.message == message
            assert str(exception) == message


class TestDatabaseConnectionException:
    """Test cases for DatabaseConnectionException."""

    def test_database_connection_exception_creation(self):
        """Test creating DatabaseConnectionException."""
        message = "Database connection failed"
        exception = DatabaseConnectionException(message)
        
        assert str(exception) == message
        assert exception.message == message

    def test_database_connection_exception_inheritance(self):
        """Test DatabaseConnectionException inheritance."""
        exception = DatabaseConnectionException("test")
        
        assert isinstance(exception, MultiTenantException)
        assert isinstance(exception, Exception)
        assert isinstance(exception, DatabaseConnectionException)

    def test_database_connection_exception_database_scenarios(self):
        """Test DatabaseConnectionException with database error scenarios."""
        db_scenarios = [
            "Connection timeout to PostgreSQL",
            "Authentication failed for database user",
            "Database 'tenants' does not exist",
            "Connection pool exhausted",
            "SSL connection required but not configured",
            "PostgreSQL server not responding",
        ]
        
        for message in db_scenarios:
            exception = DatabaseConnectionException(message)
            assert exception.message == message
            assert str(exception) == message


class TestInvalidConfigurationException:
    """Test cases for InvalidConfigurationException."""

    def test_invalid_configuration_exception_creation(self):
        """Test creating InvalidConfigurationException."""
        message = "Configuration is invalid"
        exception = InvalidConfigurationException(message)
        
        assert str(exception) == message
        assert exception.message == message

    def test_invalid_configuration_exception_inheritance(self):
        """Test InvalidConfigurationException inheritance."""
        exception = InvalidConfigurationException("test")
        
        assert isinstance(exception, MultiTenantException)
        assert isinstance(exception, Exception)
        assert isinstance(exception, InvalidConfigurationException)

    def test_invalid_configuration_exception_config_scenarios(self):
        """Test InvalidConfigurationException with configuration error scenarios."""
        config_scenarios = [
            "DATABASE_URL environment variable not set",
            "JWT_SECRET_KEY is required but missing",
            "Invalid log level specified: INVALID",
            "CORS origins format is incorrect",
            "Environment must be one of: development, staging, production",
            "Database URL format is invalid",
        ]
        
        for message in config_scenarios:
            exception = InvalidConfigurationException(message)
            assert exception.message == message
            assert str(exception) == message


class TestHTTPExceptionHelpers:
    """Test cases for HTTP exception helper functions."""

    def test_tenant_not_found_exception_helper(self):
        """Test tenant_not_found_exception helper function."""
        tenant_id = str(uuid4())
        
        http_exception = tenant_not_found_exception(tenant_id)
        
        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_404_NOT_FOUND
        assert tenant_id in http_exception.detail
        assert "not found" in http_exception.detail.lower()

    def test_tenant_not_found_exception_helper_various_tenant_ids(self):
        """Test tenant_not_found_exception helper with various tenant IDs."""
        tenant_ids = [
            str(uuid4()),
            "hsbc-holdings",
            "jpmorgan-chase-london",
            "goldman-sachs-123",
            "special-chars-@#$",
            "unicode-tenant-🏦",
        ]
        
        for tenant_id in tenant_ids:
            http_exception = tenant_not_found_exception(tenant_id)
            
            assert isinstance(http_exception, HTTPException)
            assert http_exception.status_code == status.HTTP_404_NOT_FOUND
            assert tenant_id in http_exception.detail
            assert f"Tenant '{tenant_id}' not found" == http_exception.detail

    def test_tenant_context_missing_exception_helper(self):
        """Test tenant_context_missing_exception helper function."""
        http_exception = tenant_context_missing_exception()
        
        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_400_BAD_REQUEST
        assert "tenant context" in http_exception.detail.lower()
        assert "required" in http_exception.detail.lower()

    def test_database_connection_exception_helper(self):
        """Test database_connection_exception helper function."""
        http_exception = database_connection_exception()
        
        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "database" in http_exception.detail.lower()
        assert "unavailable" in http_exception.detail.lower()

    def test_invalid_configuration_exception_helper(self):
        """Test invalid_configuration_exception helper function."""
        detail = "Missing DATABASE_URL environment variable"
        
        http_exception = invalid_configuration_exception(detail)
        
        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert detail in http_exception.detail
        assert "configuration error" in http_exception.detail.lower()

    def test_invalid_configuration_exception_helper_various_details(self):
        """Test invalid_configuration_exception helper with various details."""
        error_details = [
            "Missing JWT_SECRET_KEY",
            "Invalid log level: INVALID",
            "Database URL format is incorrect",
            "CORS origins configuration error",
            "Environment variable REDIS_URL not found",
        ]
        
        for detail in error_details:
            http_exception = invalid_configuration_exception(detail)
            
            assert isinstance(http_exception, HTTPException)
            assert http_exception.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert f"Configuration error: {detail}" == http_exception.detail

    def test_http_exception_helpers_return_types(self):
        """Test that all HTTP exception helpers return HTTPException instances."""
        helpers = [
            (tenant_not_found_exception, ("test-tenant",)),
            (tenant_context_missing_exception, ()),
            (database_connection_exception, ()),
            (invalid_configuration_exception, ("test detail",)),
        ]
        
        for helper_func, args in helpers:
            result = helper_func(*args)
            assert isinstance(result, HTTPException)
            assert hasattr(result, 'status_code')
            assert hasattr(result, 'detail')
            assert isinstance(result.status_code, int)
            assert isinstance(result.detail, str)

    def test_http_exception_status_codes(self):
        """Test HTTP exception helpers use correct status codes."""
        # Test each helper function returns expected status codes
        tenant_not_found = tenant_not_found_exception("test")
        assert tenant_not_found.status_code == 404
        
        context_missing = tenant_context_missing_exception()
        assert context_missing.status_code == 400
        
        db_connection = database_connection_exception()
        assert db_connection.status_code == 503
        
        invalid_config = invalid_configuration_exception("test")
        assert invalid_config.status_code == 500


class TestExceptionIntegration:
    """Test cases for exception integration and usage patterns."""

    def test_all_custom_exceptions_inherit_from_base(self):
        """Test that all custom exceptions inherit from MultiTenantException."""
        custom_exceptions = [
            TenantNotFoundException,
            TenantContextMissingException,
            DatabaseConnectionException,
            InvalidConfigurationException,
        ]
        
        for exception_class in custom_exceptions:
            exception = exception_class("test message")
            assert isinstance(exception, MultiTenantException)
            assert isinstance(exception, Exception)

    def test_exception_chaining_scenarios(self):
        """Test exception chaining scenarios."""
        # Test that exceptions can be chained
        try:
            try:
                raise DatabaseConnectionException("Connection failed")
            except DatabaseConnectionException as db_error:
                raise TenantNotFoundException("Tenant lookup failed") from db_error
        except TenantNotFoundException as e:
            assert "Tenant lookup failed" in str(e)
            assert isinstance(e.__cause__, DatabaseConnectionException)
            assert "Connection failed" in str(e.__cause__)

    def test_exception_handling_realistic_scenarios(self):
        """Test exception handling in realistic fintech scenarios."""
        tenant_scenarios = [
            {
                "tenant_id": "hsbc-holdings",
                "error_type": TenantNotFoundException,
                "message": "HSBC Holdings tenant not found in system",
            },
            {
                "tenant_id": "jpmorgan-london",
                "error_type": TenantContextMissingException,
                "message": "JP Morgan London context missing from request",
            },
            {
                "tenant_id": "goldman-sachs-ny",
                "error_type": DatabaseConnectionException,
                "message": "Cannot connect to Goldman Sachs NY tenant database",
            },
        ]
        
        for scenario in tenant_scenarios:
            tenant_id = scenario["tenant_id"]
            error_type = scenario["error_type"]
            message = scenario["message"]
            
            # Test custom exception
            exception = error_type(message)
            assert isinstance(exception, MultiTenantException)
            assert str(exception) == message
            
            # Test corresponding HTTP exception
            if error_type == TenantNotFoundException:
                http_exc = tenant_not_found_exception(tenant_id)
                assert http_exc.status_code == 404
                assert tenant_id in http_exc.detail

    def test_exception_message_formatting(self):
        """Test exception message formatting consistency."""
        test_cases = [
            {
                "exception_type": TenantNotFoundException,
                "message": "Tenant 'hsbc-holdings' not found",
                "expected_format": lambda msg: "not found" in msg.lower(),
            },
            {
                "exception_type": TenantContextMissingException,
                "message": "Tenant context is required but not provided",
                "expected_format": lambda msg: "context" in msg.lower(),
            },
            {
                "exception_type": DatabaseConnectionException,
                "message": "Database service is temporarily unavailable",
                "expected_format": lambda msg: "database" in msg.lower(),
            },
            {
                "exception_type": InvalidConfigurationException,
                "message": "Configuration error: missing DATABASE_URL",
                "expected_format": lambda msg: "configuration" in msg.lower(),
            },
        ]
        
        for case in test_cases:
            exception = case["exception_type"](case["message"])
            assert case["expected_format"](str(exception))

    def test_http_helpers_create_fastapi_compatible_exceptions(self):
        """Test that HTTP helpers create FastAPI-compatible exceptions."""
        http_exceptions = [
            tenant_not_found_exception("test-tenant"),
            tenant_context_missing_exception(),
            database_connection_exception(),
            invalid_configuration_exception("test error"),
        ]
        
        for exc in http_exceptions:
            # Should be HTTPException instances
            assert isinstance(exc, HTTPException)
            
            # Should have required attributes for FastAPI
            assert hasattr(exc, 'status_code')
            assert hasattr(exc, 'detail')
            assert hasattr(exc, 'headers')  # HTTPException has headers attribute
            
            # Status code should be valid HTTP status code
            assert 100 <= exc.status_code <= 599
            
            # Detail should be a string
            assert isinstance(exc.detail, str)
            assert len(exc.detail) > 0

    def test_module_imports_and_exports(self):
        """Test that all exceptions and helpers are properly importable."""
        from src.multi_tenant_db.core import exceptions
        
        # Test custom exception classes
        assert hasattr(exceptions, 'MultiTenantException')
        assert hasattr(exceptions, 'TenantNotFoundException')
        assert hasattr(exceptions, 'TenantContextMissingException')
        assert hasattr(exceptions, 'DatabaseConnectionException')
        assert hasattr(exceptions, 'InvalidConfigurationException')
        
        # Test HTTP helper functions
        assert hasattr(exceptions, 'tenant_not_found_exception')
        assert hasattr(exceptions, 'tenant_context_missing_exception')
        assert hasattr(exceptions, 'database_connection_exception')
        assert hasattr(exceptions, 'invalid_configuration_exception')
        
        # Test that they are callable
        assert callable(exceptions.tenant_not_found_exception)
        assert callable(exceptions.tenant_context_missing_exception)
        assert callable(exceptions.database_connection_exception)
        assert callable(exceptions.invalid_configuration_exception)

    def test_exception_documentation_and_usage(self):
        """Test that exceptions have proper documentation."""
        # Check that classes have docstrings or are self-documenting
        exceptions_to_check = [
            MultiTenantException,
            TenantNotFoundException,
            TenantContextMissingException,
            DatabaseConnectionException,
            InvalidConfigurationException,
        ]
        
        for exc_class in exceptions_to_check:
            # Should be properly named
            assert exc_class.__name__.endswith('Exception')
            
            # Should be instantiable with a message
            instance = exc_class("test message")
            assert str(instance) == "test message"

    def test_fintech_error_scenarios_comprehensive(self):
        """Test comprehensive fintech error scenarios."""
        # Simulate realistic banking error scenarios
        banking_scenarios = [
            {
                "scenario": "Tenant isolation breach attempt",
                "tenant_id": "competitor-bank",
                "exception": TenantNotFoundException,
                "message": "Access denied: tenant not found or access not authorized",
            },
            {
                "scenario": "Regulatory compliance check failure",
                "tenant_id": "offshore-bank",
                "exception": TenantContextMissingException,
                "message": "Regulatory context missing: KYC/AML validation required",
            },
            {
                "scenario": "High availability database failover",
                "tenant_id": "critical-trading-system",
                "exception": DatabaseConnectionException,
                "message": "Primary database unavailable, failover in progress",
            },
            {
                "scenario": "Environment configuration mismatch",
                "tenant_id": "production-bank",
                "exception": InvalidConfigurationException,
                "message": "Production environment misconfigured: encryption keys invalid",
            },
        ]
        
        for scenario in banking_scenarios:
            tenant_id = scenario["tenant_id"]
            exception_type = scenario["exception"]
            message = scenario["message"]
            
            # Test custom exception creation
            custom_exception = exception_type(message)
            assert isinstance(custom_exception, MultiTenantException)
            assert str(custom_exception) == message
            
            # Test that tenant_id can be used in HTTP helpers where applicable
            if exception_type == TenantNotFoundException:
                http_exc = tenant_not_found_exception(tenant_id)
                assert tenant_id in http_exc.detail
                assert http_exc.status_code == 404