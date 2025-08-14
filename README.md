# Multi Tenant Database

The goal of this project is to setup a multi tenant database using SQLAlchemy and FastAPI, implementing row level security (RLS) to ensure that each tenant can only access their own data.

# Project Structure

```
.
├── .env                                    # Environment variables
├── .gitignore                             # Git ignore rules
├── .pre-commit-config.yaml               # Pre-commit hooks configuration
├── README.md                             # Project documentation
├── DATABASE_SECURITY_TESTING.md         # Security testing documentation
├── SECURITY_TEST_RESULTS.md             # Security test results
├── Makefile                              # Build and development commands
├── pyproject.toml                        # Python project configuration
├── alembic.ini                           # Alembic migration configuration
├── main.py                               # Application entry point
├── coverage.xml                          # Test coverage results
├── database_security_tests.sql          # SQL security test scripts
├── uv.lock                               # Python dependency lock file
├── docs/                                 # Project documentation
│   ├── DATABASE_SETUP.md
│   ├── FUNCTIONAL_REQUIREMENTS.md
│   ├── NON_FUNCTIONAL_REQUIREMENTS.md
│   ├── PROJECT_GOALS.md
│   ├── PROJECT_PLAN.md
│   ├── PROJECT_REQUIREMENTS.md
│   ├── PROJECT_STATUS.md
│   └── TEST_STRATEGY.md
├── scripts/                              # Utility scripts
│   └── validate_db_functions.py
├── alembic/                              # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 76f0447e0164_add_missing_rls_functions_for_tenant_.py
│       ├── 8d429f220452_add_missing_rls_policies_for_tenant_.py
│       └── d66543feddd6_create_tenant_model_with_rls_support.py
├── docker/                               # Docker configurations
│   ├── docker-compose.yml
│   ├── docker-compose.test.yml
│   └── postgres/
│       ├── init/
│       │   ├── 01_create_schema.sql
│       │   ├── 02_enable_rls.sql
│       │   ├── 03_sample_data.sql
│       │   └── 04_admin_functions.sql
│       ├── pg_hba.conf
│       └── postgresql.conf
├── src/                                  # Main application source code
│   └── multi_tenant_db/
│       ├── __init__.py
│       ├── README.md
│       ├── main.py                       # FastAPI application
│       ├── api/                          # API layer
│       │   ├── __init__.py
│       │   ├── middleware/
│       │   │   ├── __init__.py
│       │   │   └── tenant.py            # Tenant context middleware
│       │   └── v1/                       # API version 1
│       │       ├── __init__.py
│       │       ├── health.py            # Health check endpoints
│       │       ├── router.py            # Main API router
│       │       └── tenants.py           # Tenant management endpoints
│       ├── core/                         # Core application logic
│       │   ├── __init__.py
│       │   ├── config.py                # Application configuration
│       │   ├── deps.py                  # Dependency injection
│       │   ├── exceptions.py            # Custom exceptions
│       │   └── logging.py               # Logging configuration
│       ├── db/                          # Database layer
│       │   ├── __init__.py
│       │   └── session.py               # Database session management
│       ├── models/                       # Database models
│       │   ├── __init__.py
│       │   ├── base.py                  # Base model with RLS support
│       │   └── tenant.py                # Tenant model
│       ├── schemas/                      # Pydantic schemas
│       │   ├── __init__.py
│       │   └── tenant.py                # Tenant API schemas
│       ├── services/                     # Business logic services
│       │   ├── __init__.py
│       │   └── tenant.py                # Tenant service layer
│       └── utils/                        # Utility functions
│           └── __init__.py
├── tests/                                # Comprehensive test suite
│   ├── __init__.py
│   ├── conftest.py                       # Test configuration
│   ├── test_config.py                    # Configuration tests
│   ├── factories.py                      # Test data factories
│   ├── run_database_security_tests.py   # Security test runner
│   ├── fixtures/                         # Test fixtures
│   │   └── __init__.py
│   ├── database/                         # Database-specific tests
│   │   ├── __init__.py
│   │   └── test_migrations.py
│   ├── unit/                            # Unit tests
│   │   ├── __init__.py
│   │   ├── test_api/                    # API unit tests
│   │   │   ├── __init__.py
│   │   │   ├── test_health.py
│   │   │   └── test_tenants.py
│   │   ├── test_core/                   # Core logic tests
│   │   │   ├── __init__.py
│   │   │   ├── test_deps.py
│   │   │   ├── test_exceptions.py
│   │   │   └── test_logging.py
│   │   ├── test_db/                     # Database tests
│   │   │   ├── __init__.py
│   │   │   └── test_session.py
│   │   ├── test_middleware/             # Middleware tests
│   │   │   ├── __init__.py
│   │   │   └── test_tenant.py
│   │   ├── test_models/                 # Model tests
│   │   │   ├── __init__.py
│   │   │   ├── test_base.py
│   │   │   └── test_tenant.py
│   │   ├── test_schemas/                # Schema tests
│   │   │   ├── __init__.py
│   │   │   └── test_tenant.py
│   │   └── test_services/               # Service tests
│   │       ├── __init__.py
│   │       └── test_tenant.py
│   ├── integration/                     # Integration tests
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── factories.py
│   │   ├── test_api/                    # API integration tests
│   │   │   ├── __init__.py
│   │   │   ├── test_health_integration.py
│   │   │   └── test_tenants_integration.py
│   │   ├── test_database/               # Database integration tests
│   │   │   ├── __init__.py
│   │   │   ├── test_rls_integration.py
│   │   │   └── test_session_integration.py
│   │   └── test_scenarios/              # Business scenario tests
│   │       ├── __init__.py
│   │       ├── test_banking_hierarchy.py
│   │       └── test_fintech_business_rules.py
│   ├── security/                        # Security tests
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_penetration.py
│   │   └── test_rls_security.py
│   └── performance/                     # Performance tests
│       ├── __init__.py
│       └── test_database_performance.py
├── htmlcov/                             # Test coverage HTML reports
└── .venv/                               # Virtual environment
```

# What the project does

Implements simple APIs to create, read, update and delete tenants. It's a fintech application that allows users to create and manage their own tenants.
The very simple usecase shows how HSBC parent has access to HSBC HK and HSBC London tenants but doesn't have access to Barclays tenant for example.

## Prerequisites

- Python 3.13.5
- PostgreSQL 17
- FastAPI
- SQLAlchemy
- Alembic
