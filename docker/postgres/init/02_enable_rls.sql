-- Row Level Security (RLS) Setup
-- Hybrid approach: SET LOCAL tenant context + application-level logic
-- Created: 2025-08-06 for secure multi-tenant data isolation

-- Enable RLS on tenants table
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owners and superusers (for testing)
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;

-- Create function to get current tenant context from session
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS UUID AS $$
BEGIN
    -- Get tenant_id from session variable set by application
    RETURN current_setting('app.current_tenant_id', true)::UUID;
EXCEPTION
    WHEN OTHERS THEN
        -- Return NULL if not set or invalid
        RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

-- Create function to check if user can access tenant data
CREATE OR REPLACE FUNCTION can_access_tenant(target_tenant_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    session_tenant_id UUID;
    target_parent_id UUID;
    session_parent_id UUID;
BEGIN
    -- Get current session tenant
    session_tenant_id := current_tenant_id();
    
    -- If no session tenant set, deny access
    IF session_tenant_id IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- If accessing own tenant, allow
    IF session_tenant_id = target_tenant_id THEN
        RETURN TRUE;
    END IF;
    
    -- Check if session tenant is parent of target tenant
    SELECT parent_tenant_id INTO target_parent_id 
    FROM tenants 
    WHERE tenant_id = target_tenant_id;
    
    IF target_parent_id = session_tenant_id THEN
        RETURN TRUE;
    END IF;
    
    -- Check if both tenants share the same parent (sibling access - not allowed by default)
    -- This is more restrictive - siblings cannot see each other
    
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql STABLE;

-- Create comprehensive RLS policy for SELECT operations
CREATE POLICY tenant_select_policy ON tenants
    FOR SELECT
    USING (can_access_tenant(tenant_id));

-- Create RLS policy for INSERT operations
-- Users can only create subsidiaries under their own tenant (if they're a parent)
-- or create new parent tenants
CREATE POLICY tenant_insert_policy ON tenants
    FOR INSERT
    WITH CHECK (
        -- Allow creation if no session tenant (bootstrap case)
        current_tenant_id() IS NULL OR
        
        -- Allow parent tenant creation
        (tenant_type = 'parent' AND parent_tenant_id IS NULL) OR
        
        -- Allow subsidiary creation under current tenant
        (tenant_type = 'subsidiary' AND parent_tenant_id = current_tenant_id()) OR
        
        -- Allow subsidiary creation if current tenant is the parent
        (tenant_type = 'subsidiary' AND 
         parent_tenant_id IS NOT NULL AND 
         can_access_tenant(parent_tenant_id))
    );

-- Create RLS policy for UPDATE operations
CREATE POLICY tenant_update_policy ON tenants
    FOR UPDATE
    USING (can_access_tenant(tenant_id))
    WITH CHECK (
        -- Ensure updated record still complies with access rules
        can_access_tenant(tenant_id) AND
        
        -- Prevent changing tenant_type or parent_tenant_id
        tenant_type = OLD.tenant_type AND
        (parent_tenant_id = OLD.parent_tenant_id OR 
         (parent_tenant_id IS NULL AND OLD.parent_tenant_id IS NULL))
    );

-- Create RLS policy for DELETE operations
CREATE POLICY tenant_delete_policy ON tenants
    FOR DELETE
    USING (
        can_access_tenant(tenant_id) AND
        
        -- Additional check: cannot delete parent with active subsidiaries
        NOT EXISTS (
            SELECT 1 FROM tenants child 
            WHERE child.parent_tenant_id = tenants.tenant_id
        )
    );

-- Create function to set tenant context for session
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
RETURNS VOID AS $$
BEGIN
    -- Validate that the tenant exists
    IF NOT EXISTS (SELECT 1 FROM tenants WHERE tenant_id = tenant_uuid) THEN
        RAISE EXCEPTION 'Tenant % does not exist', tenant_uuid;
    END IF;
    
    -- Set the session variable
    PERFORM set_config('app.current_tenant_id', tenant_uuid::text, true);
END;
$$ LANGUAGE plpgsql;

-- Create function to clear tenant context
CREATE OR REPLACE FUNCTION clear_tenant_context()
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', '', true);
END;
$$ LANGUAGE plpgsql;

-- Create function to get tenant hierarchy (for debugging/admin purposes)
CREATE OR REPLACE FUNCTION get_tenant_hierarchy(root_tenant_id UUID)
RETURNS TABLE (
    tenant_id UUID,
    name VARCHAR(200),
    tenant_type tenant_type,
    level INTEGER,
    path TEXT
) AS $$
WITH RECURSIVE tenant_tree AS (
    -- Base case: start with the root tenant
    SELECT 
        t.tenant_id,
        t.name,
        t.tenant_type,
        1 as level,
        t.name::TEXT as path
    FROM tenants t
    WHERE t.tenant_id = root_tenant_id
    
    UNION ALL
    
    -- Recursive case: get children
    SELECT 
        t.tenant_id,
        t.name,
        t.tenant_type,
        tt.level + 1,
        tt.path || ' -> ' || t.name
    FROM tenants t
    JOIN tenant_tree tt ON t.parent_tenant_id = tt.tenant_id
)
SELECT * FROM tenant_tree ORDER BY level, name;
$$ LANGUAGE sql;

-- Add comments for RLS documentation
COMMENT ON FUNCTION current_tenant_id() IS 'Gets the current tenant context from session variable';
COMMENT ON FUNCTION can_access_tenant(UUID) IS 'Checks if current session can access specific tenant data';
COMMENT ON FUNCTION set_tenant_context(UUID) IS 'Sets tenant context for current session';
COMMENT ON FUNCTION clear_tenant_context() IS 'Clears tenant context from current session';
COMMENT ON FUNCTION get_tenant_hierarchy(UUID) IS 'Returns hierarchical view of tenant and its subsidiaries';