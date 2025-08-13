"""
Integration test configuration and fixtures.

Provides database setup, cleanup, and realistic test data for integration tests.
Uses real database connections and transactions for end-to-end testing.
"""

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from src.multi_tenant_db.core.config import Settings
from src.multi_tenant_db.db.session import get_db_session
from src.multi_tenant_db.main import create_application
from src.multi_tenant_db.models.base import Base
from src.multi_tenant_db.models.tenant import Tenant, TenantType


@pytest.fixture(scope="session")
def integration_settings() -> Settings:
    """Create integration test database settings."""
    return Settings(
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5433/multi_tenant_test_db",
        jwt_secret_key="integration_test_secret_key_for_testing_only",
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


@pytest_asyncio.fixture(scope="function")
async def integration_engine(integration_settings: Settings):
    """Create async database engine for integration tests."""
    engine = create_async_engine(
        str(integration_settings.database_url),
        echo=integration_settings.debug,
        pool_size=integration_settings.db_pool_size,
        max_overflow=integration_settings.db_max_overflow,
        pool_timeout=integration_settings.db_pool_timeout,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def integration_db_session(integration_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create database session with transaction rollback for test isolation.
    Each test gets a fresh transaction that is rolled back after the test.
    """
    async with integration_engine.connect() as conn:
        trans = await conn.begin()
        
        # Create session bound to the transaction
        session = AsyncSession(bind=conn, expire_on_commit=False)
        
        yield session
        
        await session.close()
        await trans.rollback()


@pytest_asyncio.fixture
async def integration_app(integration_settings: Settings, integration_db_session: AsyncSession) -> FastAPI:
    """Create FastAPI app with integration test database session."""
    app = create_application()
    
    # Override settings and database session
    async def get_integration_settings():
        return integration_settings
    
    async def get_integration_db_session():
        return integration_db_session
    
    from src.multi_tenant_db.core.config import get_settings
    
    app.dependency_overrides[get_settings] = get_integration_settings
    app.dependency_overrides[get_db_session] = get_integration_db_session
    
    return app


@pytest_asyncio.fixture
async def integration_client(integration_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for integration testing."""
    async with AsyncClient(app=integration_app, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def db_connection(integration_engine) -> AsyncGenerator[AsyncConnection, None]:
    """Create direct database connection for RLS testing."""
    async with integration_engine.connect() as conn:
        yield conn


# Realistic Tenant Test Data Fixtures

@pytest.fixture
def hsbc_parent_id() -> UUID:
    """HSBC parent tenant ID for consistent testing."""
    return UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def barclays_parent_id() -> UUID:
    """Barclays parent tenant ID for isolation testing."""
    return UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def hsbc_hk_id() -> UUID:
    """HSBC Hong Kong subsidiary ID."""
    return UUID("11111111-1111-1111-1111-111111111112")


@pytest.fixture
def hsbc_london_id() -> UUID:
    """HSBC London subsidiary ID."""
    return UUID("11111111-1111-1111-1111-111111111113")


@pytest.fixture
def barclays_us_id() -> UUID:
    """Barclays US subsidiary ID."""
    return UUID("22222222-2222-2222-2222-222222222223")


@pytest_asyncio.fixture
async def hsbc_parent_tenant(
    integration_db_session: AsyncSession,
    hsbc_parent_id: UUID
) -> Tenant:
    """Create HSBC parent tenant in database."""
    tenant = Tenant(
        tenant_id=hsbc_parent_id,
        name="HSBC Holdings plc",
        parent_tenant_id=None,
        tenant_type=TenantType.PARENT,
        tenant_metadata={
            "country": "United Kingdom",
            "headquarters": "London",
            "business_type": "multinational_bank",
            "founded_year": 1865,
            "employee_count": 220000,
            "regulatory_licenses": [
                "UK_banking_license",
                "FCA_authorization",
                "PRA_authorization"
            ],
            "primary_currency": "GBP",
            "market_cap_billion_usd": 120.5,
        },
        created_at=datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
    )
    
    integration_db_session.add(tenant)
    await integration_db_session.commit()
    await integration_db_session.refresh(tenant)
    
    return tenant


@pytest_asyncio.fixture
async def barclays_parent_tenant(
    integration_db_session: AsyncSession,
    barclays_parent_id: UUID
) -> Tenant:
    """Create Barclays parent tenant in database for isolation testing."""
    tenant = Tenant(
        tenant_id=barclays_parent_id,
        name="Barclays plc",
        parent_tenant_id=None,
        tenant_type=TenantType.PARENT,
        tenant_metadata={
            "country": "United Kingdom",
            "headquarters": "London",
            "business_type": "multinational_bank",
            "founded_year": 1690,
            "employee_count": 83500,
            "regulatory_licenses": [
                "UK_banking_license",
                "FCA_authorization",
                "PRA_authorization"
            ],
            "primary_currency": "GBP",
            "market_cap_billion_usd": 28.2,
        },
        created_at=datetime(2025, 1, 2, 9, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 2, 9, 0, 0, tzinfo=timezone.utc),
    )
    
    integration_db_session.add(tenant)
    await integration_db_session.commit()
    await integration_db_session.refresh(tenant)
    
    return tenant


@pytest_asyncio.fixture
async def hsbc_hk_subsidiary(
    integration_db_session: AsyncSession,
    hsbc_parent_tenant: Tenant,
    hsbc_hk_id: UUID
) -> Tenant:
    """Create HSBC Hong Kong subsidiary tenant."""
    tenant = Tenant(
        tenant_id=hsbc_hk_id,
        name="HSBC Bank (Hong Kong) Limited",
        parent_tenant_id=hsbc_parent_tenant.tenant_id,
        tenant_type=TenantType.SUBSIDIARY,
        tenant_metadata={
            "country": "Hong Kong",
            "region": "Asia Pacific",
            "business_unit": "retail_banking",
            "local_currency": "HKD",
            "employee_count": 15000,
            "local_licenses": [
                "HKMA_banking_license",
                "SFC_type_1_license",
                "MPF_registration"
            ],
            "established_year": 1865,
            "branches": 127,
            "parent_company": "HSBC Holdings plc",
        },
        created_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    
    integration_db_session.add(tenant)
    await integration_db_session.commit()
    await integration_db_session.refresh(tenant)
    
    return tenant


@pytest_asyncio.fixture
async def hsbc_london_subsidiary(
    integration_db_session: AsyncSession,
    hsbc_parent_tenant: Tenant,
    hsbc_london_id: UUID
) -> Tenant:
    """Create HSBC London subsidiary tenant."""
    tenant = Tenant(
        tenant_id=hsbc_london_id,
        name="HSBC UK Bank plc",
        parent_tenant_id=hsbc_parent_tenant.tenant_id,
        tenant_type=TenantType.SUBSIDIARY,
        tenant_metadata={
            "country": "United Kingdom",
            "region": "Europe",
            "business_unit": "investment_banking",
            "local_currency": "GBP",
            "employee_count": 28000,
            "local_licenses": [
                "FCA_authorization",
                "PRA_authorization",
                "FSCS_protection"
            ],
            "established_year": 1836,
            "branches": 441,
            "parent_company": "HSBC Holdings plc",
        },
        created_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
    )
    
    integration_db_session.add(tenant)
    await integration_db_session.commit()
    await integration_db_session.refresh(tenant)
    
    return tenant


@pytest_asyncio.fixture
async def barclays_us_subsidiary(
    integration_db_session: AsyncSession,
    barclays_parent_tenant: Tenant,
    barclays_us_id: UUID
) -> Tenant:
    """Create Barclays US subsidiary tenant for isolation testing."""
    tenant = Tenant(
        tenant_id=barclays_us_id,
        name="Barclays US LLC",
        parent_tenant_id=barclays_parent_tenant.tenant_id,
        tenant_type=TenantType.SUBSIDIARY,
        tenant_metadata={
            "country": "United States",
            "region": "North America",
            "business_unit": "investment_banking",
            "local_currency": "USD",
            "employee_count": 8500,
            "local_licenses": [
                "OCC_banking_charter",
                "FDIC_insurance",
                "FINRA_membership"
            ],
            "established_year": 1994,
            "offices": 25,
            "parent_company": "Barclays plc",
        },
        created_at=datetime(2025, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
    )
    
    integration_db_session.add(tenant)
    await integration_db_session.commit()
    await integration_db_session.refresh(tenant)
    
    return tenant


# RLS Context Management Fixtures

@pytest_asyncio.fixture
async def set_tenant_context():
    """Helper function to set tenant context for RLS testing."""
    async def _set_context(db_session: AsyncSession, tenant_id: UUID) -> None:
        """Set the tenant context for row-level security."""
        await db_session.execute(
            text("SELECT set_current_tenant_id(:tenant_id)"),
            {"tenant_id": str(tenant_id)}
        )
    
    return _set_context


@pytest_asyncio.fixture
async def clear_tenant_context():
    """Helper function to clear tenant context."""
    async def _clear_context(db_session: AsyncSession) -> None:
        """Clear the current tenant context."""
        await db_session.execute(text("SELECT clear_current_tenant_id()"))
    
    return _clear_context


# Test Headers for API Testing

@pytest.fixture
def hsbc_headers(hsbc_parent_id: UUID) -> dict[str, str]:
    """Headers for HSBC parent tenant API requests."""
    return {
        "X-Tenant-ID": str(hsbc_parent_id),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@pytest.fixture
def hsbc_hk_headers(hsbc_hk_id: UUID) -> dict[str, str]:
    """Headers for HSBC Hong Kong subsidiary API requests."""
    return {
        "X-Tenant-ID": str(hsbc_hk_id),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@pytest.fixture
def hsbc_london_headers(hsbc_london_id: UUID) -> dict[str, str]:
    """Headers for HSBC London subsidiary API requests."""
    return {
        "X-Tenant-ID": str(hsbc_london_id),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@pytest.fixture
def barclays_headers(barclays_parent_id: UUID) -> dict[str, str]:
    """Headers for Barclays parent tenant API requests."""
    return {
        "X-Tenant-ID": str(barclays_parent_id),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@pytest.fixture
def barclays_us_headers(barclays_us_id: UUID) -> dict[str, str]:
    """Headers for Barclays US subsidiary API requests."""
    return {
        "X-Tenant-ID": str(barclays_us_id),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# Performance Testing Fixtures

@pytest.fixture
def performance_threshold_ms() -> int:
    """Maximum response time threshold for API calls in milliseconds."""
    return 500


@pytest.fixture
def timing_validator():
    """Helper function to validate API response timing."""
    def _validate_timing(response_time_ms: float, threshold_ms: int = 500) -> bool:
        """Validate that response time is within acceptable threshold."""
        return response_time_ms <= threshold_ms
    
    return _validate_timing


# Database Cleanup and Verification Fixtures

@pytest_asyncio.fixture
async def verify_tenant_isolation():
    """Helper function to verify tenant data isolation."""
    async def _verify_isolation(
        db_session: AsyncSession,
        tenant_id: UUID,
        expected_tenant_ids: set[UUID]
    ) -> bool:
        """
        Verify that only expected tenants are visible in current context.
        
        Args:
            db_session: Database session with tenant context set
            tenant_id: Current tenant ID context
            expected_tenant_ids: Set of tenant IDs that should be visible
            
        Returns:
            True if isolation is correct, False otherwise
        """
        # Set tenant context
        await db_session.execute(
            text("SELECT set_current_tenant_id(:tenant_id)"),
            {"tenant_id": str(tenant_id)}
        )
        
        # Query all visible tenants
        result = await db_session.execute(text("SELECT tenant_id FROM tenants"))
        visible_tenant_ids = {UUID(str(row[0])) for row in result.fetchall()}
        
        # Verify only expected tenants are visible
        return visible_tenant_ids == expected_tenant_ids
    
    return _verify_isolation


@pytest_asyncio.fixture
async def database_health_check():
    """Helper function to verify database connectivity and RLS functions."""
    async def _health_check(db_session: AsyncSession) -> dict[str, Any]:
        """
        Perform comprehensive database health check.
        
        Returns:
            Dictionary with health check results
        """
        health_status = {
            "database_connected": False,
            "rls_enabled": False,
            "functions_available": False,
            "tenant_table_exists": False,
            "error": None
        }
        
        try:
            # Test basic connectivity
            result = await db_session.execute(text("SELECT 1"))
            health_status["database_connected"] = bool(result.scalar())
            
            # Check if RLS is enabled on tenants table
            result = await db_session.execute(text("""
                SELECT relrowsecurity 
                FROM pg_class 
                WHERE relname = 'tenants'
            """))
            health_status["rls_enabled"] = bool(result.scalar())
            
            # Check if tenant functions exist
            result = await db_session.execute(text("""
                SELECT COUNT(*) 
                FROM pg_proc 
                WHERE proname IN ('set_current_tenant_id', 'clear_current_tenant_id', 'get_current_tenant_id')
            """))
            function_count = result.scalar()
            health_status["functions_available"] = function_count == 3
            
            # Check if tenants table exists
            result = await db_session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'tenants'
                )
            """))
            health_status["tenant_table_exists"] = bool(result.scalar())
            
        except Exception as e:
            health_status["error"] = str(e)
        
        return health_status
    
    return _health_check


# Test Data Validation Fixtures

@pytest.fixture
def validate_tenant_response():
    """Helper function to validate tenant API response structure."""
    def _validate_response(response_data: dict, expected_fields: set[str]) -> bool:
        """
        Validate that response contains all expected fields.
        
        Args:
            response_data: Response data dictionary
            expected_fields: Set of expected field names
            
        Returns:
            True if all fields are present and valid
        """
        if not isinstance(response_data, dict):
            return False
        
        response_fields = set(response_data.keys())
        return expected_fields.issubset(response_fields)
    
    return _validate_response


@pytest.fixture
def tenant_response_fields() -> set[str]:
    """Expected fields in tenant API response."""
    return {
        "tenant_id",
        "name", 
        "parent_tenant_id",
        "tenant_type",
        "metadata",
        "created_at",
        "updated_at"
    }