"""
Integration tests for Row Level Security (RLS) policies.

Tests RLS policies work correctly with real database operations
and tenant context switching.
"""

from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.multi_tenant_db.models.tenant import Tenant


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.tenant
class TestRLSPolicyIntegration:
    """Integration tests for RLS policy enforcement."""

    async def test_rls_tenant_context_functions(
        self,
        db_connection: AsyncConnection,
    ) -> None:
        """Test RLS tenant context functions work correctly."""
        # Test setting tenant context
        test_tenant_id = "11111111-1111-1111-1111-111111111111"
        
        result = await db_connection.execute(
            text("SELECT set_current_tenant_id(:tenant_id)"),
            {"tenant_id": test_tenant_id}
        )
        assert result.scalar() is True

        # Test getting current tenant context
        result = await db_connection.execute(
            text("SELECT get_current_tenant_id()")
        )
        current_tenant_id = result.scalar()
        assert current_tenant_id == test_tenant_id

        # Test clearing tenant context
        result = await db_connection.execute(
            text("SELECT clear_current_tenant_id()")
        )
        assert result.scalar() is True

        # Verify context is cleared
        result = await db_connection.execute(
            text("SELECT get_current_tenant_id()")
        )
        current_tenant_id = result.scalar()
        assert current_tenant_id is None

    async def test_rls_policy_enforcement_parent_tenant(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        hsbc_hk_subsidiary: Tenant,
        barclays_parent_tenant: Tenant,
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """Test RLS policy enforcement for parent tenant access."""
        # Set HSBC parent context
        await set_tenant_context(integration_db_session, hsbc_parent_tenant.tenant_id)

        # Parent should see itself and its subsidiaries
        result = await integration_db_session.execute(
            text("SELECT tenant_id, name FROM tenants ORDER BY created_at")
        )
        visible_tenants = result.fetchall()
        
        visible_tenant_ids = {UUID(str(row[0])) for row in visible_tenants}
        expected_tenant_ids = {hsbc_parent_tenant.tenant_id, hsbc_hk_subsidiary.tenant_id}
        
        assert expected_tenant_ids.issubset(visible_tenant_ids)
        assert barclays_parent_tenant.tenant_id not in visible_tenant_ids

        await clear_tenant_context(integration_db_session)

    async def test_rls_policy_enforcement_subsidiary_tenant(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        hsbc_hk_subsidiary: Tenant,
        hsbc_london_subsidiary: Tenant,
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """Test RLS policy enforcement for subsidiary tenant access."""
        # Set HSBC HK subsidiary context
        await set_tenant_context(integration_db_session, hsbc_hk_subsidiary.tenant_id)

        # Subsidiary should only see itself
        result = await integration_db_session.execute(
            text("SELECT tenant_id, name FROM tenants")
        )
        visible_tenants = result.fetchall()
        
        visible_tenant_ids = {UUID(str(row[0])) for row in visible_tenants}
        
        # Should only see itself
        assert visible_tenant_ids == {hsbc_hk_subsidiary.tenant_id}
        
        # Should not see parent or sibling
        assert hsbc_parent_tenant.tenant_id not in visible_tenant_ids
        assert hsbc_london_subsidiary.tenant_id not in visible_tenant_ids

        await clear_tenant_context(integration_db_session)

    async def test_rls_policy_cross_tenant_isolation(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        barclays_parent_tenant: Tenant,
        barclays_us_subsidiary: Tenant,
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """Test complete isolation between different tenant hierarchies."""
        # Set HSBC context
        await set_tenant_context(integration_db_session, hsbc_parent_tenant.tenant_id)

        result = await integration_db_session.execute(
            text("SELECT tenant_id FROM tenants")
        )
        hsbc_visible = {UUID(str(row[0])) for row in result.fetchall()}

        # Set Barclays context
        await set_tenant_context(integration_db_session, barclays_parent_tenant.tenant_id)

        result = await integration_db_session.execute(
            text("SELECT tenant_id FROM tenants")
        )
        barclays_visible = {UUID(str(row[0])) for row in result.fetchall()}

        # Verify complete isolation - no overlap
        assert len(hsbc_visible.intersection(barclays_visible)) == 0
        
        # Verify each sees their own tenants
        assert hsbc_parent_tenant.tenant_id in hsbc_visible
        assert barclays_parent_tenant.tenant_id in barclays_visible
        assert barclays_us_subsidiary.tenant_id in barclays_visible
        
        # Verify they don't see each other
        assert barclays_parent_tenant.tenant_id not in hsbc_visible
        assert hsbc_parent_tenant.tenant_id not in barclays_visible

        await clear_tenant_context(integration_db_session)

    async def test_rls_policy_with_direct_sql_operations(
        self,
        db_connection: AsyncConnection,
        hsbc_parent_tenant: Tenant,
        barclays_parent_tenant: Tenant,
    ) -> None:
        """Test RLS policies work with direct SQL operations."""
        # Set HSBC context using direct connection
        await db_connection.execute(
            text("SELECT set_current_tenant_id(:tenant_id)"),
            {"tenant_id": str(hsbc_parent_tenant.tenant_id)}
        )

        # Try to access Barclays tenant directly via SQL
        result = await db_connection.execute(
            text("SELECT name FROM tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(barclays_parent_tenant.tenant_id)}
        )
        
        # Should return no results due to RLS
        barclays_data = result.fetchone()
        assert barclays_data is None

        # Should be able to access own tenant
        result = await db_connection.execute(
            text("SELECT name FROM tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(hsbc_parent_tenant.tenant_id)}
        )
        
        hsbc_data = result.fetchone()
        assert hsbc_data is not None
        assert hsbc_data[0] == hsbc_parent_tenant.name

    async def test_rls_policy_insert_operations(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """Test RLS policies during insert operations."""
        # Set HSBC context
        await set_tenant_context(integration_db_session, hsbc_parent_tenant.tenant_id)

        # Insert new subsidiary tenant
        new_tenant_id = "11111111-1111-1111-1111-999999999999"
        
        await integration_db_session.execute(
            text("""
                INSERT INTO tenants (tenant_id, name, parent_tenant_id, tenant_type, tenant_metadata)
                VALUES (:tenant_id, :name, :parent_id, :tenant_type, :metadata)
            """),
            {
                "tenant_id": new_tenant_id,
                "name": "HSBC Test Subsidiary",
                "parent_id": str(hsbc_parent_tenant.tenant_id),
                "tenant_type": "subsidiary",
                "metadata": '{"test": "rls_insert"}'
            }
        )
        
        await integration_db_session.commit()

        # Verify the new tenant is visible in HSBC context
        result = await integration_db_session.execute(
            text("SELECT name FROM tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": new_tenant_id}
        )
        
        new_tenant = result.fetchone()
        assert new_tenant is not None
        assert new_tenant[0] == "HSBC Test Subsidiary"

        await clear_tenant_context(integration_db_session)

    async def test_rls_policy_update_operations(
        self,
        integration_db_session: AsyncSession,
        hsbc_hk_subsidiary: Tenant,
        barclays_parent_tenant: Tenant,
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """Test RLS policies during update operations."""
        # Set HSBC parent context (should be able to update subsidiary)
        await set_tenant_context(integration_db_session, hsbc_hk_subsidiary.parent_tenant_id)

        # Update HSBC subsidiary - should succeed
        await integration_db_session.execute(
            text("""
                UPDATE tenants 
                SET name = :new_name 
                WHERE tenant_id = :tenant_id
            """),
            {
                "new_name": "HSBC Hong Kong Updated via RLS",
                "tenant_id": str(hsbc_hk_subsidiary.tenant_id)
            }
        )
        
        await integration_db_session.commit()

        # Verify update succeeded
        result = await integration_db_session.execute(
            text("SELECT name FROM tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(hsbc_hk_subsidiary.tenant_id)}
        )
        
        updated_tenant = result.fetchone()
        assert updated_tenant[0] == "HSBC Hong Kong Updated via RLS"

        # Try to update Barclays tenant - should fail (no rows affected)
        result = await integration_db_session.execute(
            text("""
                UPDATE tenants 
                SET name = :new_name 
                WHERE tenant_id = :tenant_id
            """),
            {
                "new_name": "Malicious Update Attempt",
                "tenant_id": str(barclays_parent_tenant.tenant_id)
            }
        )
        
        assert result.rowcount == 0  # No rows were updated

        await clear_tenant_context(integration_db_session)

    async def test_rls_policy_delete_operations(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        barclays_parent_tenant: Tenant,
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """Test RLS policies during delete operations."""
        # Create a test tenant for deletion
        test_tenant_id = "11111111-1111-1111-1111-888888888888"
        
        await integration_db_session.execute(
            text("""
                INSERT INTO tenants (tenant_id, name, parent_tenant_id, tenant_type, tenant_metadata)
                VALUES (:tenant_id, :name, :parent_id, :tenant_type, :metadata)
            """),
            {
                "tenant_id": test_tenant_id,
                "name": "HSBC Test for Deletion",
                "parent_id": str(hsbc_parent_tenant.tenant_id),
                "tenant_type": "subsidiary",
                "metadata": '{"test": "deletion"}'
            }
        )
        await integration_db_session.commit()

        # Set HSBC parent context
        await set_tenant_context(integration_db_session, hsbc_parent_tenant.tenant_id)

        # Should be able to delete own subsidiary
        result = await integration_db_session.execute(
            text("DELETE FROM tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": test_tenant_id}
        )
        
        assert result.rowcount == 1  # One row was deleted
        await integration_db_session.commit()

        # Try to delete Barclays tenant - should fail
        result = await integration_db_session.execute(
            text("DELETE FROM tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(barclays_parent_tenant.tenant_id)}
        )
        
        assert result.rowcount == 0  # No rows were deleted

        await clear_tenant_context(integration_db_session)

    async def test_rls_policy_performance_impact(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        hsbc_hk_subsidiary: Tenant,
        hsbc_london_subsidiary: Tenant,
        set_tenant_context,
        clear_tenant_context,
        performance_threshold_ms: int,
    ) -> None:
        """Test RLS policy performance impact on queries."""
        import time

        # Set tenant context
        await set_tenant_context(integration_db_session, hsbc_parent_tenant.tenant_id)

        # Time multiple queries with RLS
        query_times = []
        
        for _ in range(10):
            start_time = time.time()
            
            result = await integration_db_session.execute(
                text("SELECT tenant_id, name, tenant_type FROM tenants ORDER BY created_at")
            )
            _ = result.fetchall()
            
            end_time = time.time()
            query_time_ms = (end_time - start_time) * 1000
            query_times.append(query_time_ms)

        # Validate query performance
        avg_query_time = sum(query_times) / len(query_times)
        max_query_time = max(query_times)
        
        # RLS queries should still be fast (within 2x threshold)
        assert avg_query_time <= performance_threshold_ms * 2
        assert max_query_time <= performance_threshold_ms * 3

        await clear_tenant_context(integration_db_session)

    async def test_rls_policy_complex_queries(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        hsbc_hk_subsidiary: Tenant,
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """Test RLS policies with complex queries and joins."""
        # Set HSBC parent context
        await set_tenant_context(integration_db_session, hsbc_parent_tenant.tenant_id)

        # Complex query with subqueries and aggregations
        result = await integration_db_session.execute(
            text("""
                SELECT 
                    t1.tenant_type,
                    COUNT(*) as tenant_count,
                    array_agg(t1.name ORDER BY t1.name) as tenant_names,
                    (
                        SELECT COUNT(*) 
                        FROM tenants t2 
                        WHERE t2.parent_tenant_id = t1.tenant_id
                    ) as subsidiary_count
                FROM tenants t1
                GROUP BY t1.tenant_type
                ORDER BY t1.tenant_type
            """)
        )
        
        results = result.fetchall()
        assert len(results) > 0
        
        # Should see both parent and subsidiary types in HSBC context
        tenant_types = {row[0] for row in results}
        assert "parent" in tenant_types
        assert "subsidiary" in tenant_types

        # Verify specific counts based on our test data
        for row in results:
            tenant_type, count, names, subsidiary_count = row
            if tenant_type == "parent":
                assert count >= 1  # At least HSBC parent
                assert hsbc_parent_tenant.name in names
            elif tenant_type == "subsidiary":
                assert count >= 1  # At least HSBC HK subsidiary
                assert hsbc_hk_subsidiary.name in names

        await clear_tenant_context(integration_db_session)

    async def test_rls_policy_error_handling(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """Test RLS policy behavior during error conditions."""
        # Test with invalid tenant ID
        try:
            await set_tenant_context(integration_db_session, "invalid-uuid")
            # Should handle gracefully, queries should return empty results
            result = await integration_db_session.execute(
                text("SELECT COUNT(*) FROM tenants")
            )
            count = result.scalar()
            assert count == 0  # No tenants visible with invalid context
        finally:
            await clear_tenant_context(integration_db_session)

        # Test with valid context after error
        await set_tenant_context(integration_db_session, hsbc_parent_tenant.tenant_id)
        
        result = await integration_db_session.execute(
            text("SELECT COUNT(*) FROM tenants")
        )
        count = result.scalar()
        assert count > 0  # Should see tenants again

        await clear_tenant_context(integration_db_session)


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.tenant
class TestRLSTransactionIntegration:
    """Integration tests for RLS behavior within transactions."""

    async def test_rls_context_within_transaction(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """Test RLS context behavior within database transactions."""
        # Begin explicit transaction
        await integration_db_session.begin()
        
        try:
            # Set tenant context within transaction
            await set_tenant_context(integration_db_session, hsbc_parent_tenant.tenant_id)
            
            # Insert new tenant within transaction
            new_tenant_id = "11111111-1111-1111-1111-777777777777"
            
            await integration_db_session.execute(
                text("""
                    INSERT INTO tenants (tenant_id, name, parent_tenant_id, tenant_type, tenant_metadata)
                    VALUES (:tenant_id, :name, :parent_id, :tenant_type, :metadata)
                """),
                {
                    "tenant_id": new_tenant_id,
                    "name": "HSBC Transaction Test",
                    "parent_id": str(hsbc_parent_tenant.tenant_id),
                    "tenant_type": "subsidiary",
                    "metadata": '{"test": "transaction"}'
                }
            )
            
            # Verify tenant is visible within same transaction
            result = await integration_db_session.execute(
                text("SELECT name FROM tenants WHERE tenant_id = :tenant_id"),
                {"tenant_id": new_tenant_id}
            )
            
            tenant = result.fetchone()
            assert tenant is not None
            assert tenant[0] == "HSBC Transaction Test"
            
            # Commit transaction
            await integration_db_session.commit()
            
        except Exception:
            # Rollback on any error
            await integration_db_session.rollback()
            raise
        finally:
            await clear_tenant_context(integration_db_session)

    async def test_rls_context_rollback_behavior(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """Test RLS context behavior during transaction rollback."""
        # Set tenant context
        await set_tenant_context(integration_db_session, hsbc_parent_tenant.tenant_id)
        
        # Begin transaction that we'll rollback
        await integration_db_session.begin()
        
        try:
            # Insert tenant within transaction
            rollback_tenant_id = "11111111-1111-1111-1111-666666666666"
            
            await integration_db_session.execute(
                text("""
                    INSERT INTO tenants (tenant_id, name, parent_tenant_id, tenant_type, tenant_metadata)
                    VALUES (:tenant_id, :name, :parent_id, :tenant_type, :metadata)
                """),
                {
                    "tenant_id": rollback_tenant_id,
                    "name": "HSBC Rollback Test",
                    "parent_id": str(hsbc_parent_tenant.tenant_id),
                    "tenant_type": "subsidiary",
                    "metadata": '{"test": "rollback"}'
                }
            )
            
            # Verify tenant is visible within transaction
            result = await integration_db_session.execute(
                text("SELECT name FROM tenants WHERE tenant_id = :tenant_id"),
                {"tenant_id": rollback_tenant_id}
            )
            
            tenant = result.fetchone()
            assert tenant is not None
            
            # Rollback transaction
            await integration_db_session.rollback()
            
        except Exception:
            await integration_db_session.rollback()
            raise

        # Start new transaction to verify rollback worked
        await integration_db_session.begin()
        
        try:
            # Tenant should not exist after rollback
            result = await integration_db_session.execute(
                text("SELECT name FROM tenants WHERE tenant_id = :tenant_id"),
                {"tenant_id": rollback_tenant_id}
            )
            
            tenant = result.fetchone()
            assert tenant is None  # Should be None due to rollback
            
            await integration_db_session.commit()
            
        except Exception:
            await integration_db_session.rollback()
            raise
        finally:
            await clear_tenant_context(integration_db_session)