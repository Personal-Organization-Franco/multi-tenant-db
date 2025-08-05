# Multi Tenant Database

The goal of this project is to setup a multi tenant database using SQLAlchemy and FastAPI, implementing row level security (RLS) to ensure that each tenant can only access their own data.

# Project Structure

```
.
├── .env
├── .gitignore
├── README.md
├── docs
├── scripts
├── alembic
├── app
│   ├── __init__.py
│   ├── api
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── routes
│   │       ├── __init__.py
│   │       └── tenant.py
│   ├── config.py
│   ├── database
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── models.py
│   │   └── session.py
│   ├── main.py
│   └── schemas.py
├── .venv
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
