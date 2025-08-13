"""
Unit tests for tenant model.

Tests the Tenant model including hierarchical relationships, validation,
properties, and database constraints.
"""

import enum
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID as PostgresUUID
from sqlalchemy.orm import Mapped

from src.multi_tenant_db.models.tenant import Tenant, TenantType
from src.multi_tenant_db.models.base import Base, TimestampMixin
from tests.factories import (
    TenantFactory, 
    ParentTenantFactory, 
    SubsidiaryTenantFactory,
    generate_valid_metadata,
    generate_realistic_parent_tenant_data,
    generate_realistic_subsidiary_tenant_data,
)


class TestTenantType:
    """Test cases for TenantType enumeration."""

    def test_tenant_type_is_string_enum(self):
        """Test that TenantType inherits from str and enum.Enum."""
        assert issubclass(TenantType, str)
        assert issubclass(TenantType, enum.Enum)

    def test_tenant_type_values(self):
        """Test TenantType enum values."""
        assert TenantType.PARENT.value == "parent"
        assert TenantType.SUBSIDIARY.value == "subsidiary"

    def test_tenant_type_string_conversion(self):
        """Test TenantType string conversion."""
        assert str(TenantType.PARENT) == "parent"
        assert str(TenantType.SUBSIDIARY) == "subsidiary"

    def test_tenant_type_equality_with_strings(self):
        """Test TenantType equality with string values."""
        assert TenantType.PARENT == "parent"
        assert TenantType.SUBSIDIARY == "subsidiary"

    def test_tenant_type_all_members(self):
        """Test that all expected TenantType members exist."""
        expected_members = {"PARENT", "SUBSIDIARY"}
        actual_members = {member.name for member in TenantType}
        assert actual_members == expected_members

    def test_tenant_type_iteration(self):
        """Test TenantType enumeration iteration."""
        types = list(TenantType)
        assert len(types) == 2
        assert TenantType.PARENT in types
        assert TenantType.SUBSIDIARY in types


class TestTenantModel:
    """Test cases for Tenant model class."""

    def test_tenant_inherits_from_base_and_timestamp_mixin(self):
        """Test Tenant inherits from Base and TimestampMixin."""
        assert issubclass(Tenant, Base)
        assert issubclass(Tenant, TimestampMixin)

    def test_tenant_table_name(self):
        """Test Tenant table name generation."""
        assert Tenant.__tablename__ == "tenants"

    def test_tenant_has_all_required_fields(self):
        """Test Tenant has all required fields."""
        expected_fields = {
            'tenant_id', 'name', 'parent_tenant_id', 'tenant_type',
            'tenant_metadata', 'created_at', 'updated_at'
        }
        
        # Get all annotated fields
        actual_fields = set(Tenant.__annotations__.keys())
        
        # Check that all expected fields are present
        assert expected_fields.issubset(actual_fields)

    def test_tenant_id_field_configuration(self):
        """Test tenant_id field configuration."""
        tenant_id_column = Tenant.__dict__['tenant_id']
        column_obj = tenant_id_column.property.columns[0]
        
        # Check primary key
        assert column_obj.primary_key is True
        
        # Check UUID type
        assert isinstance(column_obj.type, PostgresUUID)
        assert column_obj.type.as_uuid is True
        
        # Check default
        assert column_obj.default is not None
        
        # Check comment
        assert column_obj.comment == "Unique identifier for the tenant"

    def test_name_field_configuration(self):
        """Test name field configuration."""
        name_column = Tenant.__dict__['name']
        column_obj = name_column.property.columns[0]
        
        # Check type and length
        assert isinstance(column_obj.type, String)
        assert column_obj.type.length == 200
        
        # Check nullable
        assert column_obj.nullable is False
        
        # Check comment
        expected_comment = "Human-readable tenant name, unique within parent hierarchy"
        assert column_obj.comment == expected_comment

    def test_parent_tenant_id_field_configuration(self):
        """Test parent_tenant_id field configuration."""
        parent_id_column = Tenant.__dict__['parent_tenant_id']
        column_obj = parent_id_column.property.columns[0]
        
        # Check UUID type
        assert isinstance(column_obj.type, PostgresUUID)
        assert column_obj.type.as_uuid is True
        
        # Check nullable (should be True for parent tenants)
        assert column_obj.nullable is True
        
        # Check foreign key
        assert len(column_obj.foreign_keys) > 0
        fk = list(column_obj.foreign_keys)[0]
        assert str(fk.column) == "tenants.tenant_id"
        assert fk.ondelete == "RESTRICT"

    def test_tenant_type_field_configuration(self):
        """Test tenant_type field configuration."""
        tenant_type_column = Tenant.__dict__['tenant_type']
        column_obj = tenant_type_column.property.columns[0]
        
        # Check ENUM type
        assert isinstance(column_obj.type, ENUM)
        
        # Check not nullable
        assert column_obj.nullable is False
        
        # Check comment
        expected_comment = "Type of tenant: parent (top-level) or subsidiary"
        assert column_obj.comment == expected_comment

    def test_tenant_metadata_field_configuration(self):
        """Test tenant_metadata field configuration."""
        metadata_column = Tenant.__dict__['tenant_metadata']
        column_obj = metadata_column.property.columns[0]
        
        # Check JSONB type
        assert isinstance(column_obj.type, JSONB)
        
        # Check nullable
        assert column_obj.nullable is True
        
        # Check column name mapping
        assert column_obj.name == "metadata"
        
        # Check default
        assert column_obj.default is not None

    def test_tenant_relationships_configuration(self):
        """Test Tenant relationships configuration."""
        # Check parent relationship
        assert hasattr(Tenant, 'parent')
        parent_rel = Tenant.__dict__['parent']
        assert parent_rel.property.entity.class_ is Tenant
        
        # Check subsidiaries relationship  
        assert hasattr(Tenant, 'subsidiaries')
        subsidiaries_rel = Tenant.__dict__['subsidiaries']
        assert subsidiaries_rel.property.entity.class_ is Tenant

    def test_tenant_table_constraints(self):
        """Test Tenant table constraints."""
        table_args = Tenant.__table_args__
        
        # Convert to list for easier testing
        constraints = []
        indexes = []
        
        for arg in table_args:
            if isinstance(arg, CheckConstraint):
                constraints.append(arg)
            elif isinstance(arg, Index):
                indexes.append(arg)
        
        # Check that we have expected constraints
        constraint_names = [c.name for c in constraints]
        expected_constraints = [
            "ck_tenant_parent_logic",
            "ck_tenant_no_self_reference", 
            "ck_tenant_name_not_empty"
        ]
        
        for expected in expected_constraints:
            assert expected in constraint_names
        
        # Check that we have expected indexes
        index_names = [i.name for i in indexes]
        expected_indexes = [
            "uq_tenant_name_per_parent",
            "ix_tenant_parent_id",
            "ix_tenant_type",
            "ix_tenant_name_lower",
            "ix_tenant_metadata"
        ]
        
        for expected in expected_indexes:
            assert expected in index_names

    def test_unique_name_per_parent_index(self):
        """Test unique name per parent index configuration."""
        table_args = Tenant.__table_args__
        unique_index = None
        
        for arg in table_args:
            if isinstance(arg, Index) and arg.name == "uq_tenant_name_per_parent":
                unique_index = arg
                break
        
        assert unique_index is not None
        assert unique_index.unique is True
        
        # Check columns
        column_names = [col.name for col in unique_index.columns]
        assert "name" in column_names
        assert "parent_tenant_id" in column_names


class TestTenantModelMethods:
    """Test cases for Tenant model methods."""

    def test_tenant_repr(self):
        """Test Tenant __repr__ method."""
        tenant = TenantFactory.build()
        repr_str = repr(tenant)
        
        assert repr_str.startswith("<Tenant(")
        assert f"id={tenant.tenant_id}" in repr_str
        assert f"name='{tenant.name}'" in repr_str
        assert f"type={tenant.tenant_type})" in repr_str

    def test_tenant_str(self):
        """Test Tenant __str__ method."""
        tenant = TenantFactory.build()
        str_representation = str(tenant)
        
        expected = f"{tenant.name} ({tenant.tenant_type.value})"
        assert str_representation == expected

    def test_parent_tenant_str(self):
        """Test parent tenant string representation."""
        parent = ParentTenantFactory.build(name="HSBC Holdings")
        str_representation = str(parent)
        
        assert str_representation == "HSBC Holdings (parent)"

    def test_subsidiary_tenant_str(self):
        """Test subsidiary tenant string representation."""
        subsidiary = SubsidiaryTenantFactory.build(name="HSBC Hong Kong")
        str_representation = str(subsidiary)
        
        assert str_representation == "HSBC Hong Kong (subsidiary)"


class TestTenantModelProperties:
    """Test cases for Tenant model properties."""

    def test_is_parent_property_for_parent_tenant(self):
        """Test is_parent property returns True for parent tenants."""
        parent = ParentTenantFactory.build()
        assert parent.is_parent is True

    def test_is_parent_property_for_subsidiary_tenant(self):
        """Test is_parent property returns False for subsidiary tenants."""
        subsidiary = SubsidiaryTenantFactory.build()
        assert subsidiary.is_parent is False

    def test_is_subsidiary_property_for_subsidiary_tenant(self):
        """Test is_subsidiary property returns True for subsidiary tenants."""
        subsidiary = SubsidiaryTenantFactory.build()
        assert subsidiary.is_subsidiary is True

    def test_is_subsidiary_property_for_parent_tenant(self):
        """Test is_subsidiary property returns False for parent tenants."""
        parent = ParentTenantFactory.build()
        assert parent.is_subsidiary is False

    def test_has_subsidiaries_property_with_no_subsidiaries(self):
        """Test has_subsidiaries property when no subsidiaries exist."""
        tenant = TenantFactory.build(subsidiaries=[])
        assert tenant.has_subsidiaries is False

    def test_has_subsidiaries_property_with_subsidiaries(self):
        """Test has_subsidiaries property when subsidiaries exist."""
        subsidiary1 = SubsidiaryTenantFactory.build()
        subsidiary2 = SubsidiaryTenantFactory.build()
        parent = ParentTenantFactory.build(subsidiaries=[subsidiary1, subsidiary2])
        
        assert parent.has_subsidiaries is True

    def test_has_subsidiaries_property_with_one_subsidiary(self):
        """Test has_subsidiaries property with exactly one subsidiary."""
        subsidiary = SubsidiaryTenantFactory.build()
        parent = ParentTenantFactory.build(subsidiaries=[subsidiary])
        
        assert parent.has_subsidiaries is True

    def test_properties_are_read_only(self):
        """Test that properties don't have setters."""
        tenant = TenantFactory.build()
        
        # These should not have setters (will raise AttributeError if we try to set)
        with pytest.raises(AttributeError):
            tenant.is_parent = False
        
        with pytest.raises(AttributeError):
            tenant.is_subsidiary = True
            
        with pytest.raises(AttributeError):
            tenant.has_subsidiaries = True


class TestTenantModelValidation:
    """Test cases for Tenant model validation scenarios."""

    def test_parent_tenant_creation(self):
        """Test creating a valid parent tenant."""
        parent_data = generate_realistic_parent_tenant_data()
        
        # This would be validated at the database level
        # Here we just test the model structure
        parent = TenantFactory.build(**parent_data)
        
        assert parent.tenant_type == TenantType.PARENT
        assert parent.parent_tenant_id is None
        assert parent.is_parent is True
        assert parent.is_subsidiary is False

    def test_subsidiary_tenant_creation(self):
        """Test creating a valid subsidiary tenant."""
        parent_id = uuid4()
        subsidiary_data = generate_realistic_subsidiary_tenant_data(parent_id)
        
        subsidiary = SubsidiaryTenantFactory.build(**subsidiary_data)
        
        assert subsidiary.tenant_type == TenantType.SUBSIDIARY
        assert subsidiary.parent_tenant_id == parent_id
        assert subsidiary.is_parent is False
        assert subsidiary.is_subsidiary is True

    def test_tenant_with_valid_metadata(self):
        """Test tenant with valid metadata."""
        metadata = generate_valid_metadata()
        tenant = TenantFactory.build(tenant_metadata=metadata)
        
        assert tenant.tenant_metadata == metadata
        assert isinstance(tenant.tenant_metadata, dict)

    def test_tenant_with_empty_metadata(self):
        """Test tenant with empty metadata."""
        tenant = TenantFactory.build(tenant_metadata={})
        
        assert tenant.tenant_metadata == {}

    def test_tenant_with_none_metadata(self):
        """Test tenant with None metadata."""
        tenant = TenantFactory.build(tenant_metadata=None)
        
        assert tenant.tenant_metadata is None

    def test_tenant_with_complex_metadata(self):
        """Test tenant with complex nested metadata."""
        complex_metadata = {
            "business_info": {
                "industry": "financial_services",
                "sub_industry": "investment_banking",
                "founded_year": 1995,
                "employee_count": 50000
            },
            "compliance": {
                "kyc_status": "verified",
                "aml_status": "compliant",
                "licenses": [
                    "banking_license",
                    "investment_services",
                    "insurance_broker"
                ],
                "regulatory_bodies": ["FCA", "PRA", "SEC"]
            },
            "contact_info": {
                "headquarters": {
                    "address": "1 Canada Square, London",
                    "postal_code": "E14 5HQ",
                    "country": "United Kingdom"
                },
                "phone": "+44 20 7991 8888",
                "email": "info@hsbc.com"
            },
            "technical_info": {
                "api_endpoints": ["https://api.hsbc.com/v1"],
                "supported_currencies": ["USD", "EUR", "GBP", "HKD"],
                "integration_type": "REST_API"
            }
        }
        
        tenant = TenantFactory.build(tenant_metadata=complex_metadata)
        assert tenant.tenant_metadata == complex_metadata

    def test_tenant_hierarchy_relationships(self):
        """Test tenant hierarchy relationships."""
        parent = ParentTenantFactory.build()
        
        subsidiary1 = SubsidiaryTenantFactory.build(
            parent_tenant_id=parent.tenant_id,
            parent=parent
        )
        subsidiary2 = SubsidiaryTenantFactory.build(
            parent_tenant_id=parent.tenant_id,
            parent=parent
        )
        
        parent.subsidiaries = [subsidiary1, subsidiary2]
        
        # Test parent relationships
        assert parent.is_parent is True
        assert parent.has_subsidiaries is True
        assert len(parent.subsidiaries) == 2
        
        # Test subsidiary relationships
        assert subsidiary1.parent == parent
        assert subsidiary1.parent_tenant_id == parent.tenant_id
        assert subsidiary2.parent == parent
        assert subsidiary2.parent_tenant_id == parent.tenant_id

    def test_tenant_uuid_generation(self):
        """Test that tenant UUID is properly generated."""
        tenant = TenantFactory.build()
        
        assert isinstance(tenant.tenant_id, UUID)
        assert tenant.tenant_id is not None
        
        # Test that different tenants get different UUIDs
        tenant2 = TenantFactory.build()
        assert tenant.tenant_id != tenant2.tenant_id

    def test_tenant_name_validation_scenarios(self):
        """Test various tenant name scenarios."""
        # Valid names
        valid_names = [
            "HSBC Holdings",
            "JP Morgan Chase",
            "A" * 200,  # Maximum length
            "Name with spaces and numbers 123",
            "Special-Characters_Allowed.Name",
        ]
        
        for name in valid_names:
            tenant = TenantFactory.build(name=name)
            assert tenant.name == name

    def test_fintech_realistic_data_patterns(self):
        """Test realistic fintech data patterns."""
        # Test parent company
        parent = ParentTenantFactory.build(
            name="Goldman Sachs Group",
            tenant_metadata={
                "country": "United States",
                "business_unit": "investment_banking",
                "status": "active",
                "founded_year": 1869,
                "employee_count": 45000,
                "primary_currency": "USD",
                "regulatory_licenses": [
                    "banking_license",
                    "broker_dealer",
                    "investment_advisor"
                ],
                "market_cap": "150B USD"
            }
        )
        
        # Test subsidiary
        subsidiary = SubsidiaryTenantFactory.build(
            name="Goldman Sachs International",
            parent_tenant_id=parent.tenant_id,
            tenant_metadata={
                "country": "United Kingdom", 
                "business_unit": "investment_banking",
                "region": "Europe",
                "status": "active",
                "local_currency": "GBP",
                "employee_count": 8000,
                "local_licenses": ["UK_banking_license", "FCA_authorization"],
                "parent_company": "Goldman Sachs Group"
            }
        )
        
        assert parent.is_parent is True
        assert subsidiary.is_subsidiary is True
        assert subsidiary.parent_tenant_id == parent.tenant_id
        
        # Verify metadata structure
        assert "regulatory_licenses" in parent.tenant_metadata
        assert "local_licenses" in subsidiary.tenant_metadata
        assert parent.tenant_metadata["founded_year"] == 1869
        assert subsidiary.tenant_metadata["region"] == "Europe"


class TestTenantModelConstraints:
    """Test cases for database constraint validation (conceptual tests)."""

    def test_parent_logic_constraint_validation(self):
        """Test parent logic constraint scenarios."""
        # Valid parent tenant (no parent_id)
        parent = ParentTenantFactory.build(
            tenant_type=TenantType.PARENT,
            parent_tenant_id=None
        )
        # This would pass the constraint:
        # (tenant_type = 'parent' AND parent_tenant_id IS NULL)
        assert parent.tenant_type == TenantType.PARENT
        assert parent.parent_tenant_id is None
        
        # Valid subsidiary tenant (has parent_id)
        subsidiary = SubsidiaryTenantFactory.build(
            tenant_type=TenantType.SUBSIDIARY,
            parent_tenant_id=uuid4()
        )
        # This would pass the constraint:
        # (tenant_type = 'subsidiary' AND parent_tenant_id IS NOT NULL)
        assert subsidiary.tenant_type == TenantType.SUBSIDIARY
        assert subsidiary.parent_tenant_id is not None

    def test_self_reference_constraint_validation(self):
        """Test self-reference constraint scenarios."""
        tenant_id = uuid4()
        
        # Valid tenant (no self-reference)
        tenant = TenantFactory.build(
            tenant_id=tenant_id,
            parent_tenant_id=None  # Different from tenant_id
        )
        
        # This would pass the constraint: tenant_id != parent_tenant_id
        assert tenant.tenant_id != tenant.parent_tenant_id

    def test_name_not_empty_constraint_validation(self):
        """Test name not empty constraint scenarios."""
        # Valid names that would pass constraint
        valid_names = [
            "HSBC",  # Regular name
            "A",     # Single character
            " HSBC ",  # With spaces (trimmed would be "HSBC")
            "Name with spaces",
            "123 Numeric Name",
        ]
        
        for name in valid_names:
            tenant = TenantFactory.build(name=name)
            # This would pass: trim(name) != ''
            assert tenant.name.strip() != ""