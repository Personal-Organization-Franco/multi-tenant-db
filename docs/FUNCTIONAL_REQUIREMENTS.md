# Functional Requirements

## Overview

This document defines the functional requirements for the multi-tenant database API system. The system implements secure tenant management using PostgreSQL Row Level Security (RLS) for data isolation in a fintech context.

## Core Use Cases

### UC1: Tenant Management
- Create new tenants (parent and subsidiary organizations)
- Retrieve tenant information with proper access control
- Update tenant details and relationships
- Delete tenants and handle cascading effects
- List tenants based on hierarchical access permissions

### UC2: Multi-Tenant Data Access
- Enforce tenant isolation at the database level
- Support hierarchical access (parent can access subsidiaries)
- Prevent cross-tenant data leakage
- Maintain data integrity across tenant boundaries

## API Endpoints Specification

### 1. POST /tenants
**Purpose**: Create a new tenant organization

**Request Body**:
```json
{
  "name": "HSBC Hong Kong",
  "parent_tenant_id": "hsbc-parent-uuid",
  "tenant_type": "subsidiary",
  "metadata": {
    "country": "Hong Kong",
    "business_unit": "retail_banking"
  }
}
```

**Response (201 Created)**:
```json
{
  "tenant_id": "hsbc-hk-uuid",
  "name": "HSBC Hong Kong",
  "parent_tenant_id": "hsbc-parent-uuid",
  "tenant_type": "subsidiary",
  "created_at": "2025-08-05T10:00:00Z",
  "metadata": {
    "country": "Hong Kong",
    "business_unit": "retail_banking"
  }
}
```

**Validation Rules**:
- Name must be unique within parent hierarchy
- Parent tenant must exist if specified
- Tenant type must be 'parent' or 'subsidiary'

### 2. GET /tenants
**Purpose**: List tenants based on access permissions

**Query Parameters**:
- `limit`: Maximum number of results (default: 100, max: 1000)
- `offset`: Pagination offset (default: 0)
- `tenant_type`: Filter by tenant type ('parent', 'subsidiary')

**Response (200 OK)**:
```json
{
  "tenants": [
    {
      "tenant_id": "hsbc-parent-uuid",
      "name": "HSBC",
      "tenant_type": "parent",
      "created_at": "2025-08-05T09:00:00Z"
    }
  ],
  "total_count": 1,
  "limit": 100,
  "offset": 0
}
```

**Access Control**:
- Parent tenants can see their subsidiaries
- Subsidiary tenants can only see themselves
- No cross-organization visibility

### 3. GET /tenants/{tenant_id}
**Purpose**: Retrieve specific tenant details

**Path Parameters**:
- `tenant_id`: UUID of the tenant

**Response (200 OK)**:
```json
{
  "tenant_id": "hsbc-hk-uuid",
  "name": "HSBC Hong Kong",
  "parent_tenant_id": "hsbc-parent-uuid",
  "tenant_type": "subsidiary",
  "created_at": "2025-08-05T10:00:00Z",
  "updated_at": "2025-08-05T10:00:00Z",
  "metadata": {
    "country": "Hong Kong",
    "business_unit": "retail_banking"
  }
}
```

**Error Responses**:
- 404: Tenant not found or access denied
- 403: Insufficient permissions

### 4. PUT /tenants/{tenant_id}
**Purpose**: Update tenant information

**Request Body**:
```json
{
  "name": "HSBC Hong Kong Limited",
  "metadata": {
    "country": "Hong Kong",
    "business_unit": "retail_banking",
    "status": "active"
  }
}
```

**Response (200 OK)**:
```json
{
  "tenant_id": "hsbc-hk-uuid",
  "name": "HSBC Hong Kong Limited",
  "parent_tenant_id": "hsbc-parent-uuid",
  "tenant_type": "subsidiary",
  "created_at": "2025-08-05T10:00:00Z",
  "updated_at": "2025-08-05T11:30:00Z",
  "metadata": {
    "country": "Hong Kong",
    "business_unit": "retail_banking",
    "status": "active"
  }
}
```

**Constraints**:
- Cannot change tenant_type or parent_tenant_id
- Name uniqueness validation within hierarchy

### 5. DELETE /tenants/{tenant_id}
**Purpose**: Delete a tenant

**Response (204 No Content)**

**Business Rules**:
- Cannot delete parent tenant with active subsidiaries
- Cascading delete warnings for data relationships
- Soft delete implementation for audit trail

### 6. GET /health
**Purpose**: API health check

**Response (200 OK)**:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2025-08-05T12:00:00Z",
  "version": "1.0.0"
}
```

## Data Model Requirements

### Tenant Entity
```python
class Tenant:
    tenant_id: UUID (Primary Key)
    name: str (Required, max 200 chars)
    parent_tenant_id: UUID (Foreign Key, nullable)
    tenant_type: enum ('parent', 'subsidiary')
    created_at: datetime (Auto-generated)
    updated_at: datetime (Auto-updated)
    metadata: JSON (Optional additional data)
```

### Data Relationships
- Self-referencing relationship for parent-child hierarchy
- One parent can have multiple subsidiaries
- Subsidiaries cannot have their own subsidiaries (max 2 levels)

## Validation Requirements

### Input Validation
- All UUID fields must be valid UUID4 format
- String fields must be trimmed and non-empty
- JSON metadata must be valid JSON object
- Datetime fields must be ISO 8601 format

### Business Logic Validation
- Prevent circular parent-child relationships
- Enforce unique names within tenant hierarchy
- Validate tenant type consistency with parent relationship
- Ensure parent exists before creating subsidiary

## Error Handling

### Standard HTTP Status Codes
- 200: Successful operation
- 201: Resource created successfully
- 204: Resource deleted successfully
- 400: Bad request (validation errors)
- 403: Forbidden (access denied)
- 404: Resource not found
- 409: Conflict (duplicate name, constraint violation)
- 500: Internal server error

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Tenant name must be unique within hierarchy",
    "details": {
      "field": "name",
      "value": "HSBC Hong Kong",
      "constraint": "unique_name_per_parent"
    }
  }
}
```

## Security Requirements

### Row Level Security (RLS)
- Database-level tenant isolation
- Policy enforcement for all queries
- No bypass mechanisms in application code

### Data Access Patterns
- Tenant context must be set for all operations
- Parent tenants inherit access to subsidiary data
- Complete isolation between different parent organizations

## Integration Requirements

### Database Integration
- PostgreSQL 17.5 with RLS policies
- Async SQLAlchemy 2.0 with proper connection pooling
- Alembic migrations for schema management

### API Integration
- OpenAPI 3.0 documentation auto-generation
- JSON request/response format
- RESTful endpoint design principles