"""
Pydantic schemas for tenant CRUD operations.

Implements comprehensive validation and serialization schemas for the tenant API
endpoints based on the functional requirements and database model.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..models.tenant import TenantType


class TenantBase(BaseModel):
    """Base tenant schema with common fields."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable tenant name, unique within parent hierarchy",
        examples=["HSBC Hong Kong", "JP Morgan Chase"]
    )
    
    tenant_type: TenantType = Field(
        ...,
        description="Type of tenant: parent (top-level) or subsidiary"
    )
    
    metadata: dict[str, Any] | None = Field(
        default_factory=dict,
        alias="tenant_metadata",
        description="Additional JSON metadata for flexible storage",
        examples=[{
            "country": "Hong Kong",
            "business_unit": "retail_banking",
            "status": "active"
        }]
    )
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and clean the tenant name."""
        if not v or not v.strip():
            raise ValueError("Tenant name cannot be empty or whitespace only")
        
        # Trim whitespace and validate length after trimming
        cleaned_name = v.strip()
        if len(cleaned_name) > 200:
            raise ValueError("Tenant name cannot exceed 200 characters after trimming")
        
        return cleaned_name
    
    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate metadata is a proper dictionary."""
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError("Metadata must be a dictionary")
        return v


class TenantCreate(TenantBase):
    """Schema for creating a new tenant."""
    
    parent_tenant_id: UUID | None = Field(
        default=None,
        description="Reference to parent tenant for subsidiaries",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    
    @model_validator(mode='after')
    def validate_tenant_hierarchy(self) -> 'TenantCreate':
        """Validate tenant type consistency with parent relationship."""
        if self.tenant_type == TenantType.PARENT and self.parent_tenant_id is not None:
            raise ValueError("Parent tenants cannot have a parent tenant")
        
        if self.tenant_type == TenantType.SUBSIDIARY and self.parent_tenant_id is None:
            raise ValueError("Subsidiary tenants must have a parent tenant")
        
        return self
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "HSBC Hong Kong",
                    "parent_tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                    "tenant_type": "subsidiary",
                    "metadata": {
                        "country": "Hong Kong",
                        "business_unit": "retail_banking"
                    }
                },
                {
                    "name": "JP Morgan Chase",
                    "tenant_type": "parent",
                    "metadata": {
                        "country": "United States",
                        "headquarters": "New York"
                    }
                }
            ]
        }
    )


class TenantUpdate(BaseModel):
    """Schema for updating tenant information."""
    
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Updated tenant name"
    )
    
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Updated metadata (replaces existing metadata completely)"
    )
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate and clean the tenant name if provided."""
        if v is None:
            return None
        
        if not v or not v.strip():
            raise ValueError("Tenant name cannot be empty or whitespace only")
        
        # Trim whitespace and validate length after trimming
        cleaned_name = v.strip()
        if len(cleaned_name) > 200:
            raise ValueError("Tenant name cannot exceed 200 characters after trimming")
        
        return cleaned_name
    
    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate metadata is a proper dictionary if provided."""
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError("Metadata must be a dictionary")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "HSBC Hong Kong Limited",
                    "metadata": {
                        "country": "Hong Kong",
                        "business_unit": "retail_banking",
                        "status": "active"
                    }
                }
            ]
        }
    )


class TenantResponse(TenantBase):
    """Schema for tenant response with all fields."""
    
    tenant_id: UUID = Field(
        ...,
        description="Unique identifier for the tenant"
    )
    
    parent_tenant_id: UUID | None = Field(
        default=None,
        description="Reference to parent tenant for subsidiaries"
    )
    
    created_at: datetime = Field(
        ...,
        description="Timestamp when the tenant was created"
    )
    
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the tenant was last updated"
    )
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "HSBC Hong Kong",
                    "parent_tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                    "tenant_type": "subsidiary",
                    "created_at": "2025-08-05T10:00:00Z",
                    "updated_at": "2025-08-05T10:00:00Z",
                    "metadata": {
                        "country": "Hong Kong",
                        "business_unit": "retail_banking"
                    }
                }
            ]
        }
    )


class TenantListItem(BaseModel):
    """Schema for tenant list item (minimal fields for listing)."""
    
    tenant_id: UUID = Field(
        ...,
        description="Unique identifier for the tenant"
    )
    
    name: str = Field(
        ...,
        description="Human-readable tenant name"
    )
    
    tenant_type: TenantType = Field(
        ...,
        description="Type of tenant: parent or subsidiary"
    )
    
    created_at: datetime = Field(
        ...,
        description="Timestamp when the tenant was created"
    )
    
    model_config = ConfigDict(
        from_attributes=True
    )


class TenantListResponse(BaseModel):
    """Schema for paginated tenant list response."""
    
    tenants: list[TenantListItem] = Field(
        ...,
        description="List of tenants for current page"
    )
    
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of tenants matching the criteria"
    )
    
    limit: int = Field(
        ...,
        ge=1,
        le=1000,
        description="Maximum number of results per page"
    )
    
    offset: int = Field(
        ...,
        ge=0,
        description="Number of results skipped"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "tenants": [
                        {
                            "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "HSBC",
                            "tenant_type": "parent",
                            "created_at": "2025-08-05T09:00:00Z"
                        }
                    ],
                    "total_count": 1,
                    "limit": 100,
                    "offset": 0
                }
            ]
        }
    )


class TenantDeleteResponse(BaseModel):
    """Schema for tenant deletion response."""
    
    message: str = Field(
        ...,
        description="Confirmation message for successful deletion"
    )
    
    tenant_id: UUID = Field(
        ...,
        description="ID of the deleted tenant"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "Tenant successfully deleted",
                    "tenant_id": "123e4567-e89b-12d3-a456-426614174000"
                }
            ]
        }
    )