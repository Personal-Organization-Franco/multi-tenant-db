"""
Security testing configuration and fixtures.

Provides specialized fixtures and configuration for security testing:
- Isolated database sessions
- Security test data setup
- Attack simulation utilities
- Test result validation
"""

import asyncio
import logging
from typing import AsyncGenerator, Dict, Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.multi_tenant_db.core.config import get_settings
from src.multi_tenant_db.db.session import get_async_session
from src.multi_tenant_db.models.tenant import Tenant, TenantType

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="session")
async def security_test_database():
    """Ensure security tests run against a clean database state."""
    settings = get_settings()
    
    # Verify we're running against a test database
    assert "test" in str(settings.database_url).lower(), "Security tests must run against test database"
    
    logger.info("Security tests initialized against test database")
    return True


@pytest_asyncio.fixture
async def isolated_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated database session for security tests."""
    settings = get_settings()
    async for session in get_async_session():
        try:
            # Ensure clean state
            await session.execute(text("SELECT clear_tenant_context()"))
            await session.commit()
            
            yield session
        finally:
            # Clean up after test
            await session.execute(text("SELECT clear_tenant_context()"))
            await session.commit()
            await session.close()
        break


@pytest_asyncio.fixture
async def security_baseline_data(isolated_session: AsyncSession) -> Dict[str, Any]:
    """Create baseline security test data."""
    # Clean any existing test data
    await isolated_session.execute(text("DELETE FROM tenants WHERE metadata->>'security_test' = 'true'"))
    await isolated_session.commit()
    
    # Create standardized security test tenants
    legitimate_tenant = Tenant(
        tenant_id=uuid4(),
        name="Legitimate Security Test Tenant",
        tenant_type=TenantType.PARENT,
        parent_tenant_id=None,
        tenant_metadata={
            "security_test": "true",
            "role": "legitimate",
            "sensitivity": "normal"
        }
    )
    
    high_value_tenant = Tenant(
        tenant_id=uuid4(),
        name="High Value Target Tenant",
        tenant_type=TenantType.PARENT,
        parent_tenant_id=None,
        tenant_metadata={
            "security_test": "true",
            "role": "target",
            "sensitivity": "high",
            "classified_data": "top_secret_information",
            "financial_records": {"balance": 50000000, "transactions": ["classified"]}
        }
    )
    
    subsidiary_tenant = Tenant(
        tenant_id=uuid4(),
        name="Target Subsidiary",
        tenant_type=TenantType.SUBSIDIARY,
        parent_tenant_id=high_value_tenant.tenant_id,
        tenant_metadata={
            "security_test": "true",
            "role": "subsidiary",
            "sensitive_subsidiary_data": "subsidiary_classified"
        }
    )
    
    isolated_session.add_all([legitimate_tenant, high_value_tenant, subsidiary_tenant])
    await isolated_session.commit()
    
    # Refresh to ensure data is loaded
    for tenant in [legitimate_tenant, high_value_tenant, subsidiary_tenant]:
        await isolated_session.refresh(tenant)
    
    return {
        "legitimate": legitimate_tenant,
        "target": high_value_tenant,
        "subsidiary": subsidiary_tenant,
        "session": isolated_session
    }


@pytest.fixture
def attack_vectors():
    """Provide common attack vectors for security tests."""
    return {
        "sql_injection": [
            "'; DROP TABLE tenants; --",
            "' OR 1=1; --",
            "'; UPDATE tenants SET metadata = '{\"hacked\": true}'; --",
            "' UNION SELECT NULL, NULL, NULL, NULL, NULL, NULL; --",
            "'; SELECT version(); --"
        ],
        
        "session_manipulation": [
            "'; SET app.current_tenant_id = 'unauthorized_id'; --",
            "RESET app.current_tenant_id",
            "SET LOCAL app.current_tenant_id = 'malicious_id'",
            "SELECT set_config('app.current_tenant_id', 'evil_id', false)"
        ],
        
        "privilege_escalation": [
            "ALTER TABLE tenants DISABLE ROW LEVEL SECURITY",
            "DROP POLICY tenant_select_policy ON tenants",
            "SET ROLE postgres",
            "CREATE VIEW bypass AS SELECT * FROM tenants"
        ],
        
        "information_disclosure": [
            "SELECT pg_sleep(5)",
            "SELECT version()",
            "SELECT current_user",
            "SELECT * FROM pg_policies"
        ]
    }


@pytest.fixture
def security_assertions():
    """Provide security assertion helpers."""
    class SecurityAssertions:
        @staticmethod
        def assert_no_unauthorized_access(query_result, context: str = ""):
            """Assert that query result doesn't contain unauthorized data."""
            if hasattr(query_result, 'fetchall'):
                rows = query_result.fetchall()
            elif hasattr(query_result, '__iter__'):
                rows = list(query_result)
            else:
                rows = [query_result] if query_result is not None else []
            
            assert len(rows) == 0, f"Unauthorized access detected {context}: {len(rows)} rows returned"
        
        @staticmethod
        def assert_error_message_safe(error_message: str, sensitive_data: list):
            """Assert that error messages don't leak sensitive information."""
            message_lower = str(error_message).lower()
            for sensitive in sensitive_data:
                sensitive_lower = str(sensitive).lower()
                assert sensitive_lower not in message_lower, f"Error message leaks sensitive data: {sensitive}"
        
        @staticmethod
        def assert_timing_safe(times_1: list, times_2: list, threshold: float = 0.5):
            """Assert that timing differences don't leak information."""
            avg_1 = sum(times_1) / len(times_1)
            avg_2 = sum(times_2) / len(times_2)
            relative_diff = abs(avg_1 - avg_2) / max(avg_1, avg_2)
            
            assert relative_diff < threshold, f"Timing difference may leak information: {relative_diff:.2%}"
    
    return SecurityAssertions()


@pytest.fixture(autouse=True)
def security_test_logging():
    """Configure enhanced logging for security tests."""
    security_logger = logging.getLogger("security_tests")
    security_logger.setLevel(logging.INFO)
    
    if not security_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        security_logger.addHandler(handler)
    
    yield security_logger


@pytest_asyncio.fixture
async def rls_function_validator(isolated_session: AsyncSession):
    """Validate that all RLS functions are working correctly."""
    async def validate():
        # Check that all required functions exist
        required_functions = [
            'current_tenant_id',
            'can_access_tenant',
            'set_tenant_context',
            'clear_tenant_context'
        ]
        
        for func_name in required_functions:
            result = await isolated_session.execute(text(f"""
                SELECT EXISTS(
                    SELECT 1 FROM pg_proc p 
                    JOIN pg_namespace n ON p.pronamespace = n.oid 
                    WHERE n.nspname = 'public' AND p.proname = '{func_name}'
                )
            """))
            exists = result.scalar()
            assert exists, f"Required RLS function {func_name} is missing"
        
        # Test basic function behavior
        result = await isolated_session.execute(text("SELECT current_tenant_id()"))
        tenant_id = result.scalar()
        assert tenant_id is None, "current_tenant_id should return NULL without context"
        
        await isolated_session.execute(text("SELECT clear_tenant_context()"))
        result = await isolated_session.execute(text("SELECT current_tenant_id()"))
        tenant_id = result.scalar()
        assert tenant_id is None, "clear_tenant_context should clear context"
        
        logger.info("All RLS functions validated successfully")
    
    await validate()
    return validate