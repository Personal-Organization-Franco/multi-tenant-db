"""
Test configuration management.

Basic tests to verify the configuration system works correctly.
"""

import os
from unittest.mock import patch

import pytest

from src.multi_tenant_db.core.config import Settings, get_settings


class TestSettings:
    """Test the Settings class."""

    def test_settings_with_env_vars(self):
        """Test settings with environment variables."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
                "JWT_SECRET_KEY": "test_secret",
                "ENVIRONMENT": "testing",
                "LOG_LEVEL": "DEBUG",
            },
        ):
            settings = Settings()
            assert settings.environment == "testing"
            assert settings.log_level == "DEBUG"
            assert "postgresql+asyncpg://test:test@localhost:5432/test" in str(
                settings.database_url
            )
            assert settings.jwt_secret_key == "test_secret"

    def test_cors_origins_string_parsing(self):
        """Test CORS origins can be parsed from comma-separated string."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
                "JWT_SECRET_KEY": "test_secret",
                "CORS_ORIGINS": "http://localhost:3000,http://localhost:8080,https://example.com",
            },
        ):
            settings = Settings()
            expected = [
                "http://localhost:3000",
                "http://localhost:8080",
                "https://example.com",
            ]
            assert settings.cors_origins == expected

    def test_invalid_environment_raises_error(self):
        """Test invalid environment value raises validation error."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
                "JWT_SECRET_KEY": "test_secret",
                "ENVIRONMENT": "invalid",
            },
        ):
            with pytest.raises(ValueError, match="Environment must be one of"):
                Settings()

    def test_invalid_log_level_raises_error(self):
        """Test invalid log level value raises validation error."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
                "JWT_SECRET_KEY": "test_secret",
                "LOG_LEVEL": "INVALID",
            },
        ):
            with pytest.raises(ValueError, match="Log level must be one of"):
                Settings()

    def test_is_development_property(self):
        """Test is_development property."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
                "JWT_SECRET_KEY": "test_secret",
                "ENVIRONMENT": "development",
            },
        ):
            settings = Settings()
            assert settings.is_development is True
            assert settings.is_production is False

    def test_is_production_property(self):
        """Test is_production property."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
                "JWT_SECRET_KEY": "test_secret",
                "ENVIRONMENT": "production",
            },
        ):
            settings = Settings()
            assert settings.is_production is True
            assert settings.is_development is False


class TestGetSettings:
    """Test the get_settings function."""

    def test_get_settings_returns_settings_instance(self):
        """Test get_settings returns a Settings instance."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
                "JWT_SECRET_KEY": "test_secret",
            },
        ):
            settings = get_settings()
            assert isinstance(settings, Settings)

    def test_get_settings_caches_instance(self):
        """Test get_settings caches the instance."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
                "JWT_SECRET_KEY": "test_secret",
            },
        ):
            settings1 = get_settings()
            settings2 = get_settings()
            assert settings1 is settings2  # Same instance due to caching
