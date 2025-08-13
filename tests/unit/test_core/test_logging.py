"""
Unit tests for logging configuration module.

Tests logging configuration, JSON formatter, tenant context handling,
and structured logging for the multi-tenant application.
"""

import json
import logging
import sys
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

import pytest

from src.multi_tenant_db.core.logging import (
    JSONFormatter,
    setup_logging,
    TenantContextFilter,
    get_logger,
    log_tenant_operation,
)


class TestJSONFormatter:
    """Test cases for JSONFormatter class."""

    def test_json_formatter_initialization(self):
        """Test JSONFormatter can be initialized."""
        formatter = JSONFormatter()
        
        assert isinstance(formatter, logging.Formatter)
        assert isinstance(formatter, JSONFormatter)

    def test_json_formatter_basic_formatting(self):
        """Test basic JSON formatting functionality."""
        formatter = JSONFormatter()
        
        # Create a log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Format the record
        result = formatter.format(record)
        
        # Should be valid JSON
        parsed = json.loads(result)
        
        # Check required fields
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "logger" in parsed
        assert "message" in parsed
        assert "module" in parsed
        assert "function" in parsed
        assert "line" in parsed
        
        # Check values
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert parsed["message"] == "Test message"
        assert parsed["line"] == 42

    def test_json_formatter_timestamp_format(self):
        """Test JSON formatter timestamp format."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        with patch('src.multi_tenant_db.core.logging.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2025, 8, 13, 10, 30, 45, 123456)
            
            result = formatter.format(record)
            parsed = json.loads(result)
            
            # Should have ISO format timestamp with Z suffix
            assert parsed["timestamp"].endswith("Z")
            assert "2025-08-13T10:30:45.123456Z" == parsed["timestamp"]

    def test_json_formatter_with_tenant_context(self):
        """Test JSON formatter with tenant context."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Add tenant context to record
        tenant_id = str(uuid4())
        record.tenant_id = tenant_id
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert "tenant_id" in parsed
        assert parsed["tenant_id"] == tenant_id

    def test_json_formatter_with_request_context(self):
        """Test JSON formatter with request context."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Add request context to record
        request_id = str(uuid4())
        record.request_id = request_id
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert "request_id" in parsed
        assert parsed["request_id"] == request_id

    def test_json_formatter_with_exception_info(self):
        """Test JSON formatter with exception information."""
        formatter = JSONFormatter()
        
        # Create exception info
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert "exception" in parsed
        assert "Test exception" in parsed["exception"]
        assert "ValueError" in parsed["exception"]

    def test_json_formatter_with_extra_fields(self):
        """Test JSON formatter with extra fields."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Add extra fields
        record.user_id = "user123"
        record.operation = "create_tenant"
        record.duration_ms = 150
        record.status = "success"
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert "user_id" in parsed
        assert "operation" in parsed
        assert "duration_ms" in parsed
        assert "status" in parsed
        assert parsed["user_id"] == "user123"
        assert parsed["operation"] == "create_tenant"
        assert parsed["duration_ms"] == 150
        assert parsed["status"] == "success"

    def test_json_formatter_filters_standard_fields(self):
        """Test that JSON formatter filters out standard logging fields."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        # Standard fields should not appear as extra fields
        standard_fields = [
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
            'filename', 'module', 'lineno', 'funcName', 'created',
            'msecs', 'relativeCreated', 'thread', 'threadName',
            'processName', 'process', 'message', 'exc_info', 'exc_text',
            'stack_info'
        ]
        
        for field in standard_fields:
            assert field not in parsed or field in ["message"]  # message is explicitly added

    def test_json_formatter_handles_non_serializable_extra_fields(self):
        """Test JSON formatter handles non-JSON-serializable extra fields."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Add non-serializable field
        record.complex_object = {"set": {1, 2, 3}, "function": lambda x: x}
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        # Should be converted to string
        assert "complex_object" in parsed
        assert isinstance(parsed["complex_object"], str)

    def test_json_formatter_different_log_levels(self):
        """Test JSON formatter with different log levels."""
        formatter = JSONFormatter()
        
        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]
        
        for level_num, level_name in levels:
            record = logging.LogRecord(
                name="test_logger",
                level=level_num,
                pathname="/test/path.py",
                lineno=1,
                msg=f"Test {level_name} message",
                args=(),
                exc_info=None,
            )
            
            result = formatter.format(record)
            parsed = json.loads(result)
            
            assert parsed["level"] == level_name
            assert parsed["message"] == f"Test {level_name} message"


class TestSetupLogging:
    """Test cases for setup_logging function."""

    def test_setup_logging_basic_functionality(self):
        """Test basic setup_logging functionality."""
        with patch("src.multi_tenant_db.core.logging.settings") as mock_settings, \
             patch("logging.getLogger") as mock_get_logger, \
             patch("logging.StreamHandler") as mock_handler_class:
            
            # Mock settings
            mock_settings.log_json = True
            mock_settings.log_level = "INFO"
            mock_settings.debug = False
            
            # Mock logger and handler
            mock_root_logger = Mock()
            mock_root_logger.handlers = []
            mock_get_logger.return_value = mock_root_logger
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler
            
            # Call setup_logging
            setup_logging()
            
            # Verify logger configuration
            mock_root_logger.setLevel.assert_called_with(logging.INFO)
            mock_root_logger.addHandler.assert_called_with(mock_handler)

    def test_setup_logging_json_formatter_configuration(self):
        """Test setup_logging with JSON formatter."""
        with patch("src.multi_tenant_db.core.logging.settings") as mock_settings, \
             patch("logging.getLogger") as mock_get_logger, \
             patch("logging.StreamHandler") as mock_handler_class:
            
            mock_settings.log_json = True
            mock_settings.log_level = "DEBUG"
            mock_settings.debug = True
            
            mock_root_logger = Mock()
            mock_root_logger.handlers = []
            mock_get_logger.return_value = mock_root_logger
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler
            
            setup_logging()
            
            # Should set JSON formatter
            mock_handler.setFormatter.assert_called_once()
            formatter_arg = mock_handler.setFormatter.call_args[0][0]
            assert isinstance(formatter_arg, JSONFormatter)

    def test_setup_logging_regular_formatter_configuration(self):
        """Test setup_logging with regular formatter."""
        with patch("src.multi_tenant_db.core.logging.settings") as mock_settings, \
             patch("logging.getLogger") as mock_get_logger, \
             patch("logging.StreamHandler") as mock_handler_class, \
             patch("logging.Formatter") as mock_formatter_class:
            
            mock_settings.log_json = False
            mock_settings.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            mock_settings.log_level = "WARNING"
            mock_settings.debug = False
            
            mock_root_logger = Mock()
            mock_root_logger.handlers = []
            mock_get_logger.return_value = mock_root_logger
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler
            mock_formatter = Mock()
            mock_formatter_class.return_value = mock_formatter
            
            setup_logging()
            
            # Should set regular formatter
            mock_formatter_class.assert_called_with(mock_settings.log_format)
            mock_handler.setFormatter.assert_called_with(mock_formatter)

    def test_setup_logging_removes_existing_handlers(self):
        """Test that setup_logging removes existing handlers."""
        with patch("src.multi_tenant_db.core.logging.settings") as mock_settings, \
             patch("logging.getLogger") as mock_get_logger, \
             patch("logging.StreamHandler") as mock_handler_class:
            
            mock_settings.log_json = True
            mock_settings.log_level = "INFO"
            mock_settings.debug = False
            
            # Mock existing handlers
            existing_handler1 = Mock()
            existing_handler2 = Mock()
            mock_root_logger = Mock()
            mock_root_logger.handlers = [existing_handler1, existing_handler2]
            mock_get_logger.return_value = mock_root_logger
            
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler
            
            setup_logging()
            
            # Should remove existing handlers
            assert mock_root_logger.removeHandler.call_count == 2
            mock_root_logger.removeHandler.assert_any_call(existing_handler1)
            mock_root_logger.removeHandler.assert_any_call(existing_handler2)

    def test_setup_logging_configures_specific_loggers(self):
        """Test that setup_logging configures specific loggers."""
        with patch("src.multi_tenant_db.core.logging.settings") as mock_settings, \
             patch("logging.getLogger") as mock_get_logger:
            
            mock_settings.log_json = True
            mock_settings.log_level = "INFO"
            mock_settings.debug = True
            
            # Mock loggers
            loggers = {}
            
            def mock_get_logger_side_effect(name=None):
                if name is None:
                    name = "root"
                if name not in loggers:
                    loggers[name] = Mock()
                    loggers[name].handlers = []
                return loggers[name]
            
            mock_get_logger.side_effect = mock_get_logger_side_effect
            
            setup_logging()
            
            # Check that specific loggers were configured
            expected_loggers = [
                "uvicorn.access",
                "uvicorn.error", 
                "sqlalchemy.engine",
                "multi_tenant_db",
            ]
            
            for logger_name in expected_loggers:
                assert logger_name in loggers
                loggers[logger_name].setLevel.assert_called_once()

    def test_setup_logging_different_log_levels(self):
        """Test setup_logging with different log levels."""
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        for level in log_levels:
            with patch("src.multi_tenant_db.core.logging.settings") as mock_settings, \
                 patch("logging.getLogger") as mock_get_logger, \
                 patch("logging.StreamHandler"):
                
                mock_settings.log_json = True
                mock_settings.log_level = level
                mock_settings.debug = False
                
                mock_root_logger = Mock()
                mock_root_logger.handlers = []
                mock_get_logger.return_value = mock_root_logger
                
                setup_logging()
                
                expected_level = getattr(logging, level)
                mock_root_logger.setLevel.assert_called_with(expected_level)


class TestTenantContextFilter:
    """Test cases for TenantContextFilter class."""

    def test_tenant_context_filter_initialization(self):
        """Test TenantContextFilter can be initialized."""
        filter_instance = TenantContextFilter()
        
        assert isinstance(filter_instance, logging.Filter)
        assert isinstance(filter_instance, TenantContextFilter)

    def test_tenant_context_filter_adds_tenant_id(self):
        """Test TenantContextFilter adds tenant_id to record."""
        filter_instance = TenantContextFilter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = filter_instance.filter(record)
        
        # Should return True (don't filter out)
        assert result is True
        
        # Should have tenant_id attribute
        assert hasattr(record, 'tenant_id')

    def test_tenant_context_filter_preserves_existing_tenant_id(self):
        """Test TenantContextFilter preserves existing tenant_id."""
        filter_instance = TenantContextFilter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Set existing tenant_id
        existing_tenant_id = str(uuid4())
        record.tenant_id = existing_tenant_id
        
        result = filter_instance.filter(record)
        
        assert result is True
        assert record.tenant_id == existing_tenant_id

    def test_tenant_context_filter_sets_unknown_for_missing_tenant(self):
        """Test TenantContextFilter sets 'unknown' for missing tenant."""
        filter_instance = TenantContextFilter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # No tenant_id set initially
        assert not hasattr(record, 'tenant_id')
        
        result = filter_instance.filter(record)
        
        assert result is True
        assert record.tenant_id == "unknown"

    def test_tenant_context_filter_always_returns_true(self):
        """Test that TenantContextFilter never filters out records."""
        filter_instance = TenantContextFilter()
        
        # Test with various record types
        records = []
        for level in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]:
            record = logging.LogRecord(
                name="test_logger",
                level=level,
                pathname="/test/path.py",
                lineno=1,
                msg=f"Test {level} message",
                args=(),
                exc_info=None,
            )
            records.append(record)
        
        for record in records:
            result = filter_instance.filter(record)
            assert result is True


class TestGetLogger:
    """Test cases for get_logger function."""

    def test_get_logger_basic_functionality(self):
        """Test basic get_logger functionality."""
        with patch("logging.getLogger") as mock_get_logger, \
             patch("src.multi_tenant_db.core.logging.settings") as mock_settings:
            
            mock_settings.debug = False
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            result = get_logger("test.module")
            
            assert result is mock_logger
            mock_get_logger.assert_called_once_with("test.module")

    def test_get_logger_adds_tenant_filter_in_debug_mode(self):
        """Test get_logger adds tenant filter in debug mode."""
        with patch("logging.getLogger") as mock_get_logger, \
             patch("src.multi_tenant_db.core.logging.settings") as mock_settings:
            
            mock_settings.debug = True
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            result = get_logger("test.module")
            
            assert result is mock_logger
            mock_logger.addFilter.assert_called_once()
            filter_arg = mock_logger.addFilter.call_args[0][0]
            assert isinstance(filter_arg, TenantContextFilter)

    def test_get_logger_no_filter_in_non_debug_mode(self):
        """Test get_logger doesn't add filter in non-debug mode."""
        with patch("logging.getLogger") as mock_get_logger, \
             patch("src.multi_tenant_db.core.logging.settings") as mock_settings:
            
            mock_settings.debug = False
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            result = get_logger("test.module")
            
            assert result is mock_logger
            mock_logger.addFilter.assert_not_called()

    def test_get_logger_with_various_module_names(self):
        """Test get_logger with various module names."""
        module_names = [
            "__main__",
            "src.multi_tenant_db.models.tenant",
            "src.multi_tenant_db.api.v1.tenants",
            "tests.unit.test_logging",
            "uvicorn.server",
        ]
        
        for module_name in module_names:
            with patch("logging.getLogger") as mock_get_logger, \
                 patch("src.multi_tenant_db.core.logging.settings") as mock_settings:
                
                mock_settings.debug = False
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger
                
                result = get_logger(module_name)
                
                assert result is mock_logger
                mock_get_logger.assert_called_once_with(module_name)


class TestLogTenantOperation:
    """Test cases for log_tenant_operation function."""

    def test_log_tenant_operation_basic_functionality(self):
        """Test basic log_tenant_operation functionality."""
        mock_logger = Mock()
        tenant_id = str(uuid4())
        operation = "create_tenant"
        
        log_tenant_operation(mock_logger, tenant_id, operation)
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        # Check message
        assert call_args[0][0] == f"Tenant operation: {operation}"
        
        # Check extra info
        extra = call_args[1]["extra"]
        assert extra["tenant_id"] == tenant_id

    def test_log_tenant_operation_with_details(self):
        """Test log_tenant_operation with additional details."""
        mock_logger = Mock()
        tenant_id = str(uuid4())
        operation = "update_tenant"
        details = {
            "user_id": "admin123",
            "duration_ms": 250,
            "changes": ["name", "metadata"],
            "status": "success",
        }
        
        log_tenant_operation(mock_logger, tenant_id, operation, details)
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        # Check message
        assert call_args[0][0] == f"Tenant operation: {operation}"
        
        # Check extra info includes tenant_id and details
        extra = call_args[1]["extra"]
        assert extra["tenant_id"] == tenant_id
        assert extra["user_id"] == "admin123"
        assert extra["duration_ms"] == 250
        assert extra["changes"] == ["name", "metadata"]
        assert extra["status"] == "success"

    def test_log_tenant_operation_without_details(self):
        """Test log_tenant_operation without details."""
        mock_logger = Mock()
        tenant_id = "hsbc-holdings"
        operation = "delete_tenant"
        
        log_tenant_operation(mock_logger, tenant_id, operation, None)
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        # Check message
        assert call_args[0][0] == f"Tenant operation: {operation}"
        
        # Check extra info only has tenant_id
        extra = call_args[1]["extra"]
        assert extra == {"tenant_id": tenant_id}

    def test_log_tenant_operation_realistic_scenarios(self):
        """Test log_tenant_operation with realistic fintech scenarios."""
        mock_logger = Mock()
        
        scenarios = [
            {
                "tenant_id": "hsbc-holdings",
                "operation": "create_subsidiary",
                "details": {
                    "parent_tenant": "hsbc-holdings",
                    "subsidiary_name": "HSBC Hong Kong",
                    "region": "Asia Pacific",
                    "business_unit": "retail_banking",
                },
            },
            {
                "tenant_id": "jpmorgan-chase",
                "operation": "compliance_audit",
                "details": {
                    "auditor": "regulatory_team",
                    "audit_type": "quarterly_review",
                    "findings": 0,
                    "status": "passed",
                },
            },
            {
                "tenant_id": "goldman-sachs-london",
                "operation": "data_migration",
                "details": {
                    "source_system": "legacy_db",
                    "target_system": "modernized_db",
                    "records_migrated": 1500000,
                    "duration_hours": 4.5,
                },
            },
        ]
        
        for scenario in scenarios:
            mock_logger.reset_mock()
            
            log_tenant_operation(
                mock_logger,
                scenario["tenant_id"],
                scenario["operation"],
                scenario["details"]
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            
            # Check message
            assert call_args[0][0] == f"Tenant operation: {scenario['operation']}"
            
            # Check extra info
            extra = call_args[1]["extra"]
            assert extra["tenant_id"] == scenario["tenant_id"]
            
            # Check details are included
            for key, value in scenario["details"].items():
                assert extra[key] == value

    def test_log_tenant_operation_with_empty_details(self):
        """Test log_tenant_operation with empty details dict."""
        mock_logger = Mock()
        tenant_id = str(uuid4())
        operation = "test_operation"
        details = {}
        
        log_tenant_operation(mock_logger, tenant_id, operation, details)
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        extra = call_args[1]["extra"]
        assert extra == {"tenant_id": tenant_id}


class TestLoggingIntegration:
    """Test cases for logging integration scenarios."""

    def test_json_formatter_with_tenant_context_filter(self):
        """Test JSON formatter works with tenant context filter."""
        formatter = JSONFormatter()
        filter_instance = TenantContextFilter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Apply filter first
        filter_result = filter_instance.filter(record)
        assert filter_result is True
        
        # Then format
        result = formatter.format(record)
        parsed = json.loads(result)
        
        # Should include tenant_id from filter
        assert "tenant_id" in parsed
        assert parsed["tenant_id"] == "unknown"  # Default from filter

    def test_logging_configuration_integration(self):
        """Test full logging configuration integration."""
        with patch("src.multi_tenant_db.core.logging.settings") as mock_settings:
            mock_settings.log_json = True
            mock_settings.log_level = "INFO"
            mock_settings.debug = True
            
            # This should not raise any exceptions
            setup_logging()
            
            # Get a logger with the new configuration
            logger = get_logger("test.integration")
            
            # Should be able to use the logger
            assert logger is not None

    def test_realistic_logging_workflow(self):
        """Test realistic logging workflow for fintech operations."""
        # This is a comprehensive integration test
        with patch("src.multi_tenant_db.core.logging.settings") as mock_settings:
            mock_settings.log_json = True
            mock_settings.log_level = "INFO"
            mock_settings.debug = True
            
            # Setup logging
            setup_logging()
            
            # Get logger
            logger = get_logger("fintech.tenant.operations")
            
            # Simulate tenant operations
            tenant_id = "hsbc-holdings"
            
            with patch.object(logger, 'info') as mock_info:
                # Log tenant operation
                log_tenant_operation(
                    logger,
                    tenant_id,
                    "create_account",
                    {
                        "account_type": "savings",
                        "initial_deposit": 1000.00,
                        "currency": "USD",
                        "kyc_verified": True,
                    }
                )
                
                # Verify logging was called correctly
                mock_info.assert_called_once()
                call_args = mock_info.call_args
                
                assert "Tenant operation: create_account" in call_args[0][0]
                extra = call_args[1]["extra"]
                assert extra["tenant_id"] == tenant_id
                assert extra["account_type"] == "savings"
                assert extra["initial_deposit"] == 1000.00

    def test_module_level_imports_and_usage(self):
        """Test that all logging components can be imported and used."""
        from src.multi_tenant_db.core import logging as logging_module
        
        # Check all expected components are available
        assert hasattr(logging_module, 'JSONFormatter')
        assert hasattr(logging_module, 'setup_logging')
        assert hasattr(logging_module, 'TenantContextFilter')
        assert hasattr(logging_module, 'get_logger')
        assert hasattr(logging_module, 'log_tenant_operation')
        
        # Check they are the expected types
        assert callable(logging_module.setup_logging)
        assert callable(logging_module.get_logger)
        assert callable(logging_module.log_tenant_operation)

    def test_settings_integration(self):
        """Test integration with settings module."""
        # Test that logging module correctly imports and uses settings
        from src.multi_tenant_db.core.logging import settings
        
        # Settings should be available
        assert settings is not None
        
        # Should have expected attributes (these are tested in config tests)
        expected_attrs = ['log_level', 'log_json', 'debug']
        for attr in expected_attrs:
            assert hasattr(settings, attr)

    def test_error_handling_in_logging_components(self):
        """Test error handling in logging components."""
        # Test JSONFormatter handles formatting errors gracefully
        formatter = JSONFormatter()
        
        # Create a problematic record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # This should not raise an exception even with problematic data
        result = formatter.format(record)
        assert isinstance(result, str)
        
        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)