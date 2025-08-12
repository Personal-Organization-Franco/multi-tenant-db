#!/usr/bin/env python3
"""
Database Function Validation Script

This script validates that all required RLS functions exist in the database.
It's useful for ensuring the database is properly configured after Docker setup
or migration issues.

Usage:
    python scripts/validate_db_functions.py
    
Environment Variables:
    DATABASE_URL: Full database connection string (optional, reads from .env)
"""

import asyncio
import sys
from typing import Dict, List, Tuple
import asyncpg
import os
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent / "src"))

from multi_tenant_db.core.config import get_settings


class DatabaseFunctionValidator:
    """Validates that all required database functions exist and are correct."""
    
    # Required functions with their expected signatures
    REQUIRED_FUNCTIONS = {
        "current_tenant_id": {
            "return_type": "uuid",
            "params": [],
            "description": "Gets the current tenant context from session variable"
        },
        "can_access_tenant": {
            "return_type": "boolean", 
            "params": ["target_tenant_id uuid"],
            "description": "Checks if current session can access specific tenant data"
        },
        "set_tenant_context": {
            "return_type": "void",
            "params": ["tenant_uuid uuid"],
            "description": "Sets tenant context for current session"
        },
        "clear_tenant_context": {
            "return_type": "void",
            "params": [],
            "description": "Clears tenant context from current session"
        },
        "get_tenant_hierarchy": {
            "return_type": "TABLE(tenant_id uuid, name character varying(200), tenant_type tenant_type, level integer, path text)",
            "params": ["root_tenant_id uuid"],
            "description": "Returns hierarchical view of tenant and its subsidiaries"
        }
    }
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.connection = None
    
    async def connect(self):
        """Establish database connection."""
        try:
            self.connection = await asyncpg.connect(self.database_url)
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection."""
        if self.connection:
            await self.connection.close()
    
    async def check_function_exists(self, function_name: str) -> Tuple[bool, Dict]:
        """Check if a specific function exists and return its details."""
        query = """
        SELECT 
            p.proname as function_name,
            pg_catalog.format_type(p.prorettype, NULL) as return_type,
            COALESCE(pg_catalog.pg_get_function_arguments(p.oid), '') as parameters,
            COALESCE(d.description, '') as description
        FROM pg_proc p
        LEFT JOIN pg_description d ON d.objoid = p.oid
        WHERE p.proname = $1
        """
        
        try:
            rows = await self.connection.fetch(query, function_name)
            if not rows:
                return False, {}
            
            # Take the first match (in case of overloads)
            row = rows[0]
            return True, {
                "function_name": row["function_name"],
                "return_type": row["return_type"],
                "parameters": row["parameters"],
                "description": row["description"]
            }
        except Exception as e:
            print(f"❌ Error checking function {function_name}: {e}")
            return False, {}
    
    async def validate_all_functions(self) -> bool:
        """Validate all required functions exist."""
        print("🔍 Validating database RLS functions...")
        print("=" * 60)
        
        all_valid = True
        
        for func_name, expected in self.REQUIRED_FUNCTIONS.items():
            exists, actual = await self.check_function_exists(func_name)
            
            if not exists:
                print(f"❌ Function '{func_name}' MISSING")
                print(f"   Expected: {expected['return_type']} {func_name}({', '.join(expected['params'])})")
                all_valid = False
            else:
                print(f"✅ Function '{func_name}' EXISTS")
                print(f"   Return Type: {actual['return_type']}")
                print(f"   Parameters: {actual['parameters'] or 'none'}")
                if actual['description']:
                    print(f"   Description: {actual['description']}")
                
                # Basic validation of return type (simplified)
                expected_return = expected['return_type'].lower()
                actual_return = actual['return_type'].lower()
                
                # Handle table return types differently
                if not (expected_return.startswith('table') and actual_return.startswith('table')):
                    if expected_return != actual_return:
                        print(f"   ⚠️  Warning: Return type mismatch. Expected: {expected_return}, Got: {actual_return}")
            
            print()
        
        return all_valid
    
    async def check_rls_policies(self) -> bool:
        """Check if RLS policies are properly configured on tenants table."""
        print("🔒 Validating RLS policies on tenants table...")
        print("=" * 60)
        
        # Check if RLS is enabled
        rls_query = """
        SELECT 
            schemaname,
            tablename,
            CASE WHEN c.relrowsecurity THEN true ELSE false END as rowsecurity,
            CASE WHEN c.relforcerowsecurity THEN true ELSE false END as forcerowsecurity
        FROM pg_tables t
        JOIN pg_class c ON c.relname = t.tablename
        JOIN pg_namespace n ON c.relnamespace = n.oid AND n.nspname = t.schemaname
        WHERE t.tablename = 'tenants'
        """
        
        try:
            row = await self.connection.fetchrow(rls_query)
            if not row:
                print("❌ Tenants table not found")
                return False
            
            rls_enabled = row['rowsecurity']
            force_rls = row['forcerowsecurity']
            
            print(f"Table: {row['schemaname']}.{row['tablename']}")
            print(f"RLS Enabled: {'✅ Yes' if rls_enabled else '❌ No'}")
            print(f"Force RLS: {'✅ Yes' if force_rls else '❌ No'}")
            
            if not rls_enabled:
                print("❌ Row Level Security is not enabled on tenants table")
                return False
            
            # Check for RLS policies
            policy_query = """
            SELECT 
                policyname,
                cmd,
                permissive,
                qual,
                with_check
            FROM pg_policies 
            WHERE tablename = 'tenants'
            ORDER BY policyname
            """
            
            policies = await self.connection.fetch(policy_query)
            
            print(f"\nRLS Policies Found: {len(policies)}")
            expected_policies = ['tenant_select_policy', 'tenant_insert_policy', 'tenant_update_policy', 'tenant_delete_policy']
            
            found_policies = [p['policyname'] for p in policies]
            
            for expected_policy in expected_policies:
                if expected_policy in found_policies:
                    print(f"✅ Policy '{expected_policy}' exists")
                else:
                    print(f"❌ Policy '{expected_policy}' missing")
            
            return len(policies) >= 4 and rls_enabled
            
        except Exception as e:
            print(f"❌ Error checking RLS policies: {e}")
            return False
    
    async def run_validation(self) -> bool:
        """Run complete validation suite."""
        try:
            await self.connect()
            
            functions_valid = await self.validate_all_functions()
            rls_valid = await self.check_rls_policies()
            
            print("=" * 60)
            if functions_valid and rls_valid:
                print("✅ All database functions and RLS policies are properly configured!")
                return True
            else:
                print("❌ Database validation failed!")
                print("\n🔧 To fix missing functions, run:")
                print("   alembic upgrade head")
                print("\n🔧 To completely reset the database:")
                print("   docker-compose -f docker/docker-compose.yml down -v")
                print("   docker-compose -f docker/docker-compose.yml up -d")
                print("   alembic upgrade head")
                return False
                
        finally:
            await self.disconnect()


async def main():
    """Main entry point."""
    # Try to get database URL from environment or settings
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        try:
            settings = get_settings()
            database_url = str(settings.database_url)
        except Exception as e:
            print(f"❌ Could not determine database URL: {e}")
            print("Please set DATABASE_URL environment variable or ensure .env file is configured")
            sys.exit(1)
    
    # Convert SQLAlchemy URL format to asyncpg format
    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    print(f"🔗 Connecting to database: {database_url.split('@')[0]}@{'*' * 20}")
    
    validator = DatabaseFunctionValidator(database_url)
    success = await validator.run_validation()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())