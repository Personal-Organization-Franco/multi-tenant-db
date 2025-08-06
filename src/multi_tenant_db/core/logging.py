"""
Logging configuration for the multi-tenant application.

Provides structured logging configuration with tenant context
and proper log formatting for different environments.
"""

import logging
import sys
from typing import Any

from .config import get_settings

settings = get_settings()


def setup_logging() -> None:
    """
    Configure application logging.

    Sets up logging configuration based on environment settings
    with proper formatting and log levels.
    """
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format=settings.log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

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
