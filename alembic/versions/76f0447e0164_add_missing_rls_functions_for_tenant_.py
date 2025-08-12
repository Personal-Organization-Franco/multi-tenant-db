"""Add missing RLS functions for tenant management

Revision ID: 76f0447e0164
Revises: d66543feddd6
Create Date: 2025-08-12 15:48:05.386539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76f0447e0164'
down_revision: Union[str, None] = 'd66543feddd6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration ensures all required RLS functions exist, even if Docker init scripts weren't run
    # These functions are idempotent (using CREATE OR REPLACE), so they're safe to run multiple times
    
    # Function to get current tenant context from session
    op.execute("""
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
    """)
    
    # Function to check if user can access tenant data
    op.execute("""
    CREATE OR REPLACE FUNCTION can_access_tenant(target_tenant_id UUID)
    RETURNS BOOLEAN AS $$
    DECLARE
        session_tenant_id UUID;
        target_parent_id UUID;
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
        
        -- Deny access (siblings cannot see each other)
        RETURN FALSE;
    END;
    $$ LANGUAGE plpgsql STABLE;
    """)
    
    # Function to set tenant context for session
    op.execute("""
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
    """)
    
    # Function to clear tenant context
    op.execute("""
    CREATE OR REPLACE FUNCTION clear_tenant_context()
    RETURNS VOID AS $$
    BEGIN
        PERFORM set_config('app.current_tenant_id', '', true);
    END;
    $$ LANGUAGE plpgsql;
    """)
    
    # Function to get tenant hierarchy (for debugging/admin purposes)
    op.execute("""
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
    """)
    
    # Add comments for RLS documentation
    op.execute("COMMENT ON FUNCTION current_tenant_id() IS 'Gets the current tenant context from session variable';")
    op.execute("COMMENT ON FUNCTION can_access_tenant(UUID) IS 'Checks if current session can access specific tenant data';")
    op.execute("COMMENT ON FUNCTION set_tenant_context(UUID) IS 'Sets tenant context for current session';")
    op.execute("COMMENT ON FUNCTION clear_tenant_context() IS 'Clears tenant context from current session';")
    op.execute("COMMENT ON FUNCTION get_tenant_hierarchy(UUID) IS 'Returns hierarchical view of tenant and its subsidiaries';")


def downgrade() -> None:
    # Drop the RLS utility functions
    # Note: These are used by RLS policies, so downgrading may break existing policies
    op.execute("DROP FUNCTION IF EXISTS get_tenant_hierarchy(UUID);")
    op.execute("DROP FUNCTION IF EXISTS clear_tenant_context();")
    op.execute("DROP FUNCTION IF EXISTS set_tenant_context(UUID);")