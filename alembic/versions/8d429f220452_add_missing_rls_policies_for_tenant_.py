"""Add missing RLS policies for tenant table

Revision ID: 8d429f220452
Revises: 76f0447e0164
Create Date: 2025-08-12 15:56:25.423893

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d429f220452'
down_revision: Union[str, None] = '76f0447e0164'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing RLS policies that may not have been created during initial setup
    # These use IF NOT EXISTS logic by checking existing policies first
    
    # Create RLS policy for UPDATE operations
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'tenants' AND policyname = 'tenant_update_policy') THEN
            CREATE POLICY tenant_update_policy ON tenants
                FOR UPDATE
                USING (can_access_tenant(tenant_id))
                WITH CHECK (
                    -- Ensure updated record still complies with access rules
                    can_access_tenant(tenant_id)
                );
        END IF;
    END $$;
    """)
    
    # Create RLS policy for DELETE operations
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'tenants' AND policyname = 'tenant_delete_policy') THEN
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
        END IF;
    END $$;
    """)


def downgrade() -> None:
    # Drop the added RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_delete_policy ON tenants;")
    op.execute("DROP POLICY IF EXISTS tenant_update_policy ON tenants;")