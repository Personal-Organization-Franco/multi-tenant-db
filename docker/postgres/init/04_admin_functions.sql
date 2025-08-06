-- Administrative Functions for Multi-Tenant Database
-- Created: 2025-08-06 for database administration and monitoring

-- Function to safely reset tenant context (admin only)
CREATE OR REPLACE FUNCTION admin_reset_all_tenant_contexts()
RETURNS VOID AS $$
BEGIN
    -- This function should only be used by database administrators
    -- Clear any existing tenant context
    PERFORM set_config('app.tenant_id', '', false);
END;
$$ LANGUAGE plpgsql;

-- Function to get tenant statistics
CREATE OR REPLACE FUNCTION get_tenant_statistics()
RETURNS TABLE (
    total_tenants BIGINT,
    parent_tenants BIGINT,
    subsidiary_tenants BIGINT,
    orphaned_subsidiaries BIGINT,
    max_hierarchy_depth INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM tenants)::BIGINT as total_tenants,
        (SELECT COUNT(*) FROM tenants WHERE tenant_type = 'parent')::BIGINT as parent_tenants,
        (SELECT COUNT(*) FROM tenants WHERE tenant_type = 'subsidiary')::BIGINT as subsidiary_tenants,
        (SELECT COUNT(*) 
         FROM tenants 
         WHERE tenant_type = 'subsidiary' 
         AND parent_tenant_id IS NOT NULL 
         AND parent_tenant_id NOT IN (SELECT tenant_id FROM tenants))::BIGINT as orphaned_subsidiaries,
        (SELECT COALESCE(MAX(level), 0) FROM tenant_hierarchy)::INTEGER as max_hierarchy_depth;
END;
$$ LANGUAGE plpgsql;

-- Function to audit tenant access patterns
CREATE OR REPLACE FUNCTION audit_tenant_access(target_tenant UUID)
RETURNS TABLE (
    can_select BOOLEAN,
    can_insert BOOLEAN,
    can_update BOOLEAN,
    can_delete BOOLEAN,
    current_context UUID,
    access_reason TEXT
) AS $$
DECLARE
    context_tenant UUID;
BEGIN
    -- Get current tenant context
    context_tenant := current_tenant_id();
    
    RETURN QUERY
    SELECT 
        -- Test SELECT access
        (SELECT can_access_tenant(target_tenant)) as can_select,
        
        -- Test INSERT access (simplified - would need actual insert attempt for full test)
        (context_tenant IS NULL OR 
         target_tenant IN (
             SELECT tenant_id FROM tenants 
             WHERE parent_tenant_id = context_tenant OR tenant_id = context_tenant
         )) as can_insert,
        
        -- Test UPDATE access
        (SELECT can_access_tenant(target_tenant)) as can_update,
        
        -- Test DELETE access  
        (SELECT can_access_tenant(target_tenant) AND
         NOT EXISTS (
             SELECT 1 FROM tenants child 
             WHERE child.parent_tenant_id = target_tenant
         )) as can_delete,
        
        -- Current context
        context_tenant as current_context,
        
        -- Access reason
        CASE 
            WHEN context_tenant IS NULL THEN 'No tenant context set'
            WHEN context_tenant = target_tenant THEN 'Direct tenant access'
            WHEN target_tenant IN (
                SELECT tenant_id FROM tenants WHERE parent_tenant_id = context_tenant
            ) THEN 'Parent accessing subsidiary'
            ELSE 'Access denied - no relationship'
        END as access_reason;
END;
$$ LANGUAGE plpgsql;

-- Function to check database health for multi-tenant setup
CREATE OR REPLACE FUNCTION check_database_health()
RETURNS TABLE (
    component TEXT,
    status TEXT,
    details TEXT
) AS $$
BEGIN
    -- Check RLS is enabled
    RETURN QUERY
    SELECT 
        'Row Level Security'::TEXT as component,
        CASE 
            WHEN relrowsecurity THEN 'ENABLED'::TEXT
            ELSE 'DISABLED'::TEXT
        END as status,
        CASE 
            WHEN relrowsecurity THEN 'RLS is properly enabled on tenants table'::TEXT
            ELSE 'WARNING: RLS is not enabled on tenants table'::TEXT
        END as details
    FROM pg_class 
    WHERE relname = 'tenants';
    
    -- Check required extensions
    RETURN QUERY
    SELECT 
        'Extensions'::TEXT as component,
        CASE 
            WHEN COUNT(*) = 2 THEN 'OK'::TEXT
            ELSE 'MISSING'::TEXT
        END as status,
        'Found ' || COUNT(*)::TEXT || ' of 2 required extensions (uuid-ossp, pgcrypto)' as details
    FROM pg_extension 
    WHERE extname IN ('uuid-ossp', 'pgcrypto');
    
    -- Check triggers
    RETURN QUERY
    SELECT 
        'Triggers'::TEXT as component,
        CASE 
            WHEN COUNT(*) >= 3 THEN 'OK'::TEXT
            ELSE 'MISSING'::TEXT
        END as status,
        'Found ' || COUNT(*)::TEXT || ' triggers on tenants table' as details
    FROM pg_trigger 
    WHERE tgrelid = 'tenants'::regclass AND NOT tgisinternal;
    
    -- Check policies
    RETURN QUERY
    SELECT 
        'RLS Policies'::TEXT as component,
        CASE 
            WHEN COUNT(*) >= 4 THEN 'OK'::TEXT
            ELSE 'MISSING'::TEXT
        END as status,
        'Found ' || COUNT(*)::TEXT || ' RLS policies on tenants table' as details
    FROM pg_policy 
    WHERE polrelid = 'tenants'::regclass;
    
    -- Check sample data
    RETURN QUERY
    SELECT 
        'Sample Data'::TEXT as component,
        CASE 
            WHEN COUNT(*) > 0 THEN 'LOADED'::TEXT
            ELSE 'EMPTY'::TEXT
        END as status,
        'Found ' || COUNT(*)::TEXT || ' tenant records' as details
    FROM tenants;
    
END;
$$ LANGUAGE plpgsql;

-- Function to demonstrate tenant isolation (for testing)
CREATE OR REPLACE FUNCTION test_tenant_isolation()
RETURNS TABLE (
    test_scenario TEXT,
    tenant_context TEXT,
    visible_tenants BIGINT,
    expected_count BIGINT,
    status TEXT
) AS $$
BEGIN
    -- Test 1: No context - should see nothing due to RLS
    PERFORM clear_tenant_context();
    RETURN QUERY
    SELECT 
        'No tenant context'::TEXT as test_scenario,
        'NULL'::TEXT as tenant_context,
        (SELECT COUNT(*) FROM tenants)::BIGINT as visible_tenants,
        0::BIGINT as expected_count,
        CASE 
            WHEN (SELECT COUNT(*) FROM tenants) = 0 THEN 'PASS'::TEXT
            ELSE 'FAIL'::TEXT
        END as status;
    
    -- Test 2: Parent tenant context - should see self + subsidiaries
    PERFORM set_tenant_context('00000000-0000-0000-0000-000000000001');
    RETURN QUERY
    SELECT 
        'HSBC parent context'::TEXT as test_scenario,
        'HSBC Holdings'::TEXT as tenant_context,
        (SELECT COUNT(*) FROM tenants)::BIGINT as visible_tenants,
        4::BIGINT as expected_count, -- HSBC + 3 subsidiaries
        CASE 
            WHEN (SELECT COUNT(*) FROM tenants) = 4 THEN 'PASS'::TEXT
            ELSE 'FAIL'::TEXT
        END as status;
    
    -- Test 3: Subsidiary context - should see only self
    PERFORM set_tenant_context('00000000-0000-0000-0001-000000000001');
    RETURN QUERY
    SELECT 
        'HSBC HK subsidiary context'::TEXT as test_scenario,
        'HSBC Hong Kong'::TEXT as tenant_context,
        (SELECT COUNT(*) FROM tenants)::BIGINT as visible_tenants,
        1::BIGINT as expected_count, -- Only HSBC HK
        CASE 
            WHEN (SELECT COUNT(*) FROM tenants) = 1 THEN 'PASS'::TEXT
            ELSE 'FAIL'::TEXT
        END as status;
    
    -- Clean up - clear context
    PERFORM clear_tenant_context();
END;
$$ LANGUAGE plpgsql;

-- Function to backup tenant data (metadata only)
CREATE OR REPLACE FUNCTION export_tenant_metadata()
RETURNS TABLE (
    tenant_export JSONB
) AS $$
BEGIN
    -- Export all tenant data as JSON for backup/migration
    RETURN QUERY
    SELECT jsonb_build_object(
        'tenant_id', tenant_id,
        'name', name,
        'parent_tenant_id', parent_tenant_id,
        'tenant_type', tenant_type,
        'created_at', created_at,
        'updated_at', updated_at,
        'metadata', metadata
    ) as tenant_export
    FROM tenants
    ORDER BY 
        CASE WHEN parent_tenant_id IS NULL THEN 0 ELSE 1 END,
        created_at;
END;
$$ LANGUAGE plpgsql;

-- Add comments for admin functions
COMMENT ON FUNCTION admin_reset_all_tenant_contexts() IS 'Administrative function to reset tenant contexts - use with caution';
COMMENT ON FUNCTION get_tenant_statistics() IS 'Returns comprehensive statistics about tenant data';
COMMENT ON FUNCTION audit_tenant_access(UUID) IS 'Audits access permissions for a specific tenant';
COMMENT ON FUNCTION check_database_health() IS 'Comprehensive health check for multi-tenant database setup';
COMMENT ON FUNCTION test_tenant_isolation() IS 'Tests RLS tenant isolation with different contexts';
COMMENT ON FUNCTION export_tenant_metadata() IS 'Exports tenant metadata as JSON for backup/migration';