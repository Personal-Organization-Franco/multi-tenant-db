"""
Comprehensive Row Level Security (RLS) testing for multi-tenant database.

This module tests all RLS policies with real database queries to ensure
complete tenant isolation and proper hierarchical access control.
"""

import asyncio
import logging
from uuid import UUID, uuid4
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from src.multi_tenant_db.core.config import get_settings
from src.multi_tenant_db.db.session import get_async_session
from src.multi_tenant_db.models.tenant import Tenant, TenantType

logger = logging.getLogger(__name__)


class TestRLSSecurityValidation:
    """
    Test suite for comprehensive RLS security validation.
    
    Tests all RLS policies with real database queries to verify:
    - Tenant isolation at SQL level
    - Hierarchical access patterns
    - Policy enforcement across all CRUD operations
    - Session context security
    """

    @pytest_asyncio.fixture
    async def db_session(self) -> AsyncSession:
        """Create a real database session for testing."""
        settings = get_settings()
        async for session in get_async_session():
            yield session
            break

    @pytest_asyncio.fixture
    async def test_tenants(self, db_session: AsyncSession) -> Dict[str, Tenant]:
        """Create test tenants with hierarchical structure."""
        # Clear any existing tenant context
        await db_session.execute(text("SELECT clear_tenant_context()"))
        await db_session.commit()
        
        # Create parent tenant
        parent_tenant = Tenant(
            tenant_id=uuid4(),
            name="Parent Bank Corp",
            tenant_type=TenantType.PARENT,
            parent_tenant_id=None,
            tenant_metadata={"level": "parent", "test": True}
        )
        
        # Create first subsidiary
        subsidiary1 = Tenant(
            tenant_id=uuid4(),
            name="Subsidiary Bank US",
            tenant_type=TenantType.SUBSIDIARY,
            parent_tenant_id=parent_tenant.tenant_id,
            tenant_metadata={"level": "subsidiary", "region": "US", "test": True}
        )
        
        # Create second subsidiary
        subsidiary2 = Tenant(
            tenant_id=uuid4(),
            name="Subsidiary Bank EU",
            tenant_type=TenantType.SUBSIDIARY,
            parent_tenant_id=parent_tenant.tenant_id,
            tenant_metadata={"level": "subsidiary", "region": "EU", "test": True}
        )
        
        # Create separate parent tenant (for isolation testing)
        separate_parent = Tenant(
            tenant_id=uuid4(),
            name="Separate Bank Corp",
            tenant_type=TenantType.PARENT,
            parent_tenant_id=None,
            tenant_metadata={"level": "parent", "isolated": True, "test": True}
        )
        
        # Create subsidiary under separate parent
        separate_subsidiary = Tenant(
            tenant_id=uuid4(),
            name="Separate Subsidiary Bank",
            tenant_type=TenantType.SUBSIDIARY,
            parent_tenant_id=separate_parent.tenant_id,
            tenant_metadata={"level": "subsidiary", "isolated": True, "test": True}
        )
        
        # Add all tenants to session
        db_session.add_all([
            parent_tenant, subsidiary1, subsidiary2, 
            separate_parent, separate_subsidiary
        ])
        await db_session.commit()
        
        # Refresh to get updated data
        for tenant in [parent_tenant, subsidiary1, subsidiary2, separate_parent, separate_subsidiary]:
            await db_session.refresh(tenant)
        
        return {
            "parent": parent_tenant,
            "subsidiary1": subsidiary1,
            "subsidiary2": subsidiary2,
            "separate_parent": separate_parent,
            "separate_subsidiary": separate_subsidiary
        }

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup_tenant_context(self, db_session: AsyncSession):
        """Ensure clean tenant context before and after each test."""
        # Clear context before test
        await db_session.execute(text("SELECT clear_tenant_context()"))
        await db_session.commit()
        
        yield
        
        # Clear context after test
        await db_session.execute(text("SELECT clear_tenant_context()"))
        await db_session.commit()

    async def test_rls_enabled_on_tenants_table(self, db_session: AsyncSession):
        """Test that RLS is properly enabled on tenants table."""
        # Check if RLS is enabled
        result = await db_session.execute(text("""
            SELECT relrowsecurity, relforcerowsecurity 
            FROM pg_class 
            WHERE relname = 'tenants'
        """))
        rls_status = result.fetchone()
        
        assert rls_status is not None, "Tenants table should exist"
        assert rls_status[0] is True, "RLS should be enabled on tenants table"
        assert rls_status[1] is True, "FORCE RLS should be enabled on tenants table"

    async def test_current_tenant_id_function_security(self, db_session: AsyncSession):
        """Test current_tenant_id() function security and behavior."""
        # Test without tenant context
        result = await db_session.execute(text("SELECT current_tenant_id()"))
        tenant_id = result.scalar()
        assert tenant_id is None, "Should return NULL when no tenant context is set"
        
        # Test with valid tenant context
        test_uuid = uuid4()
        await db_session.execute(text(f"SET app.current_tenant_id = '{test_uuid}'"))
        
        result = await db_session.execute(text("SELECT current_tenant_id()"))
        tenant_id = result.scalar()
        assert tenant_id == test_uuid, "Should return the set tenant ID"
        
        # Test with invalid UUID format
        await db_session.execute(text("SET app.current_tenant_id = 'invalid-uuid'"))
        result = await db_session.execute(text("SELECT current_tenant_id()"))
        tenant_id = result.scalar()
        assert tenant_id is None, "Should return NULL for invalid UUID"

    async def test_can_access_tenant_function_security(self, db_session: AsyncSession, test_tenants: Dict[str, Tenant]):
        """Test can_access_tenant() function with various access patterns."""
        parent = test_tenants["parent"]
        subsidiary1 = test_tenants["subsidiary1"]
        separate_parent = test_tenants["separate_parent"]
        
        # Test without session context (should deny all access)
        result = await db_session.execute(text(f"SELECT can_access_tenant('{parent.tenant_id}')"))
        can_access = result.scalar()
        assert can_access is False, "Should deny access without tenant context"
        
        # Test parent accessing own data
        await db_session.execute(text(f"SELECT set_tenant_context('{parent.tenant_id}')"))
        result = await db_session.execute(text(f"SELECT can_access_tenant('{parent.tenant_id}')"))
        can_access = result.scalar()
        assert can_access is True, "Parent should access own data"
        
        # Test parent accessing subsidiary data
        result = await db_session.execute(text(f"SELECT can_access_tenant('{subsidiary1.tenant_id}')"))
        can_access = result.scalar()
        assert can_access is True, "Parent should access subsidiary data"
        
        # Test parent accessing unrelated tenant data
        result = await db_session.execute(text(f"SELECT can_access_tenant('{separate_parent.tenant_id}')"))
        can_access = result.scalar()
        assert can_access is False, "Parent should NOT access unrelated tenant data"
        
        # Test subsidiary accessing own data
        await db_session.execute(text(f"SELECT set_tenant_context('{subsidiary1.tenant_id}')"))
        result = await db_session.execute(text(f"SELECT can_access_tenant('{subsidiary1.tenant_id}')"))
        can_access = result.scalar()
        assert can_access is True, "Subsidiary should access own data"
        
        # Test subsidiary accessing parent data (should be denied)
        result = await db_session.execute(text(f"SELECT can_access_tenant('{parent.tenant_id}')"))
        can_access = result.scalar()
        assert can_access is False, "Subsidiary should NOT access parent data"

    async def test_select_policy_enforcement(self, db_session: AsyncSession, test_tenants: Dict[str, Tenant]):
        """Test SELECT policy enforcement with various tenant contexts."""
        parent = test_tenants["parent"]
        subsidiary1 = test_tenants["subsidiary1"]
        subsidiary2 = test_tenants["subsidiary2"]
        separate_parent = test_tenants["separate_parent"]
        
        # Test with no tenant context (should return no rows)
        result = await db_session.execute(text("SELECT COUNT(*) FROM tenants WHERE metadata->>'test' = 'true'"))
        count = result.scalar()
        assert count == 0, "Should return no rows without tenant context"
        
        # Test parent tenant can see own and subsidiary data
        await db_session.execute(text(f"SELECT set_tenant_context('{parent.tenant_id}')"))
        result = await db_session.execute(text("SELECT tenant_id FROM tenants ORDER BY name"))
        visible_tenants = [row[0] for row in result.fetchall()]
        
        expected_ids = {parent.tenant_id, subsidiary1.tenant_id, subsidiary2.tenant_id}
        actual_ids = set(visible_tenants)
        assert actual_ids == expected_ids, f"Parent should see own and subsidiary tenants. Expected: {expected_ids}, Got: {actual_ids}"
        
        # Test subsidiary tenant can only see own data
        await db_session.execute(text(f"SELECT set_tenant_context('{subsidiary1.tenant_id}')"))
        result = await db_session.execute(text("SELECT tenant_id FROM tenants"))
        visible_tenants = [row[0] for row in result.fetchall()]
        
        assert len(visible_tenants) == 1, "Subsidiary should only see own data"
        assert visible_tenants[0] == subsidiary1.tenant_id, "Subsidiary should see only itself"
        
        # Test complete isolation between separate tenant hierarchies
        await db_session.execute(text(f"SELECT set_tenant_context('{separate_parent.tenant_id}')"))
        result = await db_session.execute(text("SELECT tenant_id FROM tenants"))
        visible_tenants = [row[0] for row in result.fetchall()]
        
        # Should only see separate_parent and its subsidiary
        assert len(visible_tenants) == 2, "Separate parent should see only its hierarchy"
        visible_ids = set(visible_tenants)
        expected_separate_ids = {separate_parent.tenant_id, test_tenants["separate_subsidiary"].tenant_id}
        assert visible_ids == expected_separate_ids, "Should only see separate tenant hierarchy"

    async def test_insert_policy_enforcement(self, db_session: AsyncSession, test_tenants: Dict[str, Tenant]):
        """Test INSERT policy enforcement and validation."""
        parent = test_tenants["parent"]
        subsidiary1 = test_tenants["subsidiary1"]
        
        # Test insertion without tenant context (should work for parent tenants)
        await db_session.execute(text("SELECT clear_tenant_context()"))
        
        new_parent_id = uuid4()
        try:
            await db_session.execute(text(f"""
                INSERT INTO tenants (tenant_id, name, tenant_type, parent_tenant_id, metadata)
                VALUES ('{new_parent_id}', 'New Parent Bank', 'parent', NULL, '{{"test": true}}')
            """))
            await db_session.commit()
            # Should succeed
        except Exception as e:
            pytest.fail(f"Should allow parent tenant creation without context: {e}")
        
        # Test subsidiary creation under parent tenant context
        await db_session.execute(text(f"SELECT set_tenant_context('{parent.tenant_id}')"))
        
        new_subsidiary_id = uuid4()
        try:
            await db_session.execute(text(f"""
                INSERT INTO tenants (tenant_id, name, tenant_type, parent_tenant_id, metadata)
                VALUES ('{new_subsidiary_id}', 'New Subsidiary Bank', 'subsidiary', '{parent.tenant_id}', '{{"test": true}}')
            """))
            await db_session.commit()
            # Should succeed
        except Exception as e:
            pytest.fail(f"Should allow subsidiary creation under parent context: {e}")
        
        # Test unauthorized subsidiary creation (subsidiary trying to create subsidiary)
        await db_session.execute(text(f"SELECT set_tenant_context('{subsidiary1.tenant_id}')"))
        
        unauthorized_subsidiary_id = uuid4()
        with pytest.raises(SQLAlchemyError):
            await db_session.execute(text(f"""
                INSERT INTO tenants (tenant_id, name, tenant_type, parent_tenant_id, metadata)
                VALUES ('{unauthorized_subsidiary_id}', 'Unauthorized Subsidiary', 'subsidiary', '{parent.tenant_id}', '{{"test": true}}')
            """))
            await db_session.commit()

    async def test_update_policy_enforcement(self, db_session: AsyncSession, test_tenants: Dict[str, Tenant]):
        """Test UPDATE policy enforcement and restrictions."""
        parent = test_tenants["parent"]
        subsidiary1 = test_tenants["subsidiary1"]
        separate_parent = test_tenants["separate_parent"]
        
        # Test parent updating own data
        await db_session.execute(text(f"SELECT set_tenant_context('{parent.tenant_id}')"))
        
        try:
            await db_session.execute(text(f"""
                UPDATE tenants 
                SET metadata = metadata || '{{"updated": true}}' 
                WHERE tenant_id = '{parent.tenant_id}'
            """))
            await db_session.commit()
            # Should succeed
        except Exception as e:
            pytest.fail(f"Parent should be able to update own data: {e}")
        
        # Test parent updating subsidiary data
        try:
            await db_session.execute(text(f"""
                UPDATE tenants 
                SET metadata = metadata || '{{"updated_by_parent": true}}' 
                WHERE tenant_id = '{subsidiary1.tenant_id}'
            """))
            await db_session.commit()
            # Should succeed
        except Exception as e:
            pytest.fail(f"Parent should be able to update subsidiary data: {e}")
        
        # Test unauthorized update (accessing unrelated tenant)
        with pytest.raises(SQLAlchemyError):
            await db_session.execute(text(f"""
                UPDATE tenants 
                SET metadata = metadata || '{{"unauthorized": true}}' 
                WHERE tenant_id = '{separate_parent.tenant_id}'
            """))
            await db_session.commit()
        
        # Test subsidiary updating own data
        await db_session.execute(text(f"SELECT set_tenant_context('{subsidiary1.tenant_id}')"))
        
        try:
            await db_session.execute(text(f"""
                UPDATE tenants 
                SET metadata = metadata || '{{"self_updated": true}}' 
                WHERE tenant_id = '{subsidiary1.tenant_id}'
            """))
            await db_session.commit()
            # Should succeed
        except Exception as e:
            pytest.fail(f"Subsidiary should be able to update own data: {e}")
        
        # Test subsidiary attempting to update parent (should fail)
        result = await db_session.execute(text(f"""
            UPDATE tenants 
            SET metadata = metadata || '{{"unauthorized_update": true}}' 
            WHERE tenant_id = '{parent.tenant_id}'
        """))
        await db_session.commit()
        
        # Check that no rows were affected (policy prevented update)
        assert result.rowcount == 0, "Subsidiary should not be able to update parent data"

    async def test_delete_policy_enforcement(self, db_session: AsyncSession, test_tenants: Dict[str, Tenant]):
        """Test DELETE policy enforcement and cascade restrictions."""
        parent = test_tenants["parent"]
        subsidiary1 = test_tenants["subsidiary1"]
        separate_parent = test_tenants["separate_parent"]
        separate_subsidiary = test_tenants["separate_subsidiary"]
        
        # Test deleting subsidiary with parent context
        await db_session.execute(text(f"SELECT set_tenant_context('{parent.tenant_id}')"))
        
        try:
            await db_session.execute(text(f"DELETE FROM tenants WHERE tenant_id = '{subsidiary1.tenant_id}'"))
            await db_session.commit()
            # Should succeed
        except Exception as e:
            pytest.fail(f"Parent should be able to delete subsidiary: {e}")
        
        # Test attempting to delete parent with active subsidiaries (should fail)
        with pytest.raises(SQLAlchemyError):
            await db_session.execute(text(f"DELETE FROM tenants WHERE tenant_id = '{parent.tenant_id}'"))
            await db_session.commit()
        
        # Test subsidiary attempting to delete parent (should fail due to RLS)
        await db_session.execute(text(f"SELECT set_tenant_context('{separate_subsidiary.tenant_id}')"))
        
        result = await db_session.execute(text(f"DELETE FROM tenants WHERE tenant_id = '{separate_parent.tenant_id}'"))
        await db_session.commit()
        
        # Check that no rows were affected (policy prevented deletion)
        assert result.rowcount == 0, "Subsidiary should not be able to delete parent"
        
        # Test unauthorized deletion (different tenant hierarchy)
        await db_session.execute(text(f"SELECT set_tenant_context('{separate_parent.tenant_id}')"))
        
        result = await db_session.execute(text(f"DELETE FROM tenants WHERE tenant_id = '{parent.tenant_id}'"))
        await db_session.commit()
        
        assert result.rowcount == 0, "Should not be able to delete unrelated tenant"

    async def test_session_context_manipulation_resistance(self, db_session: AsyncSession, test_tenants: Dict[str, Tenant]):
        """Test resistance to session context manipulation attacks."""
        parent = test_tenants["parent"]
        separate_parent = test_tenants["separate_parent"]
        
        # Set legitimate tenant context
        await db_session.execute(text(f"SELECT set_tenant_context('{parent.tenant_id}')"))
        
        # Attempt to manipulate session variable directly
        await db_session.execute(text(f"SET app.current_tenant_id = '{separate_parent.tenant_id}'"))
        
        # Verify that set_tenant_context validation is bypassed but RLS still works
        result = await db_session.execute(text("SELECT current_tenant_id()"))
        current_id = result.scalar()
        assert current_id == separate_parent.tenant_id, "Session variable was manipulated"
        
        # But RLS should still prevent access to unauthorized data
        result = await db_session.execute(text(f"SELECT tenant_id FROM tenants WHERE tenant_id = '{parent.tenant_id}'"))
        rows = result.fetchall()
        assert len(rows) == 0, "RLS should prevent access even with manipulated session"
        
        # Test setting invalid tenant context
        with pytest.raises(SQLAlchemyError):
            await db_session.execute(text(f"SELECT set_tenant_context('{uuid4()}')"))

    async def test_rls_function_immutability(self, db_session: AsyncSession):
        """Test that RLS functions cannot be modified or dropped by regular operations."""
        # Test attempting to drop RLS functions (should be restricted)
        with pytest.raises(SQLAlchemyError):
            await db_session.execute(text("DROP FUNCTION current_tenant_id()"))
        
        with pytest.raises(SQLAlchemyError):
            await db_session.execute(text("DROP FUNCTION can_access_tenant(UUID)"))
        
        # Test attempting to modify function behavior
        with pytest.raises(SQLAlchemyError):
            await db_session.execute(text("""
                CREATE OR REPLACE FUNCTION current_tenant_id()
                RETURNS UUID AS $$ SELECT NULL::UUID; $$ LANGUAGE sql;
            """))

    async def test_rls_policies_comprehensive_coverage(self, db_session: AsyncSession):
        """Test that all required RLS policies exist and are properly configured."""
        # Get all policies on tenants table
        result = await db_session.execute(text("""
            SELECT policyname, cmd, permissive, roles, qual, with_check
            FROM pg_policies 
            WHERE tablename = 'tenants'
            ORDER BY policyname
        """))
        policies = result.fetchall()
        
        policy_names = [p[0] for p in policies]
        expected_policies = {
            'tenant_select_policy',
            'tenant_insert_policy', 
            'tenant_update_policy',
            'tenant_delete_policy'
        }
        
        actual_policies = set(policy_names)
        assert actual_policies == expected_policies, f"Missing policies: {expected_policies - actual_policies}"
        
        # Verify each policy has correct command
        policy_commands = {p[0]: p[1] for p in policies}
        assert policy_commands['tenant_select_policy'] == 'SELECT'
        assert policy_commands['tenant_insert_policy'] == 'INSERT'
        assert policy_commands['tenant_update_policy'] == 'UPDATE'
        assert policy_commands['tenant_delete_policy'] == 'DELETE'
        
        # Verify policies are restrictive (not permissive)
        for policy in policies:
            assert policy[2] == 'RESTRICTIVE' or policy[2] is None, f"Policy {policy[0]} should be restrictive"

    async def test_hierarchical_access_edge_cases(self, db_session: AsyncSession, test_tenants: Dict[str, Tenant]):
        """Test edge cases in hierarchical access patterns."""
        parent = test_tenants["parent"]
        subsidiary1 = test_tenants["subsidiary1"]
        subsidiary2 = test_tenants["subsidiary2"]
        
        # Test sibling access (subsidiary1 accessing subsidiary2)
        await db_session.execute(text(f"SELECT set_tenant_context('{subsidiary1.tenant_id}')"))
        
        result = await db_session.execute(text(f"SELECT tenant_id FROM tenants WHERE tenant_id = '{subsidiary2.tenant_id}'"))
        rows = result.fetchall()
        assert len(rows) == 0, "Subsidiaries should not access each other's data"
        
        # Test deep hierarchy prevention (attempt to create sub-subsidiary)
        await db_session.execute(text(f"SELECT set_tenant_context('{parent.tenant_id}')"))
        
        deep_subsidiary_id = uuid4()
        with pytest.raises(SQLAlchemyError):
            await db_session.execute(text(f"""
                INSERT INTO tenants (tenant_id, name, tenant_type, parent_tenant_id, metadata)
                VALUES ('{deep_subsidiary_id}', 'Deep Subsidiary', 'subsidiary', '{subsidiary1.tenant_id}', '{{"test": true}}')
            """))
            await db_session.commit()

    async def test_data_isolation_verification(self, db_session: AsyncSession, test_tenants: Dict[str, Tenant]):
        """Comprehensive test to verify complete data isolation between tenants."""
        parent = test_tenants["parent"]
        separate_parent = test_tenants["separate_parent"]
        
        # Set parent context and get row count
        await db_session.execute(text(f"SELECT set_tenant_context('{parent.tenant_id}')"))
        result = await db_session.execute(text("SELECT COUNT(*) FROM tenants"))
        parent_count = result.scalar()
        
        # Set separate parent context and get row count
        await db_session.execute(text(f"SELECT set_tenant_context('{separate_parent.tenant_id}')"))
        result = await db_session.execute(text("SELECT COUNT(*) FROM tenants"))
        separate_count = result.scalar()
        
        # Verify no overlap
        assert parent_count > 0, "Parent should see some tenants"
        assert separate_count > 0, "Separate parent should see some tenants"
        
        # Get actual visible tenants for each context
        await db_session.execute(text(f"SELECT set_tenant_context('{parent.tenant_id}')"))
        result = await db_session.execute(text("SELECT tenant_id FROM tenants"))
        parent_visible = set(row[0] for row in result.fetchall())
        
        await db_session.execute(text(f"SELECT set_tenant_context('{separate_parent.tenant_id}')"))
        result = await db_session.execute(text("SELECT tenant_id FROM tenants"))
        separate_visible = set(row[0] for row in result.fetchall())
        
        # Verify complete isolation
        overlap = parent_visible.intersection(separate_visible)
        assert len(overlap) == 0, f"Found data overlap between isolated tenants: {overlap}"

    async def test_performance_impact_measurement(self, db_session: AsyncSession, test_tenants: Dict[str, Tenant]):
        """Measure performance impact of RLS policies."""
        import time
        
        parent = test_tenants["parent"]
        await db_session.execute(text(f"SELECT set_tenant_context('{parent.tenant_id}')"))
        
        # Warm up
        for _ in range(5):
            await db_session.execute(text("SELECT COUNT(*) FROM tenants"))
        
        # Measure RLS query performance
        start_time = time.time()
        for _ in range(100):
            await db_session.execute(text("SELECT * FROM tenants ORDER BY name"))
        rls_time = time.time() - start_time
        
        logger.info(f"RLS query performance: {rls_time:.4f}s for 100 queries")
        
        # Basic performance assertion (should complete within reasonable time)
        assert rls_time < 5.0, f"RLS queries taking too long: {rls_time:.4f}s"