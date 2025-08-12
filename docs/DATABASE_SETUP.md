# Database Setup and Management Guide

This guide provides comprehensive instructions for setting up, managing, and troubleshooting the multi-tenant PostgreSQL database.

## Quick Start (New Setup)

For a fresh database setup, follow these steps:

```bash
# 1. Start the database
docker-compose -f docker/docker-compose.yml up -d

# 2. Run Alembic migrations
alembic upgrade head

# 3. Validate setup (optional but recommended)
python scripts/validate_db_functions.py
```

## Problem: Docker Init Scripts Not Applied

### Symptoms
- Database starts but missing RLS functions
- Errors like: `function set_tenant_context(uuid) does not exist`
- Functions defined in `docker/postgres/init/` weren't applied

### Root Cause
Docker PostgreSQL init scripts only run when the data volume is empty. If you:
1. Started the container before adding init scripts
2. Have an existing `postgres_data` volume
3. The init scripts were added after the first container run

Then the scripts in `docker/postgres/init/` were never executed.

### Solutions

#### Option 1: Run Migration (Recommended)
```bash
# Apply the migration that adds missing RLS functions
alembic upgrade head

# Validate everything is working
python scripts/validate_db_functions.py
```

#### Option 2: Complete Database Reset
```bash
# Stop containers and remove volumes
docker-compose -f docker/docker-compose.yml down -v

# Start fresh (this will run init scripts)
docker-compose -f docker/docker-compose.yml up -d

# Run migrations
alembic upgrade head

# Validate setup
python scripts/validate_db_functions.py
```

#### Option 3: Manual Function Creation
```bash
# Connect to database
docker-compose -f docker/docker-compose.yml exec postgres psql -U postgres -d multi_tenant_db

# Run the contents of docker/postgres/init/02_enable_rls.sql manually
\i /docker-entrypoint-initdb.d/02_enable_rls.sql
```

## Database Architecture

### Core Components

1. **Tenants Table**: Core multi-tenant data with RLS enabled
2. **RLS Functions**: Support tenant context and access control
3. **RLS Policies**: Enforce data isolation between tenants
4. **Indexes**: Optimized for tenant-aware queries

### Required Functions

| Function | Purpose | Usage |
|----------|---------|-------|
| `current_tenant_id()` | Get active tenant context | Used by RLS policies |
| `can_access_tenant(UUID)` | Check tenant access rights | Used by RLS policies |  
| `set_tenant_context(UUID)` | Set session tenant context | Called by application |
| `clear_tenant_context()` | Clear session tenant context | Called by application |
| `get_tenant_hierarchy(UUID)` | Query tenant relationships | Admin/debugging |

## Database Validation

### Automated Validation Script

The `scripts/validate_db_functions.py` script performs comprehensive checks:

```bash
# Run validation
python scripts/validate_db_functions.py

# Expected output for healthy database:
✅ All database functions and RLS policies are properly configured!
```

### Manual Validation

```sql
-- Check if functions exist
\df *tenant*

-- Check RLS policies
\d+ tenants

-- Test tenant context functions
SELECT set_tenant_context('00000000-0000-0000-0000-000000000000');
SELECT current_tenant_id();
SELECT clear_tenant_context();
```

## Migration Management

### Current Migrations

| Migration | Description |
|-----------|-------------|
| `d66543feddd6` | Create tenant model with RLS support |
| `76f0447e0164` | Add missing RLS functions (idempotent) |

### Creating New Migrations

```bash
# Generate migration
alembic revision -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

### Migration Best Practices

1. **Always backup before migrations in production**
2. **Test migrations on development data first**
3. **Use idempotent operations (CREATE OR REPLACE)**
4. **Include proper downgrade logic**
5. **Validate with the validation script after migration**

## Troubleshooting

### Common Issues

#### 1. Functions Missing After Docker Start
**Error**: `function set_tenant_context(uuid) does not exist`

**Solution**: 
```bash
alembic upgrade head
python scripts/validate_db_functions.py
```

#### 2. RLS Policies Not Working
**Error**: Users can see all tenant data

**Checks**:
```sql
-- Verify RLS is enabled
SELECT schemaname, tablename, rowsecurity, forcerowsecurity 
FROM pg_tables WHERE tablename = 'tenants';

-- Check policies exist
SELECT * FROM pg_policies WHERE tablename = 'tenants';
```

**Solution**: Re-run the initial migration
```bash
alembic downgrade base
alembic upgrade head
```

#### 3. Database Connection Issues
**Error**: Connection refused or authentication failed

**Checks**:
1. Verify `.env` file configuration
2. Check container is running: `docker ps`
3. Check logs: `docker-compose -f docker/docker-compose.yml logs postgres`

#### 4. Tenant Context Not Working
**Error**: `current_tenant_id()` returns NULL

**Debug**:
```sql
-- Check if context is set
SELECT current_setting('app.current_tenant_id', true);

-- Set context manually to test
SELECT set_config('app.current_tenant_id', 'your-tenant-uuid', true);
SELECT current_tenant_id();
```

## Development Workflow

### Daily Development
```bash
# Start database
docker-compose -f docker/docker-compose.yml up -d

# Your application development work...

# Stop when done (keeps data)
docker-compose -f docker/docker-compose.yml down
```

### Schema Changes
```bash
# 1. Create migration
alembic revision -m "Add new table/column"

# 2. Edit the generated migration file
# 3. Test migration
alembic upgrade head

# 4. Validate
python scripts/validate_db_functions.py

# 5. Test rollback capability
alembic downgrade -1
alembic upgrade head
```

### Clean Slate Testing
```bash
# Nuclear option - completely fresh database
docker-compose -f docker/docker-compose.yml down -v
docker-compose -f docker/docker-compose.yml up -d
alembic upgrade head
python scripts/validate_db_functions.py
```

## Production Considerations

### Pre-deployment Checklist
- [ ] All migrations tested in staging
- [ ] Database backup created
- [ ] Validation script passes
- [ ] RLS policies tested with real tenant data
- [ ] Performance impact assessed

### Deployment Process
1. **Backup database**
2. **Apply migrations**: `alembic upgrade head`
3. **Validate**: Run validation script
4. **Monitor**: Check application logs and performance
5. **Rollback plan**: Document downgrade steps

### Monitoring
- Monitor `current_tenant_id()` calls in logs
- Track RLS policy performance impact
- Alert on missing tenant context errors

## Security Notes

1. **Tenant Isolation**: RLS policies prevent cross-tenant data access
2. **Force RLS**: Enabled even for superuser (for testing)
3. **Session Security**: Tenant context is session-local
4. **Function Security**: Validate tenant existence before setting context

## Performance Considerations

1. **Indexes**: Tenant-aware indexes optimize filtered queries
2. **RLS Overhead**: Minimal performance impact in most cases
3. **Context Switching**: Minimal overhead for set_tenant_context()
4. **Policy Evaluation**: Cached within transaction scope

---

For more information, see:
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- Project-specific documentation in `/docs/`