"""
Health check endpoints for monitoring and diagnostics.

Simple, focused health checks following clean architecture principles.
Maximum 300 lines per the project requirements.
"""

import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from ...core.deps import DBSession
from ...db.session import test_database_connection
from ...models.tenant import Tenant

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Multi-Tenant Database API",
        "version": "0.1.0",
    }


@router.get("/database", status_code=status.HTTP_200_OK)
async def database_health_check(db: DBSession) -> dict[str, Any]:
    """Database connectivity health check."""
    try:
        result = await db.execute(text("SELECT 1 as test, NOW() as time"))
        row = result.fetchone()

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "status": "healthy",
                "test_value": row.test,
                "server_time": row.time.isoformat(),
            },
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "status": "unhealthy",
                "error": str(e),
            },
        }


@router.get("/tenant-model", status_code=status.HTTP_200_OK)
async def tenant_model_health_check(db: DBSession) -> dict[str, Any]:
    """Tenant model and RLS health check."""
    start_time = time.time()
    overall_status = "healthy"
    details = {}
    
    try:
        # Test tenant table access
        result = await db.execute(select(func.count(Tenant.tenant_id)))
        tenant_count = result.scalar()
        details["tenant_count"] = tenant_count
        
        # Test RLS is enabled
        rls_result = await db.execute(text("""
            SELECT relrowsecurity FROM pg_class WHERE relname = 'tenants'
        """))
        rls_enabled = bool(rls_result.scalar())
        details["rls_enabled"] = rls_enabled
        
        # Test RLS functions exist
        func_result = await db.execute(text("""
            SELECT COUNT(*) FROM pg_proc 
            WHERE proname IN ('current_tenant_id', 'can_access_tenant')
        """))
        func_count = func_result.scalar()
        details["rls_functions_available"] = func_count >= 2
        
        # Test basic tenant operations
        test_id = str(uuid4())
        await db.execute(text("""
            INSERT INTO tenants (tenant_id, name, tenant_type)
            VALUES (:id, :name, 'parent')
        """), {"id": test_id, "name": f"test-{test_id[:8]}"})
        
        verify_result = await db.execute(text("""
            SELECT name FROM tenants WHERE tenant_id = :id
        """), {"id": test_id})
        created = verify_result.fetchone()
        
        await db.execute(text("DELETE FROM tenants WHERE tenant_id = :id"), 
                        {"id": test_id})
        await db.commit()
        
        details["crud_operations"] = "working" if created else "failed"
        
        if not (rls_enabled and func_count >= 2 and created):
            overall_status = "unhealthy"
            
    except SQLAlchemyError as e:
        overall_status = "unhealthy"
        details["error"] = str(e)
    
    end_time = time.time()
    response_time = round((end_time - start_time) * 1000, 2)
    
    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": "tenant_model",
        "response_time_ms": response_time,
        "details": details,
    }


@router.get("/tenant-isolation", status_code=status.HTTP_200_OK)
async def tenant_isolation_health_check(db: DBSession) -> dict[str, Any]:
    """Test tenant isolation via RLS policies."""
    start_time = time.time()
    overall_status = "healthy"
    test_results = {}
    test_tenant_ids = []
    
    try:
        # Create test hierarchy
        parent_id = str(uuid4())
        child_id = str(uuid4())
        test_tenant_ids = [parent_id, child_id]
        
        # First insert parent
        await db.execute(text("""
            INSERT INTO tenants (tenant_id, name, tenant_type)
            VALUES (:parent_id, :parent_name, 'parent')
        """), {
            "parent_id": parent_id,
            "parent_name": f"test-parent-{parent_id[:8]}"
        })
        
        # Then insert subsidiary with proper parent reference
        await db.execute(text("""
            INSERT INTO tenants (tenant_id, name, tenant_type, parent_tenant_id)
            VALUES (:child_id, :child_name, 'subsidiary', :parent_id)
        """), {
            "child_id": child_id,
            "child_name": f"test-child-{child_id[:8]}",
            "parent_id": parent_id
        })
        
        # Test isolation (no tenant context = RLS functions should deny access)
        # Note: We test the RLS functions directly since superuser can bypass policies
        result = await db.execute(text("""
            SELECT COUNT(*) FROM tenants 
            WHERE tenant_id = ANY(:ids) AND can_access_tenant(tenant_id)
        """), {"ids": test_tenant_ids})
        visible_without_context = result.scalar()
        test_results["isolation_without_context"] = visible_without_context == 0
        
        # Set parent context and test visibility
        await db.execute(text(f"SET LOCAL app.current_tenant_id = '{parent_id}'"))
        
        result = await db.execute(text("""
            SELECT COUNT(*) FROM tenants 
            WHERE tenant_id = ANY(:ids) AND can_access_tenant(tenant_id)
        """), {"ids": test_tenant_ids})
        visible_with_parent_context = result.scalar()
        test_results["parent_can_see_data"] = visible_with_parent_context > 0
        
        if not all(test_results.values()):
            overall_status = "unhealthy"
            
    except SQLAlchemyError as e:
        overall_status = "unhealthy"
        test_results["error"] = str(e)
    
    finally:
        # Cleanup
        try:
            if test_tenant_ids:
                await db.execute(text("""
                    DELETE FROM tenants WHERE tenant_id = ANY(:ids)
                """), {"ids": test_tenant_ids})
                await db.commit()
        except SQLAlchemyError:
            pass
    
    end_time = time.time()
    response_time = round((end_time - start_time) * 1000, 2)
    
    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": "tenant_isolation",
        "response_time_ms": response_time,
        "test_results": test_results,
    }


@router.get("/readiness", status_code=status.HTTP_200_OK)
async def readiness_check() -> dict[str, Any]:
    """Kubernetes readiness check."""
    db_ready = await test_database_connection()
    return {
        "status": "ready" if db_ready else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": [{
            "name": "database",
            "status": "ready" if db_ready else "not_ready",
            "required": True,
        }],
    }


@router.get("/liveness", status_code=status.HTTP_200_OK)
async def liveness_check() -> dict[str, Any]:
    """Kubernetes liveness check."""
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }