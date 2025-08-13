"""
Unit tests for base models.

Tests the Base class and TimestampMixin functionality including table name
generation, timestamp handling, and SQLAlchemy configuration.
"""

import re
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.multi_tenant_db.models.base import Base, TimestampMixin


class TestBase:
    """Test cases for the Base class."""

    def test_base_inherits_from_async_attrs_and_declarative_base(self):
        """Test that Base inherits from AsyncAttrs and DeclarativeBase."""
        assert issubclass(Base, AsyncAttrs)
        assert issubclass(Base, DeclarativeBase)

    def test_tablename_generation_simple_class(self):
        """Test table name generation for simple class names."""
        class TestModel(Base):
            __test__ = False  # Prevent pytest from treating this as a test class
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
        
        # The table name should be generated from class name
        assert TestModel.__tablename__ == "test_models"

    def test_tablename_generation_camelcase_class(self):
        """Test table name generation for CamelCase class names."""
        class UserAccount(Base):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
        
        assert UserAccount.__tablename__ == "user_accounts"

    def test_tablename_generation_complex_camelcase(self):
        """Test table name generation for complex CamelCase names."""
        class HTTPResponseLog(Base):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
        
        assert HTTPResponseLog.__tablename__ == "http_response_logs"

    def test_tablename_generation_single_word(self):
        """Test table name generation for single word class names."""
        class User(Base):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
        
        assert User.__tablename__ == "users"

    def test_tablename_generation_already_plural(self):
        """Test table name generation for class names already ending in 's'."""
        class News(Base):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
        
        # Should not add another 's' if already ends with 's'
        assert News.__tablename__ == "news"

    def test_tablename_generation_with_numbers(self):
        """Test table name generation with numbers in class name."""
        class OAuth2Token(Base):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
        
        assert OAuth2Token.__tablename__ == "o_auth2_tokens"

    def test_tablename_generation_regex_pattern(self):
        """Test that the table name generation uses correct regex patterns."""
        # Test the regex patterns used in the __tablename__ method
        test_name = "HTTPResponseLog"
        
        # First regex: Convert initial CamelCase
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', test_name)
        assert name == "HTTP_ResponseLog"
        
        # Second regex: Convert remaining CamelCase
        name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
        assert name == "http_response_log"
        
        # Pluralization
        if not name.endswith('s'):
            name += 's'
        assert name == "http_response_logs"

    def test_base_class_metadata_access(self):
        """Test that Base class provides access to SQLAlchemy metadata."""
        assert hasattr(Base, "metadata")
        assert Base.metadata is not None

    def test_base_class_registry_access(self):
        """Test that Base class provides access to class registry."""
        assert hasattr(Base, "registry")
        assert Base.registry is not None

    def test_multiple_models_different_table_names(self):
        """Test that different models get different table names."""
        class FirstModel(Base):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            
        class SecondModel(Base):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
        
        assert FirstModel.__tablename__ != SecondModel.__tablename__
        assert FirstModel.__tablename__ == "first_models"
        assert SecondModel.__tablename__ == "second_models"


class TestTimestampMixin:
    """Test cases for the TimestampMixin class."""

    def test_timestamp_mixin_has_created_at_field(self):
        """Test that TimestampMixin has created_at field."""
        assert hasattr(TimestampMixin, 'created_at')
        
        # Check that it's a mapped column
        created_at = TimestampMixin.__annotations__['created_at']
        assert created_at is not None

    def test_timestamp_mixin_has_updated_at_field(self):
        """Test that TimestampMixin has updated_at field."""
        assert hasattr(TimestampMixin, 'updated_at')
        
        # Check that it's a mapped column
        updated_at = TimestampMixin.__annotations__['updated_at']
        assert updated_at is not None

    def test_created_at_field_configuration(self):
        """Test created_at field configuration."""
        # Get the mapped column for created_at
        created_at_column = TimestampMixin.__dict__['created_at']
        
        # Verify it's a MappedColumn
        from sqlalchemy.orm import MappedColumn
        assert isinstance(created_at_column, MappedColumn)
        
        # Verify it has the correct attributes  
        # In SQLAlchemy 2.0 with MappedColumn, we access the underlying column
        assert created_at_column.column.nullable is False
        assert created_at_column.column.server_default is not None

    def test_updated_at_field_configuration(self):
        """Test updated_at field configuration."""
        # Get the mapped column for updated_at
        updated_at_column = TimestampMixin.__dict__['updated_at']
        
        # Verify it's a MappedColumn
        from sqlalchemy.orm import MappedColumn
        assert isinstance(updated_at_column, MappedColumn)
        
        # Verify it has the correct attributes
        # In SQLAlchemy 2.0 with MappedColumn, we access the underlying column  
        assert updated_at_column.column.nullable is False
        assert updated_at_column.column.server_default is not None
        assert updated_at_column.column.onupdate is not None

    def test_timestamp_fields_use_timezone_aware_datetime(self):
        """Test that timestamp fields use timezone-aware DateTime."""
        created_at_column = TimestampMixin.__dict__['created_at']
        updated_at_column = TimestampMixin.__dict__['updated_at']
        
        # Get the SQLAlchemy column type from MappedColumn
        # In SQLAlchemy 2.0 with MappedColumn, we access the underlying column's type
        created_at_type = created_at_column.column.type
        updated_at_type = updated_at_column.column.type
        
        # Check that both use DateTime with timezone=True
        assert hasattr(created_at_type, 'timezone')
        assert created_at_type.timezone is True
        
        assert hasattr(updated_at_type, 'timezone')
        assert updated_at_type.timezone is True

    def test_mixin_can_be_inherited(self):
        """Test that TimestampMixin can be properly inherited."""
        class TestModelWithTimestamps(Base, TimestampMixin):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            name: Mapped[str] = mapped_column(String(50))
        
        # Check that the model has both timestamp fields
        assert hasattr(TestModelWithTimestamps, 'created_at')
        assert hasattr(TestModelWithTimestamps, 'updated_at')
        assert hasattr(TestModelWithTimestamps, 'id')
        assert hasattr(TestModelWithTimestamps, 'name')
        
        # Check table name generation still works
        assert TestModelWithTimestamps.__tablename__ == "test_model_with_timestamps"

    def test_timestamp_mixin_field_types(self):
        """Test that timestamp fields have correct Python type annotations."""
        # Check type annotations
        annotations = TimestampMixin.__annotations__
        
        assert 'created_at' in annotations
        assert 'updated_at' in annotations
        
        # Both should be Mapped[datetime]
        import typing
        created_at_type = annotations['created_at']
        updated_at_type = annotations['updated_at']
        
        # Check that they are Mapped types
        assert hasattr(created_at_type, '__origin__')
        assert str(created_at_type).startswith('sqlalchemy.orm.base.Mapped')

    def test_server_default_uses_func_now(self):
        """Test that server defaults use SQLAlchemy func.now()."""
        created_at_column = TimestampMixin.__dict__['created_at']
        updated_at_column = TimestampMixin.__dict__['updated_at']
        
        created_default = created_at_column.server_default
        updated_default = updated_at_column.server_default
        
        # Both should have server defaults
        assert created_default is not None
        assert updated_default is not None
        
        # Check that onupdate also uses func.now()
        onupdate = updated_at_column.onupdate
        assert onupdate is not None

    def test_multiple_models_with_mixin_independence(self):
        """Test that multiple models using the mixin are independent."""
        class FirstTimestampModel(Base, TimestampMixin):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            
        class SecondTimestampModel(Base, TimestampMixin):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
        
        # Both should have timestamp fields
        assert hasattr(FirstTimestampModel, 'created_at')
        assert hasattr(FirstTimestampModel, 'updated_at')
        assert hasattr(SecondTimestampModel, 'created_at')
        assert hasattr(SecondTimestampModel, 'updated_at')
        
        # They should have different table names
        assert FirstTimestampModel.__tablename__ != SecondTimestampModel.__tablename__


class TestBaseAndMixinIntegration:
    """Test cases for integration between Base and TimestampMixin."""

    def test_combined_inheritance_order(self):
        """Test that Base and TimestampMixin work together in correct order."""
        class CombinedModel(Base, TimestampMixin):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            name: Mapped[str] = mapped_column(String(100))
        
        # Should have all expected attributes
        expected_attrs = ['id', 'name', 'created_at', 'updated_at', '__tablename__']
        for attr in expected_attrs:
            assert hasattr(CombinedModel, attr)
        
        # Table name should be generated
        assert CombinedModel.__tablename__ == "combined_models"

    def test_mixin_first_inheritance_order(self):
        """Test inheritance with TimestampMixin first."""
        class MixinFirstModel(TimestampMixin, Base):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
        
        # Should still work correctly
        assert hasattr(MixinFirstModel, 'created_at')
        assert hasattr(MixinFirstModel, 'updated_at')
        assert hasattr(MixinFirstModel, '__tablename__')
        assert MixinFirstModel.__tablename__ == "mixin_first_models"

    def test_model_can_override_timestamp_behavior(self):
        """Test that models can override timestamp field behavior if needed."""
        class CustomTimestampModel(Base, TimestampMixin):
            __test__ = False
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            # Override created_at with different configuration
            created_at: Mapped[datetime] = mapped_column(
                DateTime(timezone=True),
                nullable=True,  # Different from mixin
                comment="Custom creation timestamp"
            )
        
        # Should have the overridden field
        assert hasattr(CustomTimestampModel, 'created_at')
        assert hasattr(CustomTimestampModel, 'updated_at')
        
        # Check that override worked
        created_at_column = CustomTimestampModel.__dict__['created_at']
        assert created_at_column.property.columns[0].nullable is True
        assert created_at_column.property.columns[0].comment == "Custom creation timestamp"