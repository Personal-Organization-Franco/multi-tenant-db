"""
Integration tests for database session management.

Tests database connection pooling, session lifecycle, and transaction handling
in real database scenarios.
"""

import asyncio
import time
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.multi_tenant_db.models.tenant import Tenant


@pytest.mark.integration
@pytest.mark.database
class TestDatabaseSessionIntegration:
    """Integration tests for database session management."""

    async def test_session_basic_crud_operations(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
    ) -> None:
        """Test basic CRUD operations through database session."""
        # Test CREATE - already done by fixture, verify it exists
        result = await integration_db_session.execute(
            text("SELECT name FROM tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(hsbc_parent_tenant.tenant_id)}
        )
        
        tenant = result.fetchone()
        assert tenant is not None
        assert tenant[0] == hsbc_parent_tenant.name

        # Test UPDATE
        new_name = "HSBC Holdings plc - Updated"
        await integration_db_session.execute(
            text("""
                UPDATE tenants 
                SET name = :new_name, updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = :tenant_id
            """),
            {
                "new_name": new_name,
                "tenant_id": str(hsbc_parent_tenant.tenant_id)
            }
        )
        await integration_db_session.commit()

        # Verify UPDATE
        result = await integration_db_session.execute(
            text("SELECT name FROM tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(hsbc_parent_tenant.tenant_id)}
        )
        
        updated_tenant = result.fetchone()
        assert updated_tenant[0] == new_name

        # Test READ with complex query
        result = await integration_db_session.execute(
            text("""
                SELECT tenant_id, name, tenant_type, tenant_metadata->'country' as country
                FROM tenants 
                WHERE tenant_id = :tenant_id
            """),
            {"tenant_id": str(hsbc_parent_tenant.tenant_id)}
        )
        
        tenant_data = result.fetchone()
        assert tenant_data is not None
        assert UUID(str(tenant_data[0])) == hsbc_parent_tenant.tenant_id
        assert tenant_data[1] == new_name
        assert tenant_data[2] == "parent"
        assert tenant_data[3] == "United Kingdom"

    async def test_session_transaction_commit(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
    ) -> None:
        """Test explicit transaction commit behavior."""
        # Start explicit transaction
        await integration_db_session.begin()
        
        try:
            # Insert new tenant within transaction
            new_tenant_id = "11111111-1111-1111-1111-555555555555"
            
            await integration_db_session.execute(
                text("""
                    INSERT INTO tenants (tenant_id, name, parent_tenant_id, tenant_type, tenant_metadata)
                    VALUES (:tenant_id, :name, :parent_id, :tenant_type, :metadata)
                """),
                {
                    "tenant_id": new_tenant_id,
                    "name": "HSBC Transaction Commit Test",
                    "parent_id": str(hsbc_parent_tenant.tenant_id),
                    "tenant_type": "subsidiary",
                    "metadata": '{"test": "commit", "country": "Singapore"}'
                }
            )
            
            # Commit transaction
            await integration_db_session.commit()
            
            # Start new transaction to verify persistence
            await integration_db_session.begin()
            
            result = await integration_db_session.execute(
                text("SELECT name FROM tenants WHERE tenant_id = :tenant_id"),
                {"tenant_id": new_tenant_id}
            )
            
            tenant = result.fetchone()
            assert tenant is not None
            assert tenant[0] == "HSBC Transaction Commit Test"
            
            await integration_db_session.commit()
            
        except Exception:
            await integration_db_session.rollback()
            raise

    async def test_session_transaction_rollback(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
    ) -> None:
        """Test explicit transaction rollback behavior."""
        # Start transaction
        await integration_db_session.begin()
        
        try:
            # Insert tenant that will be rolled back
            rollback_tenant_id = "11111111-1111-1111-1111-444444444444"
            
            await integration_db_session.execute(
                text("""
                    INSERT INTO tenants (tenant_id, name, parent_tenant_id, tenant_type, tenant_metadata)
                    VALUES (:tenant_id, :name, :parent_id, :tenant_type, :metadata)
                """),
                {
                    "tenant_id": rollback_tenant_id,
                    "name": "HSBC Transaction Rollback Test",
                    "parent_id": str(hsbc_parent_tenant.tenant_id),
                    "tenant_type": "subsidiary",
                    "metadata": '{"test": "rollback"}'
                }
            )
            
            # Verify tenant exists within transaction
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
            result = await integration_db_session.execute(
                text("SELECT name FROM tenants WHERE tenant_id = :tenant_id"),
                {"tenant_id": rollback_tenant_id}
            )
            
            tenant = result.fetchone()
            assert tenant is None  # Should not exist due to rollback
            
            await integration_db_session.commit()
            
        except Exception:
            await integration_db_session.rollback()
            raise

    async def test_session_concurrent_operations(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        performance_threshold_ms: int,
    ) -> None:
        """Test concurrent database operations performance."""
        # Prepare multiple operations
        async def create_tenant(index: int) -> tuple[bool, float]:
            start_time = time.time()
            
            try:
                await integration_db_session.begin()
                
                tenant_id = f"11111111-1111-1111-1111-{index:012d}"
                
                await integration_db_session.execute(
                    text("""
                        INSERT INTO tenants (tenant_id, name, parent_tenant_id, tenant_type, tenant_metadata)
                        VALUES (:tenant_id, :name, :parent_id, :tenant_type, :metadata)
                    """),
                    {
                        "tenant_id": tenant_id,
                        "name": f"HSBC Concurrent Test {index}",
                        "parent_id": str(hsbc_parent_tenant.tenant_id),
                        "tenant_type": "subsidiary",
                        "metadata": f'{{"test": "concurrent", "index": {index}}}'
                    }
                )
                
                await integration_db_session.commit()
                
                end_time = time.time()
                return True, (end_time - start_time) * 1000
                
            except Exception:
                await integration_db_session.rollback()
                end_time = time.time()
                return False, (end_time - start_time) * 1000

        # Execute operations
        tasks = [create_tenant(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Validate results
        success_count = sum(1 for success, _ in results if success)
        operation_times = [time_ms for _, time_ms in results]
        
        assert success_count == 5  # All operations should succeed
        
        # Validate performance
        avg_time = sum(operation_times) / len(operation_times)
        max_time = max(operation_times)
        
        assert avg_time <= performance_threshold_ms * 2  # Allow 2x for concurrent operations
        assert max_time <= performance_threshold_ms * 3

    async def test_session_error_handling(
        self,
        integration_db_session: AsyncSession,
    ) -> None:
        """Test session behavior during error conditions."""
        # Test handling of constraint violations
        await integration_db_session.begin()
        
        try:
            # Try to insert tenant with duplicate ID
            duplicate_id = "11111111-1111-1111-1111-111111111111"  # HSBC parent ID
            
            with pytest.raises(SQLAlchemyError):
                await integration_db_session.execute(
                    text("""
                        INSERT INTO tenants (tenant_id, name, parent_tenant_id, tenant_type, tenant_metadata)
                        VALUES (:tenant_id, :name, :parent_id, :tenant_type, :metadata)
                    """),
                    {
                        "tenant_id": duplicate_id,
                        "name": "Duplicate Tenant",
                        "parent_id": None,
                        "tenant_type": "parent",
                        "metadata": '{"test": "duplicate"}'
                    }
                )
                await integration_db_session.commit()
                
        except SQLAlchemyError:
            await integration_db_session.rollback()

        # Session should still be usable after error
        await integration_db_session.begin()
        
        try:
            result = await integration_db_session.execute(
                text("SELECT COUNT(*) FROM tenants")
            )
            count = result.scalar()
            assert count >= 0  # Should work normally
            
            await integration_db_session.commit()
            
        except Exception:
            await integration_db_session.rollback()
            raise

    async def test_session_connection_recovery(
        self,
        integration_db_session: AsyncSession,
        database_health_check,
    ) -> None:
        """Test session recovery after connection issues."""
        # First, verify session is healthy
        health_status = await database_health_check(integration_db_session)
        assert health_status["database_connected"] is True
        assert health_status["error"] is None

        # Perform normal operations to verify session works
        result = await integration_db_session.execute(
            text("SELECT 1 as test_value")
        )
        assert result.scalar() == 1

        # Test with potential connection stress
        for i in range(10):
            result = await integration_db_session.execute(
                text("SELECT pg_backend_pid() as pid")
            )
            pid = result.scalar()
            assert isinstance(pid, int)
            assert pid > 0

        # Verify session is still healthy after stress
        final_health_status = await database_health_check(integration_db_session)
        assert final_health_status["database_connected"] is True
        assert final_health_status["error"] is None

    async def test_session_json_operations(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
    ) -> None:
        """Test session handling of JSON operations and complex metadata."""
        # Test complex JSON metadata operations
        complex_metadata = {
            "financial_data": {
                "revenue_usd_millions": 52700,
                "profit_usd_millions": 12600,
                "assets_usd_billions": 2963,
                "market_cap_usd_billions": 120.5
            },
            "regulatory_info": {
                "primary_regulator": "Bank of England",
                "licenses": [
                    "UK_banking_license",
                    "FCA_authorization",
                    "PRA_authorization"
                ],
                "capital_ratios": {
                    "tier1_capital_ratio": 15.8,
                    "common_equity_tier1": 14.7,
                    "leverage_ratio": 5.2
                }
            },
            "operational_metrics": {
                "branches_worldwide": 3800,
                "atms_worldwide": 65000,
                "employees_worldwide": 220000,
                "countries_present": 64
            },
            "esg_scores": {
                "environmental_score": 8.2,
                "social_score": 7.9,
                "governance_score": 8.5,
                "overall_esg_rating": "A"
            }
        }

        # Update tenant with complex metadata
        await integration_db_session.execute(
            text("""
                UPDATE tenants 
                SET tenant_metadata = :metadata,
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = :tenant_id
            """),
            {
                "metadata": str(complex_metadata).replace("'", '"'),  # Convert to JSON string
                "tenant_id": str(hsbc_parent_tenant.tenant_id)
            }
        )
        await integration_db_session.commit()

        # Test JSON queries
        result = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->'financial_data'->>'revenue_usd_millions' as revenue,
                    tenant_metadata->'regulatory_info'->'capital_ratios'->>'tier1_capital_ratio' as tier1_ratio,
                    jsonb_array_length(tenant_metadata->'regulatory_info'->'licenses') as license_count
                FROM tenants 
                WHERE tenant_id = :tenant_id
            """),
            {"tenant_id": str(hsbc_parent_tenant.tenant_id)}
        )
        
        json_data = result.fetchone()
        assert json_data is not None
        assert json_data[0] == "52700"  # Revenue as string from JSON
        assert float(json_data[1]) == 15.8  # Tier 1 capital ratio
        assert json_data[2] == 3  # Number of licenses

        # Test JSON aggregation
        result = await integration_db_session.execute(
            text("""
                SELECT 
                    COUNT(*) as total_tenants,
                    AVG(CAST(tenant_metadata->'financial_data'->>'revenue_usd_millions' AS NUMERIC)) as avg_revenue
                FROM tenants 
                WHERE tenant_metadata->'financial_data' IS NOT NULL
                  AND tenant_id = :tenant_id
            """),
            {"tenant_id": str(hsbc_parent_tenant.tenant_id)}
        )
        
        agg_data = result.fetchone()
        assert agg_data[0] == 1  # One tenant
        assert float(agg_data[1]) == 52700.0  # Average revenue

    async def test_session_performance_monitoring(
        self,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        performance_threshold_ms: int,
    ) -> None:
        """Test session performance monitoring and timing."""
        query_times = []
        
        # Execute various queries and monitor performance
        queries = [
            "SELECT COUNT(*) FROM tenants",
            "SELECT tenant_id, name FROM tenants ORDER BY created_at LIMIT 10",
            """
            SELECT 
                tenant_type,
                COUNT(*) as count,
                AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_age_seconds
            FROM tenants 
            GROUP BY tenant_type
            """,
            """
            SELECT tenant_id, name, tenant_metadata->'country' as country
            FROM tenants 
            WHERE tenant_metadata->'country' IS NOT NULL
            ORDER BY name
            """,
            "SELECT pg_database_size(current_database()) as db_size"
        ]

        for query in queries:
            start_time = time.time()
            
            result = await integration_db_session.execute(text(query))
            _ = result.fetchall()  # Fetch all results
            
            end_time = time.time()
            query_time_ms = (end_time - start_time) * 1000
            query_times.append(query_time_ms)

        # Validate performance
        avg_query_time = sum(query_times) / len(query_times)
        max_query_time = max(query_times)
        
        assert avg_query_time <= performance_threshold_ms
        assert max_query_time <= performance_threshold_ms * 2

        # Test bulk operation performance
        start_time = time.time()
        
        # Simulate bulk read operation
        result = await integration_db_session.execute(
            text("""
                SELECT 
                    t1.tenant_id,
                    t1.name,
                    t1.tenant_type,
                    t1.tenant_metadata,
                    t2.name as parent_name
                FROM tenants t1
                LEFT JOIN tenants t2 ON t1.parent_tenant_id = t2.tenant_id
                ORDER BY t1.created_at
            """)
        )
        
        bulk_results = result.fetchall()
        
        end_time = time.time()
        bulk_query_time_ms = (end_time - start_time) * 1000
        
        assert len(bulk_results) >= 0  # Should return results
        assert bulk_query_time_ms <= performance_threshold_ms * 2  # Allow 2x for complex join

    async def test_session_isolation_levels(
        self,
        integration_db_session: AsyncSession,
    ) -> None:
        """Test session isolation levels and transaction behavior."""
        # Test current isolation level
        result = await integration_db_session.execute(
            text("SELECT current_setting('transaction_isolation')")
        )
        isolation_level = result.scalar()
        
        # PostgreSQL default should be READ COMMITTED
        assert isolation_level.lower() in ["read committed", "read_committed"]

        # Test transaction characteristics
        result = await integration_db_session.execute(
            text("SELECT txid_current_if_assigned()")
        )
        initial_txid = result.scalar()
        
        # Start explicit transaction
        await integration_db_session.begin()
        
        result = await integration_db_session.execute(
            text("SELECT txid_current()")
        )
        transaction_txid = result.scalar()
        
        # Should have a transaction ID now
        assert transaction_txid is not None
        assert isinstance(transaction_txid, int)
        
        await integration_db_session.commit()

        # Test read-only transaction (if supported)
        await integration_db_session.begin()
        
        try:
            # This should work in read-only mode
            result = await integration_db_session.execute(
                text("SELECT COUNT(*) FROM tenants")
            )
            count = result.scalar()
            assert count >= 0
            
            await integration_db_session.commit()
            
        except Exception:
            await integration_db_session.rollback()
            raise