"""
Base SQLAlchemy models and configuration.

Provides common base class with essential fields and configurations
for all database models in the multi-tenant application.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    
    Provides common configuration and async support for all models.
    All tables will have proper RLS (Row Level Security) policies applied
    at the database level.
    """
    
    # Generate table names automatically from class names
    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        # Convert CamelCase to snake_case and pluralize
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
        
        # Add 's' for pluralization (simple rule)
        if not name.endswith('s'):
            name += 's'
        
        return name


class TimestampMixin:
    """
    Mixin class that provides created_at and updated_at timestamp fields.
    
    These fields are automatically managed by database triggers for updated_at
    and default values for created_at.
    """
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Record last update timestamp"
    )