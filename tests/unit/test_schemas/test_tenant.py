"""
Unit tests for tenant schemas.

Tests all Pydantic schemas for tenant operations including validation,
serialization, field validation, and edge cases.
"""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Any

import pytest
from pydantic import ValidationError

from src.multi_tenant_db.models.tenant import TenantType
from src.multi_tenant_db.schemas.tenant import (
    TenantBase,
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantListItem,
    TenantListResponse,
    TenantDeleteResponse,
)
from tests.factories import (
    TenantCreateSchemaFactory,
    ParentTenantCreateSchemaFactory,
    SubsidiaryTenantCreateSchemaFactory,
    TenantUpdateSchemaFactory,
    TenantResponseSchemaFactory,
    TenantListItemSchemaFactory,
    generate_valid_tenant_name,
    generate_invalid_tenant_names,
    generate_valid_metadata,
    generate_realistic_parent_tenant_data,
    generate_realistic_subsidiary_tenant_data,
)


class TestTenantBase:
    """Test cases for TenantBase schema."""

    def test_tenant_base_valid_creation(self):
        """Test creating TenantBase with valid data."""
        data = {
            "name": "HSBC Holdings",
            "tenant_type": TenantType.PARENT,
            "tenant_metadata": {
                "country": "United Kingdom",
                "business_unit": "banking"
            }
        }
        
        schema = TenantBase(**data)
        
        assert schema.name == "HSBC Holdings"
        assert schema.tenant_type == TenantType.PARENT
        assert schema.metadata == {"country": "United Kingdom", "business_unit": "banking"}

    def test_tenant_base_name_field_validation(self):
        """Test name field validation in TenantBase."""
        # Valid names
        valid_names = [
            "HSBC",
            "JP Morgan Chase",
            "A",  # Minimum length
            "A" * 200,  # Maximum length
            "Name with spaces and numbers 123",
        ]
        
        for name in valid_names:
            schema = TenantBase(
                name=name,
                tenant_type=TenantType.PARENT,
            )
            assert schema.name == name

    def test_tenant_base_name_validation_empty_string(self):
        """Test name validation with empty string."""
        with pytest.raises(ValidationError) as exc_info:
            TenantBase(
                name="",
                tenant_type=TenantType.PARENT,
            )
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("cannot be empty" in str(error.get('msg', '')) for error in errors)

    def test_tenant_base_name_validation_whitespace_only(self):
        """Test name validation with whitespace-only string."""
        with pytest.raises(ValidationError) as exc_info:
            TenantBase(
                name="   ",
                tenant_type=TenantType.PARENT,
            )
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("cannot be empty" in str(error.get('msg', '')) for error in errors)

    def test_tenant_base_name_validation_too_long(self):
        """Test name validation with string too long."""
        with pytest.raises(ValidationError) as exc_info:
            TenantBase(
                name="A" * 201,  # Over 200 character limit
                tenant_type=TenantType.PARENT,
            )
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("200 characters" in str(error.get('msg', '')) for error in errors)

    def test_tenant_base_name_trimming(self):
        """Test that name is properly trimmed."""
        schema = TenantBase(
            name="  HSBC Holdings  ",
            tenant_type=TenantType.PARENT,
        )
        
        assert schema.name == "HSBC Holdings"

    def test_tenant_base_tenant_type_validation(self):
        """Test tenant_type field validation."""
        # Valid types
        for tenant_type in TenantType:
            schema = TenantBase(
                name="Test Bank",
                tenant_type=tenant_type,
            )
            assert schema.tenant_type == tenant_type

    def test_tenant_base_tenant_type_string_conversion(self):
        """Test tenant_type with string values."""
        schema = TenantBase(
            name="Test Bank",
            tenant_type="parent",  # String instead of enum
        )
        
        assert schema.tenant_type == TenantType.PARENT

    def test_tenant_base_metadata_default(self):
        """Test metadata field default value."""
        schema = TenantBase(
            name="Test Bank",
            tenant_type=TenantType.PARENT,
        )
        
        assert schema.metadata == {}

    def test_tenant_base_metadata_none_conversion(self):
        """Test metadata None value conversion to empty dict."""
        schema = TenantBase(
            name="Test Bank",
            tenant_type=TenantType.PARENT,
            tenant_metadata=None,
        )
        
        assert schema.metadata == {}

    def test_tenant_base_metadata_validation_valid_dict(self):
        """Test metadata validation with valid dictionary."""
        valid_metadata = {
            "country": "United States",
            "business_unit": "investment_banking",
            "status": "active",
            "employee_count": 50000,
            "licenses": ["banking", "securities"],
            "nested": {
                "address": {
                    "street": "123 Wall Street",
                    "city": "New York"
                }
            }
        }
        
        schema = TenantBase(
            name="Goldman Sachs",
            tenant_type=TenantType.PARENT,
            tenant_metadata=valid_metadata,
        )
        
        assert schema.metadata == valid_metadata

    def test_tenant_base_metadata_validation_invalid_type(self):
        """Test metadata validation with invalid type."""
        with pytest.raises(ValidationError) as exc_info:
            TenantBase(
                name="Test Bank",
                tenant_type=TenantType.PARENT,
                tenant_metadata="not a dict",  # String instead of dict
            )
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("must be a dictionary" in str(error.get('msg', '')) for error in errors)

    def test_tenant_base_alias_usage(self):
        """Test using alias for metadata field."""
        data = {
            "name": "Test Bank",
            "tenant_type": TenantType.PARENT,
            "tenant_metadata": {"key": "value"}  # Using alias
        }
        
        schema = TenantBase(**data)
        assert schema.metadata == {"key": "value"}

    def test_tenant_base_field_examples(self):
        """Test that field examples are properly defined."""
        # This tests the schema structure, not runtime behavior
        schema_dict = TenantBase.model_json_schema()
        
        # Check that examples exist in schema
        properties = schema_dict.get("properties", {})
        
        # Name field should have examples
        name_field = properties.get("name", {})
        assert "examples" in name_field
        
        # Metadata field should have examples
        metadata_field = properties.get("tenant_metadata", {})
        assert "examples" in metadata_field


class TestTenantCreate:
    """Test cases for TenantCreate schema."""

    def test_tenant_create_valid_parent(self):
        """Test creating TenantCreate for parent tenant."""
        data = generate_realistic_parent_tenant_data()
        schema = TenantCreate(**data)
        
        assert schema.tenant_type == TenantType.PARENT
        assert schema.parent_tenant_id is None
        assert isinstance(schema.metadata, dict)

    def test_tenant_create_valid_subsidiary(self):
        """Test creating TenantCreate for subsidiary tenant."""
        parent_id = uuid4()
        data = generate_realistic_subsidiary_tenant_data(parent_id)
        schema = TenantCreate(**data)
        
        assert schema.tenant_type == TenantType.SUBSIDIARY
        assert schema.parent_tenant_id == parent_id
        assert isinstance(schema.metadata, dict)

    def test_tenant_create_parent_tenant_id_field(self):
        """Test parent_tenant_id field configuration."""
        # Valid UUID
        parent_id = uuid4()
        schema = TenantCreate(
            name="Subsidiary Bank",
            tenant_type=TenantType.SUBSIDIARY,
            parent_tenant_id=parent_id,
        )
        
        assert schema.parent_tenant_id == parent_id

    def test_tenant_create_parent_tenant_id_none(self):
        """Test parent_tenant_id with None value."""
        schema = TenantCreate(
            name="Parent Bank", 
            tenant_type=TenantType.PARENT,
            parent_tenant_id=None,
        )
        
        assert schema.parent_tenant_id is None

    def test_tenant_create_hierarchy_validation_parent_with_no_parent_id(self):
        """Test validation: parent tenants cannot have parent_tenant_id."""
        schema = TenantCreate(
            name="Parent Bank",
            tenant_type=TenantType.PARENT,
            parent_tenant_id=None,
        )
        
        # Should be valid
        assert schema.tenant_type == TenantType.PARENT
        assert schema.parent_tenant_id is None

    def test_tenant_create_hierarchy_validation_parent_with_parent_id_fails(self):
        """Test validation: parent tenants with parent_tenant_id should fail."""
        with pytest.raises(ValidationError) as exc_info:
            TenantCreate(
                name="Invalid Parent",
                tenant_type=TenantType.PARENT,
                parent_tenant_id=uuid4(),  # Invalid: parent with parent_id
            )
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("cannot have a parent" in str(error.get('msg', '')) for error in errors)

    def test_tenant_create_hierarchy_validation_subsidiary_with_parent_id(self):
        """Test validation: subsidiary tenants must have parent_tenant_id."""
        schema = TenantCreate(
            name="Subsidiary Bank",
            tenant_type=TenantType.SUBSIDIARY,
            parent_tenant_id=uuid4(),
        )
        
        # Should be valid
        assert schema.tenant_type == TenantType.SUBSIDIARY
        assert schema.parent_tenant_id is not None

    def test_tenant_create_hierarchy_validation_subsidiary_without_parent_id_fails(self):
        """Test validation: subsidiary tenants without parent_tenant_id should fail."""
        with pytest.raises(ValidationError) as exc_info:
            TenantCreate(
                name="Invalid Subsidiary",
                tenant_type=TenantType.SUBSIDIARY,
                parent_tenant_id=None,  # Invalid: subsidiary without parent_id
            )
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("must have a parent" in str(error.get('msg', '')) for error in errors)

    def test_tenant_create_json_schema_examples(self):
        """Test TenantCreate JSON schema examples."""
        schema_dict = TenantCreate.model_json_schema()
        
        assert "examples" in schema_dict
        examples = schema_dict["examples"]
        assert len(examples) >= 2  # Parent and subsidiary examples
        
        # Check parent example
        parent_example = None
        subsidiary_example = None
        
        for example in examples:
            if example.get("tenant_type") == "parent":
                parent_example = example
            elif example.get("tenant_type") == "subsidiary":
                subsidiary_example = example
        
        assert parent_example is not None
        assert parent_example.get("parent_tenant_id") is None
        
        assert subsidiary_example is not None
        assert subsidiary_example.get("parent_tenant_id") is not None

    def test_tenant_create_with_factory(self):
        """Test TenantCreate using factory."""
        schema = TenantCreateSchemaFactory.build()
        
        assert isinstance(schema.name, str)
        assert len(schema.name) > 0
        assert schema.tenant_type in [TenantType.PARENT, TenantType.SUBSIDIARY]
        assert isinstance(schema.metadata, dict)

    def test_tenant_create_parent_with_factory(self):
        """Test parent TenantCreate using factory."""
        schema = ParentTenantCreateSchemaFactory.build()
        
        assert schema.tenant_type == TenantType.PARENT
        assert schema.parent_tenant_id is None

    def test_tenant_create_subsidiary_with_factory(self):
        """Test subsidiary TenantCreate using factory."""
        schema = SubsidiaryTenantCreateSchemaFactory.build()
        
        assert schema.tenant_type == TenantType.SUBSIDIARY
        assert schema.parent_tenant_id is not None


class TestTenantUpdate:
    """Test cases for TenantUpdate schema."""

    def test_tenant_update_all_fields_none(self):
        """Test TenantUpdate with all optional fields as None."""
        schema = TenantUpdate()
        
        assert schema.name is None
        assert schema.metadata is None

    def test_tenant_update_name_only(self):
        """Test TenantUpdate with only name."""
        schema = TenantUpdate(name="Updated Bank Name")
        
        assert schema.name == "Updated Bank Name"
        assert schema.metadata is None

    def test_tenant_update_metadata_only(self):
        """Test TenantUpdate with only metadata."""
        metadata = {"status": "updated", "last_modified": "2025-08-13"}
        schema = TenantUpdate(metadata=metadata)
        
        assert schema.name is None
        assert schema.metadata == metadata

    def test_tenant_update_both_fields(self):
        """Test TenantUpdate with both name and metadata."""
        metadata = {"status": "active", "updated_by": "admin"}
        schema = TenantUpdate(
            name="New Bank Name",
            metadata=metadata,
        )
        
        assert schema.name == "New Bank Name"
        assert schema.metadata == metadata

    def test_tenant_update_name_validation_valid(self):
        """Test TenantUpdate name validation with valid names."""
        valid_names = [
            "Updated Bank",
            "A",  # Minimum length
            "A" * 200,  # Maximum length
            "Bank Name with Numbers 123",
        ]
        
        for name in valid_names:
            schema = TenantUpdate(name=name)
            assert schema.name == name

    def test_tenant_update_name_validation_empty_fails(self):
        """Test TenantUpdate name validation with empty string."""
        with pytest.raises(ValidationError) as exc_info:
            TenantUpdate(name="")
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("cannot be empty" in str(error.get('msg', '')) for error in errors)

    def test_tenant_update_name_validation_whitespace_fails(self):
        """Test TenantUpdate name validation with whitespace-only string."""
        with pytest.raises(ValidationError) as exc_info:
            TenantUpdate(name="   ")
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("cannot be empty" in str(error.get('msg', '')) for error in errors)

    def test_tenant_update_name_validation_too_long_fails(self):
        """Test TenantUpdate name validation with too long string."""
        with pytest.raises(ValidationError) as exc_info:
            TenantUpdate(name="A" * 201)
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("200 characters" in str(error.get('msg', '')) for error in errors)

    def test_tenant_update_name_trimming(self):
        """Test TenantUpdate name trimming."""
        schema = TenantUpdate(name="  Updated Bank Name  ")
        
        assert schema.name == "Updated Bank Name"

    def test_tenant_update_metadata_validation_valid_dict(self):
        """Test TenantUpdate metadata validation with valid dictionary."""
        metadata = {
            "status": "updated",
            "last_audit": "2025-08-13T10:00:00Z",
            "compliance": {
                "kyc_status": "verified",
                "risk_rating": "low"
            },
            "employee_count": 55000,
            "new_licenses": ["derivatives_trading"]
        }
        
        schema = TenantUpdate(metadata=metadata)
        assert schema.metadata == metadata

    def test_tenant_update_metadata_validation_invalid_type_fails(self):
        """Test TenantUpdate metadata validation with invalid type."""
        with pytest.raises(ValidationError) as exc_info:
            TenantUpdate(metadata="not a dict")
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("must be a dictionary" in str(error.get('msg', '')) for error in errors)

    def test_tenant_update_json_schema_examples(self):
        """Test TenantUpdate JSON schema examples."""
        schema_dict = TenantUpdate.model_json_schema()
        
        assert "examples" in schema_dict
        examples = schema_dict["examples"]
        assert len(examples) >= 1
        
        example = examples[0]
        assert "name" in example
        assert "metadata" in example

    def test_tenant_update_with_factory(self):
        """Test TenantUpdate using factory."""
        schema = TenantUpdateSchemaFactory.build()
        
        assert isinstance(schema.name, str)
        assert len(schema.name) > 0
        assert "Updated" in schema.name
        assert isinstance(schema.metadata, dict)


class TestTenantResponse:
    """Test cases for TenantResponse schema."""

    def test_tenant_response_all_fields(self):
        """Test TenantResponse with all fields."""
        tenant_id = uuid4()
        parent_id = uuid4()
        created_time = datetime.now(timezone.utc)
        updated_time = datetime.now(timezone.utc)
        metadata = generate_valid_metadata()
        
        schema = TenantResponse(
            tenant_id=tenant_id,
            name="Response Bank",
            parent_tenant_id=parent_id,
            tenant_type=TenantType.SUBSIDIARY,
            tenant_metadata=metadata,
            created_at=created_time,
            updated_at=updated_time,
        )
        
        assert schema.tenant_id == tenant_id
        assert schema.name == "Response Bank"
        assert schema.parent_tenant_id == parent_id
        assert schema.tenant_type == TenantType.SUBSIDIARY
        assert schema.metadata == metadata
        assert schema.created_at == created_time
        assert schema.updated_at == updated_time

    def test_tenant_response_parent_tenant(self):
        """Test TenantResponse for parent tenant."""
        schema = TenantResponse(
            tenant_id=uuid4(),
            name="Parent Bank",
            parent_tenant_id=None,
            tenant_type=TenantType.PARENT,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        assert schema.tenant_type == TenantType.PARENT
        assert schema.parent_tenant_id is None

    def test_tenant_response_from_attributes_config(self):
        """Test TenantResponse from_attributes configuration."""
        config = TenantResponse.model_config
        assert config.get("from_attributes") is True

    def test_tenant_response_json_schema_examples(self):
        """Test TenantResponse JSON schema examples."""
        schema_dict = TenantResponse.model_json_schema()
        
        assert "examples" in schema_dict
        examples = schema_dict["examples"]
        assert len(examples) >= 1
        
        example = examples[0]
        required_fields = [
            "tenant_id", "name", "tenant_type", 
            "created_at", "updated_at", "metadata"
        ]
        
        for field in required_fields:
            assert field in example

    def test_tenant_response_with_factory(self):
        """Test TenantResponse using factory."""
        schema = TenantResponseSchemaFactory.build()
        
        assert isinstance(schema.tenant_id, UUID)
        assert isinstance(schema.name, str)
        assert schema.tenant_type in [TenantType.PARENT, TenantType.SUBSIDIARY]
        assert isinstance(schema.created_at, datetime)
        assert isinstance(schema.updated_at, datetime)
        assert isinstance(schema.metadata, dict)

    def test_tenant_response_serialization(self):
        """Test TenantResponse serialization to JSON."""
        schema = TenantResponseSchemaFactory.build()
        
        # Should serialize without errors
        json_str = schema.model_dump_json()
        assert isinstance(json_str, str)
        
        # Should deserialize back
        data = json.loads(json_str)
        assert isinstance(data, dict)
        assert "tenant_id" in data
        assert "name" in data


class TestTenantListItem:
    """Test cases for TenantListItem schema."""

    def test_tenant_list_item_all_fields(self):
        """Test TenantListItem with all fields."""
        tenant_id = uuid4()
        created_time = datetime.now(timezone.utc)
        
        schema = TenantListItem(
            tenant_id=tenant_id,
            name="List Item Bank",
            tenant_type=TenantType.PARENT,
            created_at=created_time,
        )
        
        assert schema.tenant_id == tenant_id
        assert schema.name == "List Item Bank"
        assert schema.tenant_type == TenantType.PARENT
        assert schema.created_at == created_time

    def test_tenant_list_item_minimal_fields(self):
        """Test TenantListItem has minimal fields for listing."""
        schema_dict = TenantListItem.model_json_schema()
        properties = schema_dict.get("properties", {})
        
        # Should only have essential fields for listing
        expected_fields = {"tenant_id", "name", "tenant_type", "created_at"}
        actual_fields = set(properties.keys())
        
        assert expected_fields == actual_fields

    def test_tenant_list_item_from_attributes_config(self):
        """Test TenantListItem from_attributes configuration."""
        config = TenantListItem.model_config
        assert config.get("from_attributes") is True

    def test_tenant_list_item_with_factory(self):
        """Test TenantListItem using factory."""
        schema = TenantListItemSchemaFactory.build()
        
        assert isinstance(schema.tenant_id, UUID)
        assert isinstance(schema.name, str)
        assert schema.tenant_type in [TenantType.PARENT, TenantType.SUBSIDIARY]
        assert isinstance(schema.created_at, datetime)


class TestTenantListResponse:
    """Test cases for TenantListResponse schema."""

    def test_tenant_list_response_all_fields(self):
        """Test TenantListResponse with all fields."""
        tenants = [
            TenantListItemSchemaFactory.build(),
            TenantListItemSchemaFactory.build(),
        ]
        
        schema = TenantListResponse(
            tenants=tenants,
            total_count=10,
            limit=5,
            offset=0,
        )
        
        assert len(schema.tenants) == 2
        assert schema.total_count == 10
        assert schema.limit == 5
        assert schema.offset == 0

    def test_tenant_list_response_empty_list(self):
        """Test TenantListResponse with empty tenant list."""
        schema = TenantListResponse(
            tenants=[],
            total_count=0,
            limit=100,
            offset=0,
        )
        
        assert schema.tenants == []
        assert schema.total_count == 0

    def test_tenant_list_response_validation_negative_total_count_fails(self):
        """Test TenantListResponse validation with negative total_count."""
        with pytest.raises(ValidationError) as exc_info:
            TenantListResponse(
                tenants=[],
                total_count=-1,  # Invalid: negative count
                limit=100,
                offset=0,
            )
        
        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_tenant_list_response_validation_zero_limit_fails(self):
        """Test TenantListResponse validation with zero limit."""
        with pytest.raises(ValidationError) as exc_info:
            TenantListResponse(
                tenants=[],
                total_count=0,
                limit=0,  # Invalid: zero limit
                offset=0,
            )
        
        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_tenant_list_response_validation_too_large_limit_fails(self):
        """Test TenantListResponse validation with too large limit."""
        with pytest.raises(ValidationError) as exc_info:
            TenantListResponse(
                tenants=[],
                total_count=0,
                limit=1001,  # Invalid: over 1000 limit
                offset=0,
            )
        
        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_tenant_list_response_validation_negative_offset_fails(self):
        """Test TenantListResponse validation with negative offset."""
        with pytest.raises(ValidationError) as exc_info:
            TenantListResponse(
                tenants=[],
                total_count=0,
                limit=100,
                offset=-1,  # Invalid: negative offset
            )
        
        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_tenant_list_response_json_schema_examples(self):
        """Test TenantListResponse JSON schema examples."""
        schema_dict = TenantListResponse.model_json_schema()
        
        assert "examples" in schema_dict
        examples = schema_dict["examples"]
        assert len(examples) >= 1
        
        example = examples[0]
        required_fields = ["tenants", "total_count", "limit", "offset"]
        
        for field in required_fields:
            assert field in example

    def test_tenant_list_response_pagination_scenarios(self):
        """Test TenantListResponse with various pagination scenarios."""
        # First page
        first_page = TenantListResponse(
            tenants=[TenantListItemSchemaFactory.build()],
            total_count=100,
            limit=10,
            offset=0,
        )
        assert first_page.limit == 10
        assert first_page.offset == 0
        
        # Middle page
        middle_page = TenantListResponse(
            tenants=[TenantListItemSchemaFactory.build()],
            total_count=100,
            limit=10,
            offset=50,
        )
        assert middle_page.offset == 50
        
        # Last page (partial)
        last_page = TenantListResponse(
            tenants=[TenantListItemSchemaFactory.build()],
            total_count=95,
            limit=10,
            offset=90,
        )
        assert last_page.total_count == 95
        assert last_page.offset == 90


class TestTenantDeleteResponse:
    """Test cases for TenantDeleteResponse schema."""

    def test_tenant_delete_response_all_fields(self):
        """Test TenantDeleteResponse with all fields."""
        tenant_id = uuid4()
        
        schema = TenantDeleteResponse(
            message="Tenant successfully deleted",
            tenant_id=tenant_id,
        )
        
        assert schema.message == "Tenant successfully deleted"
        assert schema.tenant_id == tenant_id

    def test_tenant_delete_response_custom_message(self):
        """Test TenantDeleteResponse with custom message."""
        schema = TenantDeleteResponse(
            message="Custom deletion message",
            tenant_id=uuid4(),
        )
        
        assert schema.message == "Custom deletion message"

    def test_tenant_delete_response_json_schema_examples(self):
        """Test TenantDeleteResponse JSON schema examples."""
        schema_dict = TenantDeleteResponse.model_json_schema()
        
        assert "examples" in schema_dict
        examples = schema_dict["examples"]
        assert len(examples) >= 1
        
        example = examples[0]
        assert "message" in example
        assert "tenant_id" in example
        assert "successfully deleted" in example["message"]

    def test_tenant_delete_response_serialization(self):
        """Test TenantDeleteResponse serialization."""
        schema = TenantDeleteResponse(
            message="Tenant deleted successfully",
            tenant_id=uuid4(),
        )
        
        # Should serialize without errors
        json_str = schema.model_dump_json()
        assert isinstance(json_str, str)
        
        # Should deserialize back
        data = json.loads(json_str)
        assert data["message"] == "Tenant deleted successfully"
        assert "tenant_id" in data


class TestSchemaInteroperability:
    """Test cases for schema interoperability and edge cases."""

    def test_schema_type_annotations(self):
        """Test that all schemas have proper type annotations."""
        schemas = [
            TenantBase, TenantCreate, TenantUpdate,
            TenantResponse, TenantListItem, TenantListResponse,
            TenantDeleteResponse
        ]
        
        for schema_class in schemas:
            assert hasattr(schema_class, '__annotations__')
            assert len(schema_class.__annotations__) > 0

    def test_schema_json_serialization_round_trip(self):
        """Test round-trip JSON serialization for all schemas."""
        # TenantCreate
        create_schema = TenantCreateSchemaFactory.build()
        create_json = create_schema.model_dump_json()
        recreated = TenantCreate.model_validate_json(create_json)
        assert recreated.name == create_schema.name
        
        # TenantResponse
        response_schema = TenantResponseSchemaFactory.build()
        response_json = response_schema.model_dump_json()
        recreated_response = TenantResponse.model_validate_json(response_json)
        assert recreated_response.tenant_id == response_schema.tenant_id

    def test_schema_validation_comprehensive(self):
        """Test comprehensive validation scenarios."""
        # Valid subsidiary creation
        parent_id = uuid4()
        valid_subsidiary = TenantCreate(
            name="HSBC Hong Kong",
            tenant_type=TenantType.SUBSIDIARY,
            parent_tenant_id=parent_id,
            tenant_metadata={
                "country": "Hong Kong",
                "business_unit": "retail_banking",
                "local_currency": "HKD",
                "employee_count": 8000,
                "licenses": ["hong_kong_banking_license"],
                "parent_company": "HSBC Holdings"
            }
        )
        
        assert valid_subsidiary.tenant_type == TenantType.SUBSIDIARY
        assert valid_subsidiary.parent_tenant_id == parent_id
        assert "hong_kong_banking_license" in valid_subsidiary.metadata["licenses"]

    def test_schema_field_descriptions(self):
        """Test that schemas have proper field descriptions."""
        # Check TenantCreate schema
        schema_dict = TenantCreate.model_json_schema()
        properties = schema_dict.get("properties", {})
        
        # Key fields should have descriptions
        assert "description" in properties.get("name", {})
        assert "description" in properties.get("tenant_type", {})
        assert "description" in properties.get("parent_tenant_id", {})

    def test_fintech_realistic_validation_scenarios(self):
        """Test realistic fintech validation scenarios."""
        # Large financial institution parent
        parent_data = {
            "name": "JPMorgan Chase & Co.",
            "tenant_type": TenantType.PARENT,
            "tenant_metadata": {
                "country": "United States",
                "business_unit": "universal_banking",
                "status": "active",
                "founded_year": 1799,
                "employee_count": 271025,
                "market_cap": "600B USD",
                "regulatory_licenses": [
                    "national_banking_charter",
                    "fdic_insurance",
                    "federal_reserve_membership",
                    "occ_supervision"
                ],
                "primary_currencies": ["USD", "EUR", "GBP", "JPY"],
                "headquarters": {
                    "address": "383 Madison Avenue",
                    "city": "New York",
                    "state": "NY",
                    "postal_code": "10017"
                }
            }
        }
        
        parent_schema = TenantCreate(**parent_data)
        assert parent_schema.tenant_type == TenantType.PARENT
        assert parent_schema.parent_tenant_id is None
        assert parent_schema.metadata["employee_count"] == 271025
        
        # International subsidiary
        subsidiary_data = {
            "name": "J.P. Morgan Securities plc",
            "parent_tenant_id": uuid4(),
            "tenant_type": TenantType.SUBSIDIARY,
            "tenant_metadata": {
                "country": "United Kingdom",
                "business_unit": "investment_banking",
                "region": "Europe",
                "status": "active",
                "local_currency": "GBP",
                "employee_count": 12000,
                "local_licenses": [
                    "fca_authorization",
                    "pra_banking_license",
                    "mifid_ii_compliance"
                ],
                "office_locations": [
                    "London", "Edinburgh", "Belfast"
                ],
                "parent_company": "JPMorgan Chase & Co."
            }
        }
        
        subsidiary_schema = TenantCreate(**subsidiary_data)
        assert subsidiary_schema.tenant_type == TenantType.SUBSIDIARY
        assert subsidiary_schema.parent_tenant_id is not None
        assert "fca_authorization" in subsidiary_schema.metadata["local_licenses"]