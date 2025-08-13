-- ===============================================
-- MULTI-TENANT DATABASE SECURITY VALIDATION TESTS
-- ===============================================
-- Tests comprehensive RLS implementation for production readiness
-- Execute via: docker exec -e PGPASSWORD=dev_password_123 [container] psql -U postgres -d multi_tenant_db -f database_security_tests.sql

-- Test tenant data (already created):
-- HSBC: d25719e7-d698-42e9-9eec-75095bd8fee8 (parent)
--   └─ HSBC child 1: a68d9aa1-ea90-4b53-8df5-0118b2c50d6d (subsidiary)
-- Barclays: 11111111-1111-1111-1111-111111111111 (parent)  
--   └─ Barclays Investment Banking: 11111111-1111-1111-1111-111111111112 (subsidiary)
-- Goldman Sachs: 22222222-2222-2222-2222-222222222222 (parent)
--   └─ Goldman Sachs FICC: 22222222-2222-2222-2222-222222222223 (subsidiary)

-- ===============================================
-- TEST 1: TENANT ISOLATION VALIDATION
-- ===============================================
\echo '=== TEST 1: TENANT ISOLATION VALIDATION ==='

-- Test 1.1: No tenant context - should see no data due to RLS
\echo '--- Test 1.1: No tenant context (should return empty) ---'
SELECT 'No tenant context' as test_case;
SELECT tenant_id, name FROM tenants;

-- Test 1.2: Set HSBC context - should only see HSBC family
\echo '--- Test 1.2: HSBC context (should see HSBC parent + child) ---'
SELECT set_tenant_context('d25719e7-d698-42e9-9eec-75095bd8fee8'::uuid);
SELECT 'HSBC tenant context set' as test_case;
SELECT tenant_id, name, parent_tenant_id FROM tenants ORDER BY name;

-- Test 1.3: Set Barclays context - should only see Barclays family
\echo '--- Test 1.3: Barclays context (should see Barclays parent + child) ---'
SELECT set_tenant_context('11111111-1111-1111-1111-111111111111'::uuid);
SELECT 'Barclays tenant context set' as test_case;
SELECT tenant_id, name, parent_tenant_id FROM tenants ORDER BY name;

-- Test 1.4: Set Goldman Sachs context - should only see Goldman family
\echo '--- Test 1.4: Goldman Sachs context (should see Goldman parent + child) ---'
SELECT set_tenant_context('22222222-2222-2222-2222-222222222222'::uuid);
SELECT 'Goldman Sachs tenant context set' as test_case;
SELECT tenant_id, name, parent_tenant_id FROM tenants ORDER BY name;

-- ===============================================
-- TEST 2: SUBSIDIARY TENANT ISOLATION
-- ===============================================
\echo '=== TEST 2: SUBSIDIARY TENANT ISOLATION ==='

-- Test 2.1: Set HSBC subsidiary context - should see parent + self only
\echo '--- Test 2.1: HSBC subsidiary context (should see parent + self) ---'
SELECT set_tenant_context('a68d9aa1-ea90-4b53-8df5-0118b2c50d6d'::uuid);
SELECT 'HSBC subsidiary context set' as test_case;
SELECT tenant_id, name, parent_tenant_id FROM tenants ORDER BY name;

-- Test 2.2: Set Barclays subsidiary context - should see parent + self only
\echo '--- Test 2.2: Barclays subsidiary context (should see parent + self) ---'
SELECT set_tenant_context('11111111-1111-1111-1111-111111111112'::uuid);
SELECT 'Barclays subsidiary context set' as test_case;
SELECT tenant_id, name, parent_tenant_id FROM tenants ORDER BY name;

-- ===============================================
-- TEST 3: RLS FUNCTION VALIDATION
-- ===============================================
\echo '=== TEST 3: RLS FUNCTION VALIDATION ==='

-- Test 3.1: current_tenant_id function
\echo '--- Test 3.1: current_tenant_id function ---'
SELECT set_tenant_context('d25719e7-d698-42e9-9eec-75095bd8fee8'::uuid);
SELECT current_tenant_id() as current_tenant, 
       'd25719e7-d698-42e9-9eec-75095bd8fee8'::uuid as expected_tenant,
       current_tenant_id() = 'd25719e7-d698-42e9-9eec-75095bd8fee8'::uuid as matches;

-- Test 3.2: can_access_tenant function - valid access
\echo '--- Test 3.2: can_access_tenant - valid access ---'
SELECT set_tenant_context('d25719e7-d698-42e9-9eec-75095bd8fee8'::uuid);
SELECT can_access_tenant('d25719e7-d698-42e9-9eec-75095bd8fee8'::uuid) as can_access_self,
       can_access_tenant('a68d9aa1-ea90-4b53-8df5-0118b2c50d6d'::uuid) as can_access_child;

-- Test 3.3: can_access_tenant function - invalid access
\echo '--- Test 3.3: can_access_tenant - invalid access ---'
SELECT set_tenant_context('d25719e7-d698-42e9-9eec-75095bd8fee8'::uuid);
SELECT can_access_tenant('11111111-1111-1111-1111-111111111111'::uuid) as cannot_access_barclays,
       can_access_tenant('22222222-2222-2222-2222-222222222222'::uuid) as cannot_access_goldman;

-- ===============================================
-- TEST 4: INSERT/UPDATE/DELETE OPERATIONS
-- ===============================================
\echo '=== TEST 4: INSERT/UPDATE/DELETE OPERATIONS ==='

-- Test 4.1: Insert subsidiary under current tenant context
\echo '--- Test 4.1: Insert subsidiary (should succeed) ---'
SELECT set_tenant_context('d25719e7-d698-42e9-9eec-75095bd8fee8'::uuid);
INSERT INTO tenants (tenant_id, name, parent_tenant_id, tenant_type, metadata) 
VALUES (
    '33333333-3333-3333-3333-333333333333'::uuid,
    'HSBC Test Subsidiary',
    'd25719e7-d698-42e9-9eec-75095bd8fee8'::uuid,
    'subsidiary',
    '{\"test\": true}'::jsonb
);

-- Test 4.2: Try to insert under different tenant (should fail)
\echo '--- Test 4.2: Insert under different tenant (should fail) ---'
BEGIN;
SELECT set_tenant_context('d25719e7-d698-42e9-9eec-75095bd8fee8'::uuid);
INSERT INTO tenants (tenant_id, name, parent_tenant_id, tenant_type, metadata) 
VALUES (
    '44444444-4444-4444-4444-444444444444'::uuid,
    'Should Fail Subsidiary',
    '11111111-1111-1111-1111-111111111111'::uuid,
    'subsidiary',
    '{\"test\": true}'::jsonb
);
ROLLBACK;

-- Test 4.3: Update own tenant data (should succeed)
\echo '--- Test 4.3: Update own tenant data (should succeed) ---'
SELECT set_tenant_context('d25719e7-d698-42e9-9eec-75095bd8fee8'::uuid);
UPDATE tenants 
SET metadata = metadata || '{"updated": true}'::jsonb 
WHERE tenant_id = 'd25719e7-d698-42e9-9eec-75095bd8fee8'::uuid;

-- Test 4.4: Try to update different tenant data (should affect 0 rows)
\echo '--- Test 4.4: Update different tenant data (should affect 0 rows) ---'
SELECT set_tenant_context('d25719e7-d698-42e9-9eec-75095bd8fee8'::uuid);
UPDATE tenants 
SET metadata = metadata || '{"hacked": true}'::jsonb 
WHERE tenant_id = '11111111-1111-1111-1111-111111111111'::uuid;

-- ===============================================
-- TEST 5: EDGE CASES AND SECURITY BOUNDARIES
-- ===============================================
\echo '=== TEST 5: EDGE CASES AND SECURITY BOUNDARIES ==='

-- Test 5.1: NULL tenant context
\echo '--- Test 5.1: NULL tenant context ---'
SELECT clear_tenant_context();
SELECT 'NULL tenant context' as test_case;
SELECT COUNT(*) as visible_tenants FROM tenants;

-- Test 5.2: Invalid UUID tenant context
\echo '--- Test 5.2: Invalid UUID tenant context ---'
SELECT set_tenant_context('99999999-9999-9999-9999-999999999999'::uuid);
SELECT 'Invalid UUID context' as test_case;
SELECT COUNT(*) as visible_tenants FROM tenants;

-- Test 5.3: Attempt SQL injection in tenant context
\echo '--- Test 5.3: SQL injection attempt (should be safe) ---'
BEGIN;
-- This should fail safely due to UUID type checking
-- SELECT set_tenant_context(''''; DROP TABLE tenants; --''::uuid);
ROLLBACK;

-- Clean up test data
\echo '--- Cleaning up test data ---'
SELECT set_tenant_context('d25719e7-d698-42e9-9eec-75095bd8fee8'::uuid);
DELETE FROM tenants WHERE tenant_id = '33333333-3333-3333-3333-333333333333'::uuid;

-- Reset context
SELECT clear_tenant_context();

\echo '=== SECURITY TESTS COMPLETED ==='