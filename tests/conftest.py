"""
Pytest configuration and shared fixtures for unit and integration tests.

Provides comprehensive test fixtures for database sessions, tenant data,
and mocking utilities for the multi-tenant database application.
"""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.multi_tenant_db.core.config import Settings, get_settings
from src.multi_tenant_db.models.tenant import Tenant, TenantType
from src.multi_tenant_db.schemas.tenant import (
    TenantCreate,
    TenantResponse,
    TenantUpdate,
)


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
        jwt_secret_key="test_secret_key_for_testing_only",
        environment="testing",
        debug=True,
        require_tenant_header=False,
        tenant_header_name="X-Tenant-ID",
        tenant_cookie_name="tenant_id",
        default_tenant_id="default-tenant-id",
        db_pool_size=5,
        db_max_overflow=10,
        db_pool_timeout=30,
    )


@pytest.fixture
def app(mock_settings: Settings) -> FastAPI:
    """Create FastAPI app instance for testing."""
    from src.multi_tenant_db.main import create_application
    
    # Override settings for testing
    def get_test_settings():
        return mock_settings
    
    app = create_application()
    app.dependency_overrides[get_settings] = get_test_settings
    return app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient]:
    """Create FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Create async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_db_session() -> Mock:
    """Create mock database session for unit tests."""
    session = AsyncMock(spec=AsyncSession)
    session.add = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock()
    session.delete = AsyncMock()
    return session


# Tenant Test Data Fixtures

@pytest.fixture
def parent_tenant_id() -> UUID:
    """Generate consistent parent tenant ID for tests."""
    return UUID("550e8400-e29b-41d4-a716-446655440000")


@pytest.fixture
def subsidiary_tenant_id() -> UUID:
    """Generate consistent subsidiary tenant ID for tests."""
    return UUID("123e4567-e89b-12d3-a456-426614174000")


@pytest.fixture
def parent_tenant_data(parent_tenant_id: UUID) -> dict:
    """Create parent tenant data for testing."""
    return {
        "tenant_id": parent_tenant_id,
        "name": "HSBC Bank",
        "parent_tenant_id": None,
        "tenant_type": TenantType.PARENT,
        "tenant_metadata": {
            "country": "United Kingdom",
            "headquarters": "London",
            "business_type": "multinational_bank"
        },
        "created_at": datetime(2025, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
    }


@pytest.fixture
def subsidiary_tenant_data(subsidiary_tenant_id: UUID, parent_tenant_id: UUID) -> dict:
    """Create subsidiary tenant data for testing."""
    return {
        "tenant_id": subsidiary_tenant_id,
        "name": "HSBC Hong Kong",
        "parent_tenant_id": parent_tenant_id,
        "tenant_type": TenantType.SUBSIDIARY,
        "tenant_metadata": {
            "country": "Hong Kong",
            "region": "Asia Pacific",
            "business_unit": "retail_banking"
        },
        "created_at": datetime(2025, 8, 1, 11, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 8, 1, 11, 0, 0, tzinfo=timezone.utc),
    }


@pytest.fixture
def parent_tenant_model(parent_tenant_data: dict) -> Tenant:
    """Create parent tenant model instance for testing."""
    return Tenant(**parent_tenant_data)


@pytest.fixture
def subsidiary_tenant_model(subsidiary_tenant_data: dict) -> Tenant:
    """Create subsidiary tenant model instance for testing."""
    return Tenant(**subsidiary_tenant_data)


# Tenant Schema Fixtures

@pytest.fixture
def tenant_create_parent() -> TenantCreate:
    """Create TenantCreate schema for parent tenant."""
    return TenantCreate(
        name="JP Morgan Chase",
        tenant_type=TenantType.PARENT,
        parent_tenant_id=None,
        metadata={
            "country": "United States",
            "headquarters": "New York",
            "business_type": "investment_bank"
        }
    )


@pytest.fixture
def tenant_create_subsidiary(parent_tenant_id: UUID) -> TenantCreate:
    """Create TenantCreate schema for subsidiary tenant."""
    return TenantCreate(
        name="JP Morgan Singapore",
        tenant_type=TenantType.SUBSIDIARY,
        parent_tenant_id=parent_tenant_id,
        metadata={
            "country": "Singapore",
            "region": "Asia Pacific",
            "business_unit": "investment_banking"
        }
    )


@pytest.fixture
def tenant_update() -> TenantUpdate:
    """Create TenantUpdate schema for testing."""
    return TenantUpdate(
        name="HSBC Hong Kong Limited",
        metadata={
            "country": "Hong Kong",
            "region": "Asia Pacific",
            "business_unit": "retail_banking",
            "status": "active"
        }
    )


@pytest.fixture
def tenant_response(subsidiary_tenant_data: dict) -> TenantResponse:
    """Create TenantResponse schema for testing."""
    return TenantResponse(**subsidiary_tenant_data)


# Mock Response Fixtures

@pytest.fixture
def mock_execute_result() -> Mock:
    """Create mock SQLAlchemy execute result."""
    mock_result = Mock()
    mock_result.scalar = Mock()
    mock_result.scalar_one_or_none = Mock()
    mock_result.scalars = Mock()
    mock_result.fetchone = Mock()
    
    # Mock for scalars().all() chain
    mock_scalars = Mock()
    mock_scalars.all = Mock()
    mock_result.scalars.return_value = mock_scalars
    
    return mock_result


# Test Headers and Authentication

@pytest.fixture
def tenant_headers(parent_tenant_id: UUID) -> dict[str, str]:
    """Create headers with tenant ID for API testing."""
    return {
        "X-Tenant-ID": str(parent_tenant_id),
        "Content-Type": "application/json"
    }


@pytest.fixture
def subsidiary_headers(subsidiary_tenant_id: UUID) -> dict[str, str]:
    """Create headers with subsidiary tenant ID for API testing."""
    return {
        "X-Tenant-ID": str(subsidiary_tenant_id),
        "Content-Type": "application/json"
    }


# Utility Fixtures

@pytest.fixture
def random_uuid() -> UUID:
    """Generate random UUID for testing."""
    return uuid4()


@pytest.fixture
def mock_datetime() -> datetime:
    """Create consistent datetime for testing."""
    return datetime(2025, 8, 13, 12, 0, 0, tzinfo=timezone.utc)


# Database Mock Fixtures for Different Scenarios

@pytest.fixture
def mock_integrity_error():
    """Create mock SQLAlchemy IntegrityError."""
    from sqlalchemy.exc import IntegrityError
    return IntegrityError("Mock integrity error", None, None)


@pytest.fixture
def mock_sqlalchemy_error():
    """Create mock SQLAlchemy general error."""
    from sqlalchemy.exc import SQLAlchemyError
    return SQLAlchemyError("Mock database error")


# Request Mock Fixtures

@pytest.fixture
def mock_request() -> Mock:
    """Create mock FastAPI request object."""
    request = Mock()
    request.headers = {}
    request.cookies = {}
    request.state = Mock()
    request.url = Mock()
    request.url.path = "/api/v1/test"
    request.method = "GET"
    return request


# Health Check Fixtures

@pytest.fixture
def mock_db_health_response() -> dict:
    """Create mock database health check response."""
    return {
        "status": "healthy",
        "timestamp": "2025-08-13T12:00:00Z",
        "database": {
            "status": "healthy",
            "test_value": 1,
            "server_time": "2025-08-13T12:00:00Z",
        },
    }


@pytest.fixture
def mock_tenant_model_health_response() -> dict:
    """Create mock tenant model health check response."""
    return {
        "status": "healthy",
        "timestamp": "2025-08-13T12:00:00Z",
        "component": "tenant_model",
        "response_time_ms": 15.5,
        "details": {
            "tenant_count": 5,
            "rls_enabled": True,
            "rls_functions_available": True,
            "crud_operations": "working"
        },
    }


# Pagination Fixtures

@pytest.fixture
def pagination_params() -> dict:
    """Create pagination parameters for testing."""
    return {
        "limit": 10,
        "offset": 0
    }


# Multiple Tenants Fixtures for List Operations

@pytest.fixture
def multiple_tenants_data(parent_tenant_id: UUID) -> list[dict]:
    """Create multiple tenant data for list operations testing."""
    tenants = []
    
    # Parent tenant
    tenants.append({
        "tenant_id": parent_tenant_id,
        "name": "HSBC Bank",
        "parent_tenant_id": None,
        "tenant_type": TenantType.PARENT,
        "tenant_metadata": {"country": "United Kingdom"},
        "created_at": datetime(2025, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
    })
    
    # Subsidiary tenants
    for i in range(3):
        tenants.append({
            "tenant_id": uuid4(),
            "name": f"HSBC Branch {i+1}",
            "parent_tenant_id": parent_tenant_id,
            "tenant_type": TenantType.SUBSIDIARY,
            "tenant_metadata": {"branch_number": i+1},
            "created_at": datetime(2025, 8, 1, 11, i, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 8, 1, 11, i, 0, tzinfo=timezone.utc),
        })
    
    return tenants


@pytest.fixture
def multiple_tenant_models(multiple_tenants_data: list[dict]) -> list[Tenant]:
    """Create multiple tenant model instances for testing."""
    return [Tenant(**data) for data in multiple_tenants_data]


# Error Scenario Fixtures

@pytest.fixture
def non_existent_tenant_id() -> UUID:
    """Generate non-existent tenant ID for error testing."""
    return UUID("00000000-0000-0000-0000-000000000000")


@pytest.fixture
def invalid_tenant_create() -> dict:
    """Create invalid tenant creation data for validation testing."""
    return {
        "name": "",  # Invalid: empty name
        "tenant_type": "invalid_type",  # Invalid: not in enum
        "parent_tenant_id": "not-a-uuid",  # Invalid: not a UUID
        "metadata": "not-a-dict"  # Invalid: not a dictionary
    }