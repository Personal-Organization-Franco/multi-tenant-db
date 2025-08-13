"""
Security penetration testing for multi-tenant RLS implementation.

This module contains advanced security tests that attempt to bypass
tenant isolation through various attack vectors:
- SQL injection attempts
- Session manipulation attacks  
- Authorization bypass techniques
- Edge case exploitation
- Information disclosure prevention
"""

import asyncio
import logging
import re
import time
from uuid import UUID, uuid4
from typing import Any, Dict, List, Optional, Tuple

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError, IntegrityError

from src.multi_tenant_db.core.config import get_settings
from src.multi_tenant_db.db.session import get_async_session
from src.multi_tenant_db.models.tenant import Tenant, TenantType

logger = logging.getLogger(__name__)


class TestSecurityPenetration:
    """
    Advanced security penetration testing suite.
    
    Attempts various attack vectors to verify that the RLS implementation
    is bulletproof against common and advanced security vulnerabilities.
    """

    @pytest_asyncio.fixture
    async def db_session(self) -> AsyncSession:
        """Create a database session for testing."""
        settings = get_settings()
        async for session in get_async_session():
            yield session
            break

    @pytest_asyncio.fixture
    async def isolated_test_tenants(self, db_session: AsyncSession) -> Dict[str, Tenant]:
        """Create isolated test tenants for penetration testing."""
        # Clear any existing context
        await db_session.execute(text("SELECT clear_tenant_context()"))
        await db_session.commit()
        
        # Create target tenant (what we're trying to access)
        target_tenant = Tenant(
            tenant_id=uuid4(),
            name="Target Bank Corp",
            tenant_type=TenantType.PARENT,
            parent_tenant_id=None,
            tenant_metadata={
                "sensitive_data": "classified_information",
                "financial_data": {"balance": 1000000, "accounts": ["secret_account"]},
                "penetration_test": True
            }
        )
        
        # Create attacker tenant (what we have access to)
        attacker_tenant = Tenant(
            tenant_id=uuid4(),
            name="Attacker Tenant",
            tenant_type=TenantType.PARENT,
            parent_tenant_id=None,
            tenant_metadata={
                "penetration_test": True,
                "role": "attacker"
            }
        )
        
        # Create subsidiary under target (to test hierarchical bypass)
        target_subsidiary = Tenant(
            tenant_id=uuid4(),
            name="Target Subsidiary",
            tenant_type=TenantType.SUBSIDIARY,
            parent_tenant_id=target_tenant.tenant_id,
            tenant_metadata={
                "subsidiary_secret": "subsidiary_classified_data",
                "penetration_test": True
            }
        )
        
        # Add all tenants
        db_session.add_all([target_tenant, attacker_tenant, target_subsidiary])
        await db_session.commit()
        
        # Refresh to get updated data
        for tenant in [target_tenant, attacker_tenant, target_subsidiary]:
            await db_session.refresh(tenant)
        
        return {
            "target": target_tenant,
            "attacker": attacker_tenant,
            "target_subsidiary": target_subsidiary
        }

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup_context(self, db_session: AsyncSession):
        """Ensure clean context before and after each test."""
        # Clear before test
        await db_session.execute(text("SELECT clear_tenant_context()"))
        await db_session.commit()
        
        yield
        
        # Clear after test
        await db_session.execute(text("SELECT clear_tenant_context()"))
        await db_session.commit()

    async def test_sql_injection_in_tenant_context(self, db_session: AsyncSession, isolated_test_tenants: Dict[str, Tenant]):
        """Test SQL injection attempts in tenant context setting."""
        target = isolated_test_tenants["target"]
        attacker = isolated_test_tenants["attacker"]
        
        # Set legitimate attacker context
        await db_session.execute(text(f"SELECT set_tenant_context('{attacker.tenant_id}')"))
        
        # Attempt various SQL injection attacks in session variables
        injection_attempts = [
            # Basic injection attempts
            f"'; UPDATE tenants SET metadata = metadata || '{{\"hacked\": true}}' WHERE tenant_id = '{target.tenant_id}'; SELECT '",
            f"' UNION ALL SELECT '{target.tenant_id}'::uuid --",
            f"'; DROP TABLE tenants; SELECT '",
            f"'; SELECT set_tenant_context('{target.tenant_id}'); SELECT '",
            
            # Advanced injection attempts
            f"'; INSERT INTO tenants (tenant_id, name, tenant_type) VALUES ('{uuid4()}', 'Injected', 'parent'); SELECT '",
            "'; SELECT version(); --",
            "'; SELECT current_user; --",
            "' OR 1=1; --",
            
            # Encoding attempts
            "\\x27; SELECT 1; --",
            "'; SELECT CHR(39)||CHR(59)||CHR(32)||'SELECT 1'; --"
        ]
        
        for injection in injection_attempts:
            try:
                # Attempt to inject via session variable manipulation
                await db_session.execute(text(f"SET app.current_tenant_id = '{injection}'"))
                
                # Try to access target tenant data
                result = await db_session.execute(text(f"SELECT COUNT(*) FROM tenants WHERE tenant_id = '{target.tenant_id}'"))
                count = result.scalar()
                
                # Should not be able to access target data
                assert count == 0, f"SQL injection may have bypassed RLS: {injection[:50]}..."
                
            except (SQLAlchemyError, ProgrammingError):
                # Expected - injection should fail
                continue
            
            # Verify target tenant wasn't modified
            result = await db_session.execute(text(f"SELECT metadata FROM tenants WHERE tenant_id = '{target.tenant_id}'"))
            # This query will return nothing due to RLS, but we're checking it doesn't crash
            
        # Final verification: ensure target tenant is intact
        await db_session.execute(text("SELECT clear_tenant_context()"))
        # Without context, we can't see any tenant data due to RLS
        result = await db_session.execute(text("SELECT COUNT(*) FROM tenants"))
        count = result.scalar()
        assert count == 0, "RLS should prevent access without context"

    async def test_session_hijacking_attempts(self, db_session: AsyncSession, isolated_test_tenants: Dict[str, Tenant]):
        """Test attempts to hijack or manipulate session context."""
        target = isolated_test_tenants["target"]
        attacker = isolated_test_tenants["attacker"]
        
        # Set legitimate attacker context
        await db_session.execute(text(f"SELECT set_tenant_context('{attacker.tenant_id}')"))
        
        # Verify we have attacker context
        result = await db_session.execute(text("SELECT current_tenant_id()"))
        current_id = result.scalar()
        assert current_id == attacker.tenant_id
        
        # Attempt to manipulate session variables directly
        manipulation_attempts = [
            # Direct variable manipulation
            f"SET app.current_tenant_id = '{target.tenant_id}'",
            
            # Multiple session variables
            f"SET app.current_tenant_id = '{target.tenant_id}'; SET app.backup_tenant = '{attacker.tenant_id}'",
            
            # Reset and override
            f"RESET app.current_tenant_id; SET app.current_tenant_id = '{target.tenant_id}'",
            
            # Transaction-level manipulation
            f"SET LOCAL app.current_tenant_id = '{target.tenant_id}'",
            
            # Using functions to manipulate
            f"SELECT set_config('app.current_tenant_id', '{target.tenant_id}', false)",
            
            # Nested manipulation
            f"SET app.current_tenant_id = (SELECT '{target.tenant_id}'::text)",
        ]
        
        for attempt in manipulation_attempts:
            try:
                # Execute manipulation attempt
                await db_session.execute(text(attempt))
                
                # Check what context we have now
                result = await db_session.execute(text("SELECT current_tenant_id()"))
                manipulated_id = result.scalar()
                
                # Even if session variable was changed, RLS should prevent unauthorized access
                result = await db_session.execute(text(f"SELECT COUNT(*) FROM tenants WHERE tenant_id = '{target.tenant_id}'"))
                target_count = result.scalar()
                
                assert target_count == 0, f"Session manipulation should not grant access to target tenant: {attempt[:50]}..."
                
                # Reset context for next attempt
                await db_session.execute(text(f"SELECT set_tenant_context('{attacker.tenant_id}')"))
                
            except (SQLAlchemyError, ProgrammingError):
                # Expected - manipulation should fail
                continue

    async def test_privilege_escalation_attempts(self, db_session: AsyncSession, isolated_test_tenants: Dict[str, Tenant]):
        """Test attempts to escalate privileges or bypass RLS entirely."""
        target = isolated_test_tenants["target"]
        attacker = isolated_test_tenants["attacker"]
        
        # Set attacker context
        await db_session.execute(text(f"SELECT set_tenant_context('{attacker.tenant_id}')"))
        
        escalation_attempts = [
            # Attempt to disable RLS
            "ALTER TABLE tenants DISABLE ROW LEVEL SECURITY",
            "SET row_security = off",
            
            # Attempt to modify RLS functions
            """
            CREATE OR REPLACE FUNCTION current_tenant_id()
            RETURNS UUID AS $$ SELECT NULL::UUID; $$ LANGUAGE sql;
            """,
            
            # Attempt to drop RLS policies
            "DROP POLICY tenant_select_policy ON tenants",
            "DROP POLICY IF EXISTS tenant_select_policy ON tenants",
            
            # Attempt to create bypass policies
            f"""
            CREATE POLICY bypass_policy ON tenants
            FOR ALL TO current_user
            USING (tenant_id = '{target.tenant_id}')
            """,
            
            # Attempt to modify table structure
            "ALTER TABLE tenants DROP COLUMN tenant_id",
            "ALTER TABLE tenants ADD COLUMN bypass_flag boolean DEFAULT true",
            
            # Attempt to create views to bypass RLS
            f"""
            CREATE VIEW tenant_bypass AS 
            SELECT * FROM tenants WHERE tenant_id = '{target.tenant_id}'
            """,
            
            # Attempt superuser actions
            "SET ROLE postgres",
            "SET session_authorization postgres",
            
            # Attempt to access system catalogs for information
            "SELECT * FROM pg_policies WHERE tablename = 'tenants'",
            "SELECT * FROM pg_proc WHERE proname = 'current_tenant_id'",
        ]
        
        for attempt in escalation_attempts:
            try:
                await db_session.execute(text(attempt))
                await db_session.commit()
                
                # If the command succeeded, verify it didn't actually bypass security
                result = await db_session.execute(text(f"SELECT COUNT(*) FROM tenants WHERE tenant_id = '{target.tenant_id}'"))
                target_count = result.scalar()
                
                assert target_count == 0, f"Privilege escalation may have succeeded: {attempt[:50]}..."
                
            except (SQLAlchemyError, ProgrammingError):
                # Expected - escalation should fail
                continue
            finally:
                # Rollback any changes
                await db_session.rollback()

    async def test_information_disclosure_prevention(self, db_session: AsyncSession, isolated_test_tenants: Dict[str, Tenant]):
        """Test that error messages don't disclose sensitive information."""
        target = isolated_test_tenants["target"]
        attacker = isolated_test_tenants["attacker"]
        
        # Set attacker context
        await db_session.execute(text(f"SELECT set_tenant_context('{attacker.tenant_id}')"))
        
        # Attempt queries that might leak information through error messages
        disclosure_attempts = [
            # Attempt to get existence information
            f"SELECT 1/(CASE WHEN EXISTS(SELECT 1 FROM tenants WHERE tenant_id = '{target.tenant_id}') THEN 0 ELSE 1 END)",
            
            # Attempt timing-based information disclosure
            f"SELECT pg_sleep(CASE WHEN EXISTS(SELECT 1 FROM tenants WHERE tenant_id = '{target.tenant_id}') THEN 5 ELSE 0 END)",
            
            # Attempt to extract data via error messages
            f"SELECT CAST((SELECT name FROM tenants WHERE tenant_id = '{target.tenant_id}') AS INTEGER)",
            
            # Attempt conditional logic to extract information
            f"""SELECT 
                CASE WHEN (SELECT COUNT(*) FROM tenants WHERE tenant_id = '{target.tenant_id}') > 0 
                THEN 1/0 
                ELSE 1 
                END""",
            
            # Attempt to use constraint violations for information
            f"INSERT INTO tenants (tenant_id, name, tenant_type) VALUES ('{target.tenant_id}', 'duplicate', 'parent')",
        ]
        
        for attempt in disclosure_attempts:
            try:
                result = await db_session.execute(text(attempt))
                # If query succeeds, it should not provide information about target tenant
                
            except Exception as e:
                error_message = str(e).lower()
                
                # Check that error messages don't contain sensitive information
                sensitive_patterns = [
                    target.tenant_id.hex.lower(),
                    target.name.lower(),
                    "target bank corp",
                    "classified",
                    "secret"
                ]
                
                for pattern in sensitive_patterns:
                    assert pattern not in error_message, f"Error message may disclose sensitive data: {pattern}"

    async def test_concurrent_attack_resistance(self, db_session: AsyncSession, isolated_test_tenants: Dict[str, Tenant]):
        """Test resistance to concurrent attack attempts."""
        target = isolated_test_tenants["target"]
        attacker = isolated_test_tenants["attacker"]
        
        async def attack_attempt(session_id: int):
            """Simulate concurrent attack attempt."""
            settings = get_settings()
            async for session in get_async_session():
                try:
                    # Set attacker context
                    await session.execute(text(f"SELECT set_tenant_context('{attacker.tenant_id}')"))
                    
                    # Attempt rapid context switching
                    for _ in range(10):
                        try:
                            # Try to manipulate context
                            await session.execute(text(f"SET app.current_tenant_id = '{target.tenant_id}'"))
                            
                            # Try to access target data
                            result = await session.execute(text(f"SELECT COUNT(*) FROM tenants WHERE tenant_id = '{target.tenant_id}'"))
                            count = result.scalar()
                            
                            if count > 0:
                                return f"Attack {session_id} succeeded!"
                            
                            # Reset for next attempt
                            await session.execute(text(f"SELECT set_tenant_context('{attacker.tenant_id}')"))
                            
                        except Exception:
                            continue
                    
                    return f"Attack {session_id} failed (expected)"
                finally:
                    await session.close()
                break
        
        # Launch concurrent attacks
        attack_tasks = [attack_attempt(i) for i in range(10)]
        results = await asyncio.gather(*attack_tasks, return_exceptions=True)
        
        # Verify all attacks failed
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.info(f"Attack {i} failed with exception (expected): {result}")
            else:
                assert "failed" in result, f"Concurrent attack may have succeeded: {result}"

    async def test_transaction_boundary_security(self, db_session: AsyncSession, isolated_test_tenants: Dict[str, Tenant]):
        """Test security across transaction boundaries."""
        target = isolated_test_tenants["target"]
        attacker = isolated_test_tenants["attacker"]
        
        # Test transaction rollback doesn't leave security holes
        await db_session.execute(text(f"SELECT set_tenant_context('{attacker.tenant_id}')"))
        
        try:
            # Start transaction
            await db_session.begin()
            
            # Try to manipulate context within transaction
            await db_session.execute(text(f"SET LOCAL app.current_tenant_id = '{target.tenant_id}'"))
            
            # Verify we can't access target data
            result = await db_session.execute(text(f"SELECT COUNT(*) FROM tenants WHERE tenant_id = '{target.tenant_id}'"))
            count = result.scalar()
            assert count == 0, "Should not access target data even with LOCAL context manipulation"
            
            # Force rollback
            await db_session.rollback()
            
        except Exception:
            await db_session.rollback()
        
        # Verify context is properly restored after rollback
        result = await db_session.execute(text("SELECT current_tenant_id()"))
        current_id = result.scalar()
        assert current_id == attacker.tenant_id or current_id is None, "Context should be restored after rollback"

    async def test_metadata_injection_attacks(self, db_session: AsyncSession, isolated_test_tenants: Dict[str, Tenant]):
        """Test attempts to inject malicious data through metadata fields."""
        target = isolated_test_tenants["target"]
        attacker = isolated_test_tenants["attacker"]
        
        # Set attacker context
        await db_session.execute(text(f"SELECT set_tenant_context('{attacker.tenant_id}')"))
        
        # Create malicious metadata payloads
        malicious_payloads = [
            # JSON injection attempts
            {"'; DROP TABLE tenants; --": "injection"},
            {"admin": True, "tenant_id": str(target.tenant_id)},
            {"bypass": "'; SELECT * FROM tenants; --"},
            
            # Script injection
            {"script": "<script>alert('xss')</script>"},
            {"code": "eval('malicious_code')"},
            
            # SQL function calls
            {"func": "current_user()"},
            {"query": "SELECT version()"}
        ]
        
        for payload in malicious_payloads:
            try:
                # Try to update attacker tenant with malicious metadata
                await db_session.execute(text(f"""
                    UPDATE tenants 
                    SET metadata = metadata || '{str(payload).replace("'", "''")}'::jsonb
                    WHERE tenant_id = '{attacker.tenant_id}'
                """))
                await db_session.commit()
                
                # Verify the payload didn't grant access to target tenant
                result = await db_session.execute(text(f"SELECT COUNT(*) FROM tenants WHERE tenant_id = '{target.tenant_id}'"))
                count = result.scalar()
                assert count == 0, f"Metadata injection may have bypassed security: {payload}"
                
            except Exception as e:
                # Expected - injection should fail or be safely stored
                continue

    async def test_function_parameter_injection(self, db_session: AsyncSession, isolated_test_tenants: Dict[str, Tenant]):
        """Test injection attempts through RLS function parameters."""
        target = isolated_test_tenants["target"]
        attacker = isolated_test_tenants["attacker"]
        
        # Attempt to inject through can_access_tenant function
        injection_attempts = [
            # SQL injection in UUID parameter
            f"'; UPDATE tenants SET metadata = metadata || '{{\"hacked\": true}}'; SELECT '{target.tenant_id}'::uuid; --",
            
            # Function call injection
            f"current_user()::text::uuid",
            
            # Union injection
            f"' UNION SELECT '{target.tenant_id}'::uuid --",
            
            # Nested function calls
            f"(SELECT tenant_id FROM tenants WHERE name = 'Target Bank Corp' LIMIT 1)",
        ]
        
        for injection in injection_attempts:
            try:
                # Attempt injection through can_access_tenant function
                result = await db_session.execute(text(f"SELECT can_access_tenant('{injection}')"))
                access_result = result.scalar()
                
                # Should return False or cause an error, never True
                assert access_result is False or access_result is None, f"Function parameter injection may have succeeded: {injection[:50]}..."
                
            except (SQLAlchemyError, ProgrammingError):
                # Expected - injection should fail
                continue

    async def test_rls_policy_bypass_attempts(self, db_session: AsyncSession, isolated_test_tenants: Dict[str, Tenant]):
        """Test direct attempts to bypass RLS policies."""
        target = isolated_test_tenants["target"]
        attacker = isolated_test_tenants["attacker"]
        
        # Set attacker context
        await db_session.execute(text(f"SELECT set_tenant_context('{attacker.tenant_id}')"))
        
        # Attempt various bypass techniques
        bypass_attempts = [
            # Try to use system functions
            f"SELECT * FROM tenants WHERE tenant_id = '{target.tenant_id}' AND current_user = current_user",
            
            # Try to use WITH clauses
            f"""WITH target_tenant AS (SELECT '{target.tenant_id}'::uuid as id)
               SELECT * FROM tenants t, target_tenant tt WHERE t.tenant_id = tt.id""",
            
            # Try to use subqueries
            f"""SELECT * FROM tenants WHERE tenant_id IN (
                   SELECT '{target.tenant_id}'::uuid
               )""",
            
            # Try to use LATERAL joins
            f"""SELECT * FROM tenants t
               LATERAL (SELECT '{target.tenant_id}'::uuid as target_id) l
               WHERE t.tenant_id = l.target_id""",
            
            # Try to use window functions
            f"""SELECT * FROM (
                   SELECT *, ROW_NUMBER() OVER () FROM tenants
               ) t WHERE tenant_id = '{target.tenant_id}'""",
            
            # Try to use EXCEPT/INTERSECT
            f"""SELECT * FROM tenants 
               INTERSECT 
               SELECT * FROM tenants WHERE tenant_id = '{target.tenant_id}'""",
        ]
        
        for attempt in bypass_attempts:
            try:
                result = await db_session.execute(text(attempt))
                rows = result.fetchall()
                
                # Should return no rows due to RLS
                assert len(rows) == 0, f"RLS bypass attempt may have succeeded: {attempt[:50]}..."
                
            except (SQLAlchemyError, ProgrammingError):
                # Expected - bypass should fail
                continue

    async def test_timing_attack_resistance(self, db_session: AsyncSession, isolated_test_tenants: Dict[str, Tenant]):
        """Test resistance to timing-based attacks."""
        target = isolated_test_tenants["target"]
        attacker = isolated_test_tenants["attacker"]
        non_existent_id = uuid4()
        
        # Set attacker context
        await db_session.execute(text(f"SELECT set_tenant_context('{attacker.tenant_id}')"))
        
        # Measure timing for queries against existing but inaccessible tenant
        target_times = []
        for _ in range(10):
            start_time = time.perf_counter()
            result = await db_session.execute(text(f"SELECT COUNT(*) FROM tenants WHERE tenant_id = '{target.tenant_id}'"))
            count = result.scalar()
            end_time = time.perf_counter()
            target_times.append(end_time - start_time)
            assert count == 0, "Should not access target tenant"
        
        # Measure timing for queries against non-existent tenant
        nonexistent_times = []
        for _ in range(10):
            start_time = time.perf_counter()
            result = await db_session.execute(text(f"SELECT COUNT(*) FROM tenants WHERE tenant_id = '{non_existent_id}'"))
            count = result.scalar()
            end_time = time.perf_counter()
            nonexistent_times.append(end_time - start_time)
            assert count == 0, "Should not access non-existent tenant"
        
        # Calculate average times
        avg_target_time = sum(target_times) / len(target_times)
        avg_nonexistent_time = sum(nonexistent_times) / len(nonexistent_times)
        
        # Time difference should not be significant enough to leak information
        time_difference = abs(avg_target_time - avg_nonexistent_time)
        relative_difference = time_difference / max(avg_target_time, avg_nonexistent_time)
        
        logger.info(f"Timing analysis - Target: {avg_target_time:.6f}s, Non-existent: {avg_nonexistent_time:.6f}s, Diff: {relative_difference:.2%}")
        
        # Timing difference should be minimal (less than 50% difference)
        assert relative_difference < 0.5, f"Timing difference may leak information: {relative_difference:.2%}"