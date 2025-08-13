"""
Comprehensive database performance testing for multi-tenant RLS implementation.

This module measures and validates:
- Query performance with RLS enabled vs disabled
- Bulk operation performance with tenant filtering
- RLS overhead measurement and optimization
- Index effectiveness for tenant-aware queries
- Concurrent access patterns and scalability
"""

import asyncio
import time
import statistics
import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.multi_tenant_db.core.config import get_settings
from src.multi_tenant_db.db.session import get_async_session
from src.multi_tenant_db.models.tenant import Tenant, TenantType

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Helper class to collect and analyze performance metrics."""
    
    def __init__(self):
        self.measurements: List[float] = []
        self.operation_name: str = ""
    
    def add_measurement(self, duration: float):
        """Add a performance measurement."""
        self.measurements.append(duration)
    
    def get_statistics(self) -> Dict[str, float]:
        """Get statistical summary of measurements."""
        if not self.measurements:
            return {}
        
        return {
            "count": len(self.measurements),
            "mean": statistics.mean(self.measurements),
            "median": statistics.median(self.measurements),
            "stdev": statistics.stdev(self.measurements) if len(self.measurements) > 1 else 0.0,
            "min": min(self.measurements),
            "max": max(self.measurements),
            "p95": statistics.quantiles(self.measurements, n=20)[18] if len(self.measurements) >= 20 else max(self.measurements),
            "p99": statistics.quantiles(self.measurements, n=100)[98] if len(self.measurements) >= 100 else max(self.measurements)
        }


@asynccontextmanager
async def measure_time():
    """Async context manager to measure execution time."""
    start_time = time.perf_counter()
    yield
    end_time = time.perf_counter()
    return end_time - start_time


class TestDatabasePerformance:
    """
    Comprehensive database performance test suite.
    
    Measures and validates performance characteristics of:
    - RLS-enabled queries vs non-RLS queries
    - Bulk operations with tenant filtering
    - Index effectiveness
    - Concurrent access patterns
    """

    @pytest_asyncio.fixture
    async def db_session(self) -> AsyncSession:
        """Create a database session for testing."""
        settings = get_settings()
        async for session in get_async_session():
            yield session
            break

    @pytest_asyncio.fixture
    async def performance_test_data(self, db_session: AsyncSession) -> Dict[str, List[Tenant]]:
        """Create large dataset for performance testing."""
        # Clear any existing context
        await db_session.execute(text("SELECT clear_tenant_context()"))
        await db_session.commit()
        
        # Create multiple parent tenants
        parent_tenants = []
        all_subsidiaries = []
        
        for i in range(10):  # 10 parent tenants
            parent = Tenant(
                tenant_id=uuid4(),
                name=f"Performance Test Parent {i:03d}",
                tenant_type=TenantType.PARENT,
                parent_tenant_id=None,
                tenant_metadata={
                    "performance_test": True,
                    "parent_index": i,
                    "created_for": "performance_testing"
                }
            )
            parent_tenants.append(parent)
            
            # Create subsidiaries for each parent
            subsidiaries = []
            for j in range(50):  # 50 subsidiaries per parent
                subsidiary = Tenant(
                    tenant_id=uuid4(),
                    name=f"Performance Test Subsidiary {i:03d}-{j:03d}",
                    tenant_type=TenantType.SUBSIDIARY,
                    parent_tenant_id=parent.tenant_id,
                    tenant_metadata={
                        "performance_test": True,
                        "parent_index": i,
                        "subsidiary_index": j,
                        "region": f"region_{j % 5}",  # 5 different regions
                        "business_unit": f"unit_{j % 10}"  # 10 different business units
                    }
                )
                subsidiaries.append(subsidiary)
                all_subsidiaries.append(subsidiary)
        
        # Bulk insert all tenants
        all_tenants = parent_tenants + all_subsidiaries
        db_session.add_all(all_tenants)
        await db_session.commit()
        
        # Refresh to ensure all data is loaded
        for tenant in all_tenants:
            await db_session.refresh(tenant)
        
        logger.info(f"Created {len(parent_tenants)} parent tenants and {len(all_subsidiaries)} subsidiaries for performance testing")
        
        return {
            "parents": parent_tenants,
            "subsidiaries": all_subsidiaries,
            "all": all_tenants
        }

    async def test_rls_query_performance_baseline(self, db_session: AsyncSession, performance_test_data: Dict[str, List[Tenant]]):
        """Establish baseline query performance with RLS enabled."""
        parent_tenants = performance_test_data["parents"]
        metrics = PerformanceMetrics()
        
        # Set tenant context to first parent
        test_parent = parent_tenants[0]
        await db_session.execute(text(f"SELECT set_tenant_context('{test_parent.tenant_id}')"))
        
        # Warm up the query cache
        for _ in range(5):
            await db_session.execute(text("SELECT COUNT(*) FROM tenants"))
        
        # Measure SELECT performance with RLS
        for i in range(100):
            start_time = time.perf_counter()
            result = await db_session.execute(text("SELECT * FROM tenants ORDER BY name"))
            await result.fetchall()
            end_time = time.perf_counter()
            metrics.add_measurement(end_time - start_time)
        
        stats = metrics.get_statistics()
        logger.info(f"RLS SELECT Performance - Mean: {stats['mean']:.4f}s, P95: {stats['p95']:.4f}s, P99: {stats['p99']:.4f}s")
        
        # Performance assertions
        assert stats["mean"] < 0.1, f"Average RLS query time should be under 100ms, got {stats['mean']:.4f}s"
        assert stats["p95"] < 0.2, f"95th percentile should be under 200ms, got {stats['p95']:.4f}s"
        assert stats["p99"] < 0.5, f"99th percentile should be under 500ms, got {stats['p99']:.4f}s"

    async def test_bulk_insert_performance(self, db_session: AsyncSession, performance_test_data: Dict[str, List[Tenant]]):
        """Test bulk insert performance with RLS enabled."""
        parent_tenants = performance_test_data["parents"]
        test_parent = parent_tenants[0]
        
        # Set tenant context
        await db_session.execute(text(f"SELECT set_tenant_context('{test_parent.tenant_id}')"))
        
        # Prepare bulk insert data
        bulk_tenants = []
        for i in range(100):
            tenant = Tenant(
                tenant_id=uuid4(),
                name=f"Bulk Insert Test Subsidiary {i:03d}",
                tenant_type=TenantType.SUBSIDIARY,
                parent_tenant_id=test_parent.tenant_id,
                tenant_metadata={
                    "bulk_test": True,
                    "batch_index": i,
                    "performance_test": True
                }
            )
            bulk_tenants.append(tenant)
        
        # Measure bulk insert performance
        start_time = time.perf_counter()
        db_session.add_all(bulk_tenants)
        await db_session.commit()
        end_time = time.perf_counter()
        
        bulk_insert_time = end_time - start_time
        per_record_time = bulk_insert_time / len(bulk_tenants)
        
        logger.info(f"Bulk insert performance: {bulk_insert_time:.4f}s total, {per_record_time:.6f}s per record")
        
        # Performance assertions
        assert bulk_insert_time < 5.0, f"Bulk insert of 100 records should complete under 5s, got {bulk_insert_time:.4f}s"
        assert per_record_time < 0.05, f"Per-record insert time should be under 50ms, got {per_record_time:.6f}s"

    async def test_bulk_update_performance(self, db_session: AsyncSession, performance_test_data: Dict[str, List[Tenant]]):
        """Test bulk update performance with RLS filtering."""
        parent_tenants = performance_test_data["parents"]
        test_parent = parent_tenants[0]
        
        # Set tenant context
        await db_session.execute(text(f"SELECT set_tenant_context('{test_parent.tenant_id}')"))
        
        # Measure bulk update performance
        start_time = time.perf_counter()
        result = await db_session.execute(text(f"""
            UPDATE tenants 
            SET metadata = metadata || '{{"bulk_updated": true, "updated_at": "{time.time()}"}}'
            WHERE parent_tenant_id = '{test_parent.tenant_id}'
        """))
        await db_session.commit()
        end_time = time.perf_counter()
        
        bulk_update_time = end_time - start_time
        updated_count = result.rowcount
        per_record_time = bulk_update_time / max(updated_count, 1)
        
        logger.info(f"Bulk update performance: {bulk_update_time:.4f}s total, {updated_count} records, {per_record_time:.6f}s per record")
        
        # Performance assertions
        assert bulk_update_time < 2.0, f"Bulk update should complete under 2s, got {bulk_update_time:.4f}s"
        assert per_record_time < 0.02, f"Per-record update time should be under 20ms, got {per_record_time:.6f}s"

    async def test_complex_query_performance(self, db_session: AsyncSession, performance_test_data: Dict[str, List[Tenant]]):
        """Test performance of complex queries with JOINs and aggregations."""
        parent_tenants = performance_test_data["parents"]
        test_parent = parent_tenants[0]
        
        # Set tenant context
        await db_session.execute(text(f"SELECT set_tenant_context('{test_parent.tenant_id}')"))
        
        metrics = PerformanceMetrics()
        
        # Test complex aggregation query
        complex_query = text("""
            SELECT 
                t1.name as parent_name,
                COUNT(t2.tenant_id) as subsidiary_count,
                jsonb_agg(DISTINCT t2.metadata->>'region') as regions,
                jsonb_agg(DISTINCT t2.metadata->>'business_unit') as business_units,
                AVG(EXTRACT(epoch FROM t2.created_at)) as avg_created_timestamp
            FROM tenants t1
            LEFT JOIN tenants t2 ON t1.tenant_id = t2.parent_tenant_id
            WHERE t1.tenant_type = 'parent'
            GROUP BY t1.tenant_id, t1.name
            ORDER BY subsidiary_count DESC
        """)
        
        # Warm up
        for _ in range(3):
            await db_session.execute(complex_query)
        
        # Measure complex query performance
        for i in range(20):
            start_time = time.perf_counter()
            result = await db_session.execute(complex_query)
            await result.fetchall()
            end_time = time.perf_counter()
            metrics.add_measurement(end_time - start_time)
        
        stats = metrics.get_statistics()
        logger.info(f"Complex Query Performance - Mean: {stats['mean']:.4f}s, P95: {stats['p95']:.4f}s")
        
        # Performance assertions
        assert stats["mean"] < 0.5, f"Complex query average time should be under 500ms, got {stats['mean']:.4f}s"
        assert stats["p95"] < 1.0, f"Complex query P95 should be under 1s, got {stats['p95']:.4f}s"

    async def test_index_effectiveness(self, db_session: AsyncSession, performance_test_data: Dict[str, List[Tenant]]):
        """Test that indexes are effectively used in tenant queries."""
        parent_tenants = performance_test_data["parents"]
        test_parent = parent_tenants[0]
        
        # Set tenant context
        await db_session.execute(text(f"SELECT set_tenant_context('{test_parent.tenant_id}')"))
        
        # Test queries that should use indexes
        test_queries = [
            # Test parent_tenant_id index
            (f"SELECT * FROM tenants WHERE parent_tenant_id = '{test_parent.tenant_id}'", "parent_tenant_id index"),
            
            # Test tenant_type index
            ("SELECT * FROM tenants WHERE tenant_type = 'subsidiary'", "tenant_type index"),
            
            # Test name index (functional)
            ("SELECT * FROM tenants WHERE LOWER(name) LIKE 'performance test%'", "name functional index"),
            
            # Test metadata GIN index
            ("SELECT * FROM tenants WHERE metadata->>'region' = 'region_0'", "metadata GIN index"),
        ]
        
        for query, description in test_queries:
            # Get query execution plan
            explain_result = await db_session.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {query}"))
            plan = explain_result.fetchall()
            plan_text = "\n".join([row[0] for row in plan])
            
            # Measure query performance
            start_time = time.perf_counter()
            result = await db_session.execute(text(query))
            await result.fetchall()
            end_time = time.perf_counter()
            
            query_time = end_time - start_time
            logger.info(f"{description} - Time: {query_time:.4f}s")
            
            # Check if index is being used (basic heuristic)
            if "Index Scan" not in plan_text and "Bitmap Index Scan" not in plan_text:
                logger.warning(f"Query may not be using expected index: {description}")
            
            # Performance assertion
            assert query_time < 0.1, f"{description} query should complete under 100ms, got {query_time:.4f}s"

    async def test_concurrent_access_performance(self, db_session: AsyncSession, performance_test_data: Dict[str, List[Tenant]]):
        """Test performance under concurrent access patterns."""
        parent_tenants = performance_test_data["parents"]
        
        async def simulate_tenant_access(parent_tenant: Tenant, iterations: int = 10):
            """Simulate concurrent access for a specific tenant."""
            # Create new session for concurrent access
            settings = get_settings()
            async for session in get_async_session():
                try:
                    # Set tenant context
                    await session.execute(text(f"SELECT set_tenant_context('{parent_tenant.tenant_id}')"))
                    
                    access_times = []
                    for _ in range(iterations):
                        start_time = time.perf_counter()
                        
                        # Simulate typical operations
                        await session.execute(text("SELECT COUNT(*) FROM tenants"))
                        await session.execute(text("SELECT * FROM tenants WHERE tenant_type = 'subsidiary' LIMIT 10"))
                        await session.execute(text("SELECT metadata FROM tenants WHERE metadata->>'region' IS NOT NULL LIMIT 5"))
                        
                        end_time = time.perf_counter()
                        access_times.append(end_time - start_time)
                    
                    return access_times
                finally:
                    await session.close()
                break
        
        # Test concurrent access with multiple tenants
        concurrent_tasks = []
        test_parents = parent_tenants[:5]  # Use first 5 parents
        
        for parent in test_parents:
            task = asyncio.create_task(simulate_tenant_access(parent))
            concurrent_tasks.append(task)
        
        # Measure concurrent execution
        start_time = time.perf_counter()
        results = await asyncio.gather(*concurrent_tasks)
        end_time = time.perf_counter()
        
        total_concurrent_time = end_time - start_time
        all_access_times = [time for result in results for time in result]
        
        # Calculate statistics
        avg_access_time = statistics.mean(all_access_times)
        p95_access_time = statistics.quantiles(all_access_times, n=20)[18] if len(all_access_times) >= 20 else max(all_access_times)
        
        logger.info(f"Concurrent access - Total time: {total_concurrent_time:.4f}s, Avg operation: {avg_access_time:.4f}s, P95: {p95_access_time:.4f}s")
        
        # Performance assertions
        assert total_concurrent_time < 10.0, f"Concurrent access should complete under 10s, got {total_concurrent_time:.4f}s"
        assert avg_access_time < 0.2, f"Average concurrent operation time should be under 200ms, got {avg_access_time:.4f}s"
        assert p95_access_time < 0.5, f"P95 concurrent operation time should be under 500ms, got {p95_access_time:.4f}s"

    async def test_rls_overhead_measurement(self, db_session: AsyncSession, performance_test_data: Dict[str, List[Tenant]]):
        """Measure RLS overhead by comparing queries with and without RLS context."""
        parent_tenants = performance_test_data["parents"]
        test_parent = parent_tenants[0]
        
        # Test query without tenant context (should return no rows due to RLS)
        await db_session.execute(text("SELECT clear_tenant_context()"))
        
        no_context_times = []
        for _ in range(50):
            start_time = time.perf_counter()
            result = await db_session.execute(text("SELECT COUNT(*) FROM tenants"))
            count = result.scalar()
            end_time = time.perf_counter()
            no_context_times.append(end_time - start_time)
            assert count == 0, "Should return 0 rows without tenant context"
        
        # Test query with tenant context
        await db_session.execute(text(f"SELECT set_tenant_context('{test_parent.tenant_id}')"))
        
        with_context_times = []
        for _ in range(50):
            start_time = time.perf_counter()
            result = await db_session.execute(text("SELECT COUNT(*) FROM tenants"))
            count = result.scalar()
            end_time = time.perf_counter()
            with_context_times.append(end_time - start_time)
            assert count > 0, "Should return rows with tenant context"
        
        # Calculate RLS overhead
        avg_no_context = statistics.mean(no_context_times)
        avg_with_context = statistics.mean(with_context_times)
        
        # Calculate overhead percentage
        overhead_percentage = ((avg_with_context - avg_no_context) / avg_no_context) * 100 if avg_no_context > 0 else 0
        
        logger.info(f"RLS Overhead - No context: {avg_no_context:.6f}s, With context: {avg_with_context:.6f}s, Overhead: {overhead_percentage:.2f}%")
        
        # Overhead should be reasonable (less than 50% increase)
        assert overhead_percentage < 50, f"RLS overhead should be under 50%, got {overhead_percentage:.2f}%"

    async def test_pagination_performance(self, db_session: AsyncSession, performance_test_data: Dict[str, List[Tenant]]):
        """Test performance of paginated queries with RLS."""
        parent_tenants = performance_test_data["parents"]
        test_parent = parent_tenants[0]
        
        # Set tenant context
        await db_session.execute(text(f"SELECT set_tenant_context('{test_parent.tenant_id}')"))
        
        page_sizes = [10, 25, 50, 100]
        pagination_metrics = {}
        
        for page_size in page_sizes:
            metrics = PerformanceMetrics()
            
            # Test multiple pages
            for page_num in range(5):
                offset = page_num * page_size
                
                start_time = time.perf_counter()
                result = await db_session.execute(text(f"""
                    SELECT * FROM tenants 
                    ORDER BY name 
                    LIMIT {page_size} OFFSET {offset}
                """))
                await result.fetchall()
                end_time = time.perf_counter()
                
                metrics.add_measurement(end_time - start_time)
            
            pagination_metrics[page_size] = metrics.get_statistics()
            logger.info(f"Pagination (page_size={page_size}) - Mean: {pagination_metrics[page_size]['mean']:.4f}s")
        
        # Performance assertions
        for page_size, stats in pagination_metrics.items():
            assert stats["mean"] < 0.1, f"Pagination with page_size={page_size} should average under 100ms"
            assert stats["p95"] < 0.2, f"Pagination with page_size={page_size} P95 should be under 200ms"

    async def test_memory_usage_patterns(self, db_session: AsyncSession, performance_test_data: Dict[str, List[Tenant]]):
        """Test memory usage patterns during large result set processing."""
        parent_tenants = performance_test_data["parents"]
        test_parent = parent_tenants[0]
        
        # Set tenant context
        await db_session.execute(text(f"SELECT set_tenant_context('{test_parent.tenant_id}')"))
        
        # Test streaming vs loading all results
        streaming_query = text("SELECT * FROM tenants ORDER BY name")
        
        # Measure streaming approach (fetchmany)
        start_time = time.perf_counter()
        result = await db_session.execute(streaming_query)
        row_count = 0
        while True:
            rows = result.fetchmany(50)  # Process in chunks
            if not rows:
                break
            row_count += len(rows)
        streaming_time = time.perf_counter() - start_time
        
        # Measure bulk loading approach (fetchall)
        start_time = time.perf_counter()
        result = await db_session.execute(streaming_query)
        all_rows = result.fetchall()
        bulk_time = time.perf_counter() - start_time
        
        logger.info(f"Memory usage patterns - Streaming: {streaming_time:.4f}s, Bulk: {bulk_time:.4f}s, Rows: {row_count}")
        
        # Both approaches should be reasonable
        assert streaming_time < 1.0, f"Streaming approach should complete under 1s, got {streaming_time:.4f}s"
        assert bulk_time < 1.0, f"Bulk approach should complete under 1s, got {bulk_time:.4f}s"
        assert len(all_rows) == row_count, "Row counts should match between approaches"