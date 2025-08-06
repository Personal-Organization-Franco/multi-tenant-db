# Multi-Tenant Database API

## FastAPI Project Structure

This directory contains the complete FastAPI application with multi-tenant support.

### Project Structure

```
src/multi_tenant_db/
├── api/
│   ├── middleware/         # Custom middleware components
│   │   └── tenant.py      # Multi-tenant context middleware
│   └── v1/                # API version 1 endpoints
│       ├── health.py      # Health check endpoints
│       └── router.py      # Main API router
├── core/                  # Core application components
│   ├── config.py          # Configuration management
│   ├── deps.py            # Dependency injection
│   ├── exceptions.py      # Custom exceptions
│   └── logging.py         # Logging configuration
├── db/                    # Database related code
│   └── session.py         # Database session management with RLS
├── models/                # SQLAlchemy models (future)
├── schemas/               # Pydantic schemas (future)
├── services/              # Business logic services (future)
├── utils/                 # Utility functions (future)
└── main.py                # FastAPI application factory
```

### Key Features

#### 🏗️ CLEAN Architecture
- Clear separation of concerns
- Dependency inversion principle
- Modular, testable design

#### 🏢 Multi-Tenant Support
- **Tenant Context Middleware**: Extracts tenant ID from headers/cookies
- **Database Session Management**: Automatic Row Level Security (RLS) context
- **Flexible Tenant Identification**: Headers, cookies, and JWT token support

#### ⚙️ Configuration Management
- **Pydantic Settings**: Type-safe environment variable handling
- **Environment-based Configuration**: Development, staging, production support
- **Validation**: Built-in configuration validation and error handling

#### 🔧 Middleware Stack
- **CORS**: Configurable cross-origin resource sharing
- **Compression**: GZip compression for responses
- **Multi-Tenant Context**: Automatic tenant identification and context setting
- **Database Tenant Context**: RLS context for database queries

#### 🏥 Health Endpoints
- `GET /health` - Basic health check
- `GET /api/v1/health/` - Basic API health
- `GET /api/v1/health/detailed` - Detailed health with database check
- `GET /api/v1/health/database` - Database connectivity test
- `GET /api/v1/health/readiness` - Kubernetes readiness probe
- `GET /api/v1/health/liveness` - Kubernetes liveness probe

#### 🗄️ Database Integration
- **Async SQLAlchemy**: Full async database support
- **Connection Pooling**: Optimized connection management
- **Multi-Tenant RLS**: Row Level Security with tenant context
- **Session Management**: Proper cleanup and error handling

### Usage

#### Running the Application

```bash
# Development mode
python -m uvicorn src.multi_tenant_db.main:app --reload

# Production mode
python -m uvicorn src.multi_tenant_db.main:app --host 0.0.0.0 --port 8000
```

#### Environment Variables

Required environment variables (see `.env.example`):

- `DATABASE_URL`: PostgreSQL connection string
- `JWT_SECRET_KEY`: Secret key for JWT tokens
- `ENVIRONMENT`: Application environment (development/staging/production)

#### Multi-Tenant Usage

Include tenant context in requests:

```bash
# Using header
curl -H "X-Tenant-ID: tenant123" http://localhost:8000/api/v1/health/

# Health endpoints work without tenant context
curl http://localhost:8000/health
```

### Development

#### Adding New Endpoints

1. Create endpoint module in `api/v1/`
2. Add router to `api/v1/router.py`
3. Use `TenantDBSession` dependency for tenant-aware database access

#### Database Queries

```python
from ..core.deps import TenantDBSession

@router.get("/users")
async def get_users(db: TenantDBSession):
    # Queries automatically filtered by tenant context
    result = await db.execute(select(User))
    return result.scalars().all()
```

### Next Steps

- ✅ FastAPI project structure complete
- 📋 Configure development dependencies (B1.1.2)
- 📋 Create SQLAlchemy models with RLS (D1.2.1)
- 📋 Enhanced health endpoints with database connectivity (B1.2.1)