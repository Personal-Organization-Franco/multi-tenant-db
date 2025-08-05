# Multi-Tenant Database Project Requirements

## Project Goals

The primary goal of this project is to implement a multi-tenant database system using Row Level Security (RLS) in PostgreSQL, demonstrating secure data isolation between tenants in a fintech context. The project showcases how parent organizations can access their subsidiary tenants while maintaining strict isolation from other organizations.

### Core Objectives

- Implement secure multi-tenancy using PostgreSQL Row Level Security (RLS)
- Create a simple fintech API demonstrating tenant hierarchy (e.g., HSBC parent → HSBC HK, HSBC London)
- Ensure complete data isolation between different tenant organizations
- Provide a clean, maintainable codebase following Python best practices
- Enable local development with containerized infrastructure

## Architecture & Design Principles

### Clean Architecture Implementation

The project follows clean architecture principles with clear separation of concerns:

```
app/
├── api/                    # Presentation Layer
│   ├── main.py            # FastAPI application setup
│   └── routes/            # API route handlers
│       └── tenant.py      # Tenant-specific endpoints
├── core/                  # Core Business Logic
│   ├── config.py         # Application configuration
│   └── dependencies.py   # Dependency injection
├── database/             # Data Access Layer
│   ├── base.py          # SQLAlchemy base configuration
│   ├── models/          # Database models (one class per file)
│   │   ├── __init__.py  # Package exports
│   │   └── tenant.py    # Tenant model
│   └── session.py       # Database session management
├── schemas/             # Data Validation Layer
│   ├── __init__.py     # Package exports
│   └── tenant.py       # Pydantic schemas
└── main.py             # Application entry point
```

### Code Quality Standards

- **PEP 8 Compliance**: Strict adherence to Python style guidelines
- **The Zen of Python**: Simple, readable, and explicit code
- **Type Hints**: Complete type annotations for all functions
- **Import Organization**: Alphabetical ordering with proper import groups
- **Line Length**: Maximum 80 characters per line
- **Pattern Matching**: Use `match/case` instead of long `if/elif` chains
- **Generator Expressions**: Prefer generators with `next()` for finding matches
- **One Class Per File**: Maximum maintainability through modular organization
- **Minimal Documentation**: Comments and docstrings only for complex business logic, not every function

## Technology Stack

### Core Technologies

- **Python**: 3.13.5 (latest stable version)
- **Package Manager**: uv (modern, fast Python package manager)
- **Database**: PostgreSQL 17.5-bookworm (official Docker image)
- **ORM**: SQLAlchemy 2.0.41 (with modern async support)
- **Async PostgreSQL Driver**: asyncpg 0.30.0
- **API Framework**: FastAPI 0.116.1 (with automatic OpenAPI documentation)

### Development Dependencies

- **Database Migration**: Alembic 1.16.4 (SQLAlchemy's migration tool)
- **Environment Management**: python-dotenv
- **Data Validation**: Pydantic 2.11.7 (integrated with FastAPI)
- **ASGI Server**: uvicorn 0.35.0 (for running FastAPI application)
- **Testing**: pytest + pytest-asyncio
- **Linting**: ruff 0.12.5
- **Formatting**: black (integrated with ruff)

### Database Configuration

- **Engine**: PostgreSQL 17.5-bookworm
- **Connection**: Async connection pooling with asyncpg
- **Migration Strategy**: Alembic with auto-generation
- **Naming Convention**: Consistent snake_case for all database objects
- **Security**: Row Level Security (RLS) policies for tenant isolation

## API Endpoints (Maximum 6)

The API will implement the following simple endpoints:

1. **POST /tenants** - Create a new tenant
2. **GET /tenants** - List tenants (filtered by access permissions)
3. **GET /tenants/{tenant_id}** - Get specific tenant details
4. **PUT /tenants/{tenant_id}** - Update tenant information
5. **DELETE /tenants/{tenant_id}** - Delete a tenant
6. **GET /health** - Health check endpoint

## Data Models & Schemas

### SQLAlchemy Models

Models will use SQLAlchemy 2.0 syntax with proper type hints and follow the one-class-per-file principle.

### Pydantic Schemas

All schemas will use the new Pydantic syntax with:

```python
model_config = ConfigDict(
    extra="ignore",
    populate_by_name=True,
    validate_assignment=True,
    arbitrary_types_allowed=True,
)
```

## Development Infrastructure

### Docker Configuration

- **PostgreSQL**: Official postgres:17.5-bookworm image
- **Docker Compose**: Local development environment setup
- **Volume Persistence**: Database data persistence across container restarts

### Makefile Commands

The project will be managed through a simple Makefile with the following commands:

- **db-up**: Start PostgreSQL container
- **db-down**: Stop PostgreSQL container
- **dev**: Start development server with hot reload
- **test-unit**: Run unit tests
- **test-api**: Run API integration tests
- **lint**: Run ruff linting
- **format**: Format code with black/ruff
- **migrate**: Generate new database migration
- **migrate-apply**: Apply pending migrations
- **seed-db**: Populate database with sample data
- **clean-db**: Reset database to clean state
- **start**: Start production server
- **stop**: Stop all services
- **clean**: Clean up temporary files and containers

## Multi-Tenant Security Model

### Row Level Security (RLS)

The project implements PostgreSQL RLS policies to ensure:

- **Tenant Isolation**: Each tenant can only access their own data
- **Hierarchical Access**: Parent organizations can access subsidiary tenants
- **Policy Enforcement**: Database-level security that cannot be bypassed

### Example Tenant Hierarchy

```
HSBC (Parent)
├── HSBC Hong Kong (Subsidiary)
└── HSBC London (Subsidiary)

Barclays (Parent)
├── Barclays UK (Subsidiary)
└── Barclays US (Subsidiary)
```

## Development Workflow

1. **Setup**: Use `make db-up` to start PostgreSQL
2. **Migration**: Use `make migrate-apply` to setup database schema
3. **Seeding**: Use `make seed-db` to populate test data
4. **Development**: Use `make dev` to start development server
5. **Testing**: Use `make test-unit` and `make test-api` for validation
6. **Quality**: Use `make lint` and `make format` for code quality

## Project Constraints

- **No Authentication**: Project focuses on multi-tenancy, not authentication
- **Simplicity**: Keep endpoints minimal and focused
- **Local Development**: Optimized for local Docker-based development
- **Code Quality**: Zero tolerance for linting errors or `# noqa` usage
- **File Organization**: Maximum 300 lines per file, one class per file
- **Import Standards**: Perfect import ordering without suppression comments