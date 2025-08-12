"""
Tenant model for multi-tenant application.

Implements hierarchical tenant structure with Row Level Security (RLS) integration
for complete tenant data isolation in PostgreSQL.
"""

import enum
from typing import TYPE_CHECKING, Optional, Union
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    pass  # For future foreign key relationships


class TenantType(str, enum.Enum):
    """
    Tenant type enumeration.
    
    PARENT: Top-level tenant (independent organization)
    SUBSIDIARY: Child tenant under a parent tenant
    """
    
    PARENT = "parent"
    SUBSIDIARY = "subsidiary"
    
    def __str__(self) -> str:
        """Return the enum value for string conversion."""
        return self.value


class Tenant(Base, TimestampMixin):
    """
    Tenant model with hierarchical support and RLS integration.
    
    Supports multi-tenant architecture with:
    - Parent-subsidiary relationships
    - Complete data isolation via Row Level Security
    - Hierarchical access control (parents can access subsidiary data)
    - Maximum 2-level hierarchy depth
    
    The table name is automatically generated as 'tenants' from the class name.
    """
    
    # Primary key
    tenant_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier for the tenant",
    )
    
    # Tenant name - unique within parent hierarchy
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable tenant name, unique within parent hierarchy",
    )
    
    # Self-referencing foreign key for hierarchy
    parent_tenant_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="RESTRICT"),
        nullable=True,
        comment="Reference to parent tenant for subsidiaries",
    )
    
    # Tenant type
    tenant_type: Mapped[TenantType] = mapped_column(
        ENUM(*[e.value for e in TenantType], name="tenant_type", create_type=False),
        nullable=False,
        comment="Type of tenant: parent (top-level) or subsidiary",
    )
    
    # Additional metadata as JSON
    tenant_metadata: Mapped[dict | None] = mapped_column(
        "metadata",  # Map to actual database column name
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional JSON metadata for flexible storage",
    )
    
    # Relationships
    parent: Mapped[Optional["Tenant"]] = relationship(
        "Tenant",
        remote_side="Tenant.tenant_id",
        back_populates="subsidiaries",
    )
    
    subsidiaries: Mapped[list["Tenant"]] = relationship(
        "Tenant",
        back_populates="parent",
        cascade="all, delete",
        passive_deletes=True,
    )
    
    # Table constraints
    __table_args__ = (
        # Unique name within parent hierarchy
        Index(
            "uq_tenant_name_per_parent",
            "name",
            "parent_tenant_id",
            unique=True,
        ),
        
        # Parent tenants have no parent, subsidiaries have parent
        CheckConstraint(
            "(tenant_type = 'parent' AND parent_tenant_id IS NULL) OR "
            "(tenant_type = 'subsidiary' AND parent_tenant_id IS NOT NULL)",
            name="ck_tenant_parent_logic",
        ),
        
        # Prevent self-referencing
        CheckConstraint(
            "tenant_id != parent_tenant_id",
            name="ck_tenant_no_self_reference",
        ),
        
        # Ensure name is not empty after trimming
        CheckConstraint(
            "trim(name) != ''",
            name="ck_tenant_name_not_empty",
        ),
        
        # Additional indexes for performance
        Index("ix_tenant_parent_id", "parent_tenant_id"),
        Index("ix_tenant_type", "tenant_type"),
        Index("ix_tenant_name_lower", text("lower(name)")),
        Index("ix_tenant_metadata", "metadata", postgresql_using="gin"),
    )
    
    def __repr__(self) -> str:
        """String representation of the tenant."""
        return (
            f"<Tenant(id={self.tenant_id}, name='{self.name}', "
            f"type={self.tenant_type})>"
        )
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self.name} ({self.tenant_type.value})"
    
    @property
    def is_parent(self) -> bool:
        """Check if this tenant is a parent tenant."""
        return self.tenant_type == TenantType.PARENT
    
    @property
    def is_subsidiary(self) -> bool:
        """Check if this tenant is a subsidiary tenant."""
        return self.tenant_type == TenantType.SUBSIDIARY
    
    @property
    def has_subsidiaries(self) -> bool:
        """Check if this tenant has any subsidiaries."""
        return len(self.subsidiaries) > 0