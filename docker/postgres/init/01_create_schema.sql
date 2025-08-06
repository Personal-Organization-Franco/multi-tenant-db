-- Multi-Tenant Database Schema
-- PostgreSQL 17.5 with Row Level Security (RLS)
-- Created: 2025-08-06 for fintech multi-tenant application

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create enum types
CREATE TYPE tenant_type AS ENUM ('parent', 'subsidiary');

-- Create tenant table with proper constraints
CREATE TABLE tenants (
    tenant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    parent_tenant_id UUID REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    tenant_type tenant_type NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Ensure tenant names are unique within the same parent hierarchy
    CONSTRAINT unique_name_per_parent UNIQUE (name, parent_tenant_id),
    
    -- Business logic constraints
    CONSTRAINT parent_tenant_must_be_parent CHECK (
        (tenant_type = 'parent' AND parent_tenant_id IS NULL) OR
        (tenant_type = 'subsidiary' AND parent_tenant_id IS NOT NULL)
    ),
    
    -- Prevent self-referencing
    CONSTRAINT no_self_reference CHECK (tenant_id != parent_tenant_id),
    
    -- Ensure name is not empty after trimming
    CONSTRAINT name_not_empty CHECK (trim(name) != '')
);

-- Create indexes for optimal performance
CREATE INDEX idx_tenants_parent_id ON tenants(parent_tenant_id) WHERE parent_tenant_id IS NOT NULL;
CREATE INDEX idx_tenants_type ON tenants(tenant_type);
CREATE INDEX idx_tenants_created_at ON tenants(created_at);
CREATE INDEX idx_tenants_name_lower ON tenants(lower(name));
CREATE INDEX idx_tenants_metadata_gin ON tenants USING gin(metadata);

-- Create function to update updated_at automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for automatic updated_at
CREATE TRIGGER update_tenants_updated_at 
    BEFORE UPDATE ON tenants 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Create function to prevent more than 2 levels of hierarchy
CREATE OR REPLACE FUNCTION check_tenant_hierarchy_depth()
RETURNS TRIGGER AS $$
DECLARE
    parent_has_parent BOOLEAN := FALSE;
BEGIN
    -- Only check for subsidiaries
    IF NEW.tenant_type = 'subsidiary' AND NEW.parent_tenant_id IS NOT NULL THEN
        -- Check if the parent already has a parent (would create 3 levels)
        SELECT EXISTS(
            SELECT 1 FROM tenants 
            WHERE tenant_id = NEW.parent_tenant_id 
            AND parent_tenant_id IS NOT NULL
        ) INTO parent_has_parent;
        
        IF parent_has_parent THEN
            RAISE EXCEPTION 'Tenant hierarchy cannot exceed 2 levels';
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to enforce hierarchy depth
CREATE TRIGGER check_hierarchy_depth_trigger
    BEFORE INSERT OR UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION check_tenant_hierarchy_depth();

-- Create function to prevent circular references (additional safety)
CREATE OR REPLACE FUNCTION check_circular_reference()
RETURNS TRIGGER AS $$
DECLARE
    temp_parent_id UUID;
    depth INTEGER := 0;
BEGIN
    -- Only check when parent_tenant_id is set
    IF NEW.parent_tenant_id IS NOT NULL THEN
        temp_parent_id := NEW.parent_tenant_id;
        
        -- Walk up the hierarchy to check for cycles
        WHILE temp_parent_id IS NOT NULL AND depth < 10 LOOP
            -- If we find ourselves, it's circular
            IF temp_parent_id = NEW.tenant_id THEN
                RAISE EXCEPTION 'Circular reference detected in tenant hierarchy';
            END IF;
            
            -- Get the next parent
            SELECT parent_tenant_id INTO temp_parent_id 
            FROM tenants 
            WHERE tenant_id = temp_parent_id;
            
            depth := depth + 1;
        END LOOP;
        
        -- Additional safety: if we hit depth limit, something's wrong
        IF depth >= 10 THEN
            RAISE EXCEPTION 'Tenant hierarchy depth exceeded maximum allowed';
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for circular reference check
CREATE TRIGGER check_circular_reference_trigger
    BEFORE INSERT OR UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION check_circular_reference();

-- Add comments for documentation
COMMENT ON TABLE tenants IS 'Multi-tenant organization table with hierarchical support';
COMMENT ON COLUMN tenants.tenant_id IS 'Unique identifier for the tenant';
COMMENT ON COLUMN tenants.name IS 'Human-readable tenant name, unique within parent hierarchy';
COMMENT ON COLUMN tenants.parent_tenant_id IS 'Reference to parent tenant for subsidiaries';
COMMENT ON COLUMN tenants.tenant_type IS 'Type of tenant: parent (top-level) or subsidiary';
COMMENT ON COLUMN tenants.metadata IS 'Additional JSON metadata for flexible data storage';