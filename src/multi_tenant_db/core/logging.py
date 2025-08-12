"""
Logging configuration for the multi-tenant application.

Provides structured logging configuration with tenant context
and proper log formatting for different environments.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any

from .config import get_settings

settings = get_settings()


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Formats log records as JSON objects with consistent structure
    for better parsing and monitoring.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Create base log structure
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add tenant context if available
        if hasattr(record, 'tenant_id'):
            log_data["tenant_id"] = record.tenant_id
            
        # Add request context if available  
        if hasattr(record, 'request_id'):
            log_data["request_id"] = record.request_id
            
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'message', 'exc_info', 'exc_text',
                'stack_info', 'tenant_id', 'request_id'
            }:
                # Only include extra fields that are JSON serializable
                try:
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)
        
        return json.dumps(log_data, default=str)


def setup_logging() -> None:
    """
    Configure application logging.

    Sets up logging configuration based on environment settings
    with proper formatting and log levels.
    """
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Choose formatter based on configuration
    if settings.log_json:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(settings.log_format)
    
    handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))
    
    # Remove any existing handlers
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)
    
    # Add our JSON handler
    root_logger.addHandler(handler)

    # Configure specific loggers for different components
    loggers = {
        "uvicorn.access": logging.WARNING,
        "uvicorn.error": logging.INFO,
        "sqlalchemy.engine": logging.WARNING if not settings.debug else logging.INFO,
        "multi_tenant_db": getattr(logging, settings.log_level),
    }

    for logger_name, level in loggers.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)


class TenantContextFilter(logging.Filter):
    """
    Logging filter to add tenant context to log records.

    This filter can be used to automatically include tenant information
    in log messages for better traceability in multi-tenant environments.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add tenant context to log record if available.

        Args:
            record: Log record to filter

        Returns:
            bool: Always True (don't filter out records)
        """
        # Try to get tenant context from current request
        # This would be enhanced when request context is available
        tenant_id = getattr(record, "tenant_id", "unknown")
        record.tenant_id = tenant_id

        return True


def get_logger(name: str) -> logging.Logger:
    """
    Get logger with application configuration.

    Args:
        name: Logger name (typically __name__)

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)

    # Add tenant context filter if in debug mode
    if settings.debug:
        tenant_filter = TenantContextFilter()
        logger.addFilter(tenant_filter)

    return logger


def log_tenant_operation(
    logger: logging.Logger,
    tenant_id: str,
    operation: str,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Log tenant-specific operations.

    Args:
        logger: Logger instance
        tenant_id: Tenant identifier
        operation: Operation being performed
        details: Additional operation details
    """
    extra_info = {"tenant_id": tenant_id}
    if details:
        extra_info.update(details)

    logger.info(
        f"Tenant operation: {operation}",
        extra=extra_info,
    )
