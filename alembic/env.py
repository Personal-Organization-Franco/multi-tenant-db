"""
Alembic environment configuration for async SQLAlchemy.

Configures Alembic to work with async SQLAlchemy and multi-tenant
database setup with proper migration support.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
import sys
from pathlib import Path

# Add the src directory to sys.path so we can import our models
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import models for autogenerate support
from multi_tenant_db.models.base import Base
from multi_tenant_db.models.tenant import Tenant  # noqa: F401
from multi_tenant_db.core.config import get_settings

target_metadata = Base.metadata

# Other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    # Use settings from configuration, fallback to env var for migrations
    import os
    try:
        settings = get_settings()
        url = str(settings.database_url)
    except Exception:
        # Fallback to environment variable during migrations
        url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:your_secure_password_here@localhost:5432/multi_tenant_db")
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with database connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    # Use settings from configuration, fallback to env var for migrations
    import os
    try:
        settings = get_settings()
        database_url = str(settings.database_url)
    except Exception:
        # Fallback to environment variable during migrations
        database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:your_secure_password_here@localhost:5432/multi_tenant_db")
    
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()