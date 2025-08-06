-- Sample Data for Multi-Tenant Database
-- Created: 2025-08-06 for development and testing
-- This file creates sample tenant hierarchy based on fintech use case

-- Temporarily disable RLS for initial data insertion
SET session_replication_role = replica;

-- Insert parent tenants (major financial institutions)
INSERT INTO tenants (tenant_id, name, tenant_type, metadata) VALUES 
(
    '00000000-0000-0000-0000-000000000001',
    'HSBC Holdings',
    'parent',
    '{
        "country": "United Kingdom",
        "business_type": "multinational_bank",
        "founded": "1865",
        "headquarters": "London"
    }'::jsonb
),
(
    '00000000-0000-0000-0000-000000000002',
    'JPMorgan Chase',
    'parent',
    '{
        "country": "United States",
        "business_type": "investment_bank",
        "founded": "1799",
        "headquarters": "New York"
    }'::jsonb
),
(
    '00000000-0000-0000-0000-000000000003',
    'Deutsche Bank',
    'parent',
    '{
        "country": "Germany",
        "business_type": "universal_bank",
        "founded": "1870",
        "headquarters": "Frankfurt"
    }'::jsonb
);

-- Insert subsidiary tenants
INSERT INTO tenants (tenant_id, name, parent_tenant_id, tenant_type, metadata) VALUES
-- HSBC subsidiaries
(
    '00000000-0000-0000-0001-000000000001',
    'HSBC Hong Kong',
    '00000000-0000-0000-0000-000000000001',
    'subsidiary',
    '{
        "country": "Hong Kong",
        "business_unit": "retail_banking",
        "region": "Asia Pacific",
        "local_license": "HKMA-2024-001"
    }'::jsonb
),
(
    '00000000-0000-0000-0001-000000000002',
    'HSBC UK',
    '00000000-0000-0000-0000-000000000001',
    'subsidiary',
    '{
        "country": "United Kingdom",
        "business_unit": "retail_banking",
        "region": "Europe",
        "local_license": "FCA-2024-001"
    }'::jsonb
),
(
    '00000000-0000-0000-0001-000000000003',
    'HSBC Canada',
    '00000000-0000-0000-0000-000000000001',
    'subsidiary',
    '{
        "country": "Canada",
        "business_unit": "commercial_banking",
        "region": "North America",
        "local_license": "OSFI-2024-001"
    }'::jsonb
),

-- JPMorgan subsidiaries
(
    '00000000-0000-0000-0002-000000000001',
    'Chase Bank',
    '00000000-0000-0000-0000-000000000002',
    'subsidiary',
    '{
        "country": "United States",
        "business_unit": "consumer_banking",
        "region": "North America",
        "local_license": "OCC-2024-001"
    }'::jsonb
),
(
    '00000000-0000-0000-0002-000000000002',
    'JPMorgan Securities',
    '00000000-0000-0000-0000-000000000002',
    'subsidiary',
    '{
        "country": "United States",
        "business_unit": "investment_banking",
        "region": "Global",
        "local_license": "SEC-2024-001"
    }'::jsonb
),

-- Deutsche Bank subsidiaries
(
    '00000000-0000-0000-0003-000000000001',
    'Deutsche Bank AG London',
    '00000000-0000-0000-0000-000000000003',
    'subsidiary',
    '{
        "country": "United Kingdom",
        "business_unit": "investment_banking",
        "region": "Europe",
        "local_license": "FCA-2024-002"
    }'::jsonb
),
(
    '00000000-0000-0000-0003-000000000002',
    'Deutsche Bank Americas',
    '00000000-0000-0000-0000-000000000003',
    'subsidiary',
    '{
        "country": "United States",
        "business_unit": "corporate_banking",
        "region": "Americas",
        "local_license": "FED-2024-001"
    }'::jsonb
);

-- Re-enable RLS
SET session_replication_role = DEFAULT;

-- Create view for easy tenant hierarchy visualization
CREATE OR REPLACE VIEW tenant_hierarchy AS
WITH RECURSIVE tenant_tree AS (
    -- Base case: all parent tenants
    SELECT 
        tenant_id,
        name,
        parent_tenant_id,
        tenant_type,
        1 as level,
        name as full_path,
        ARRAY[tenant_id] as path_ids
    FROM tenants
    WHERE parent_tenant_id IS NULL
    
    UNION ALL
    
    -- Recursive case: all subsidiaries
    SELECT 
        t.tenant_id,
        t.name,
        t.parent_tenant_id,
        t.tenant_type,
        tt.level + 1,
        tt.full_path || ' -> ' || t.name,
        tt.path_ids || t.tenant_id
    FROM tenants t
    JOIN tenant_tree tt ON t.parent_tenant_id = tt.tenant_id
)
SELECT 
    tenant_id,
    name,
    parent_tenant_id,
    tenant_type,
    level,
    full_path,
    path_ids
FROM tenant_tree
ORDER BY full_path;

-- Create function to validate sample data integrity
CREATE OR REPLACE FUNCTION validate_sample_data()
RETURNS TABLE (
    test_name TEXT,
    status TEXT,
    details TEXT
) AS $$
BEGIN
    -- Test 1: All parent tenants have no parent
    RETURN QUERY
    SELECT 
        'Parent tenants validation'::TEXT,
        CASE 
            WHEN COUNT(*) = 0 THEN 'PASS'::TEXT
            ELSE 'FAIL'::TEXT
        END,
        CASE 
            WHEN COUNT(*) = 0 THEN 'All parent tenants correctly have no parent'::TEXT
            ELSE COUNT(*)::TEXT || ' parent tenants incorrectly have parent_tenant_id set'
        END
    FROM tenants 
    WHERE tenant_type = 'parent' AND parent_tenant_id IS NOT NULL;
    
    -- Test 2: All subsidiaries have a parent
    RETURN QUERY
    SELECT 
        'Subsidiary tenants validation'::TEXT,
        CASE 
            WHEN COUNT(*) = 0 THEN 'PASS'::TEXT
            ELSE 'FAIL'::TEXT
        END,
        CASE 
            WHEN COUNT(*) = 0 THEN 'All subsidiary tenants correctly have a parent'::TEXT
            ELSE COUNT(*)::TEXT || ' subsidiary tenants missing parent_tenant_id'
        END
    FROM tenants 
    WHERE tenant_type = 'subsidiary' AND parent_tenant_id IS NULL;
    
    -- Test 3: No circular references
    RETURN QUERY
    SELECT 
        'Circular reference check'::TEXT,
        CASE 
            WHEN COUNT(*) = 0 THEN 'PASS'::TEXT
            ELSE 'FAIL'::TEXT
        END,
        CASE 
            WHEN COUNT(*) = 0 THEN 'No circular references found'::TEXT
            ELSE COUNT(*)::TEXT || ' circular references detected'
        END
    FROM tenants t1
    JOIN tenants t2 ON t1.parent_tenant_id = t2.tenant_id
    WHERE t2.parent_tenant_id = t1.tenant_id;
    
    -- Test 4: No more than 2 levels
    RETURN QUERY
    SELECT 
        'Hierarchy depth check'::TEXT,
        CASE 
            WHEN MAX(level) <= 2 THEN 'PASS'::TEXT
            ELSE 'FAIL'::TEXT
        END,
        'Maximum hierarchy depth: ' || MAX(level)::TEXT || ' levels'
    FROM tenant_hierarchy;
    
    -- Test 5: Name uniqueness within parent scope
    RETURN QUERY
    SELECT 
        'Name uniqueness check'::TEXT,
        CASE 
            WHEN COUNT(*) = 0 THEN 'PASS'::TEXT
            ELSE 'FAIL'::TEXT
        END,
        CASE 
            WHEN COUNT(*) = 0 THEN 'All tenant names are unique within their parent scope'::TEXT
            ELSE COUNT(*)::TEXT || ' duplicate names found within parent scope'
        END
    FROM (
        SELECT name, parent_tenant_id, COUNT(*) as cnt
        FROM tenants
        GROUP BY name, parent_tenant_id
        HAVING COUNT(*) > 1
    ) duplicates;
    
END;
$$ LANGUAGE plpgsql;

-- Add sample data validation comment
COMMENT ON FUNCTION validate_sample_data() IS 'Validates the integrity of sample tenant data';
COMMENT ON VIEW tenant_hierarchy IS 'Hierarchical view of all tenants with their full path';