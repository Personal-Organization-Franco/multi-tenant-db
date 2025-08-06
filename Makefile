# Multi-Tenant Database API - Development Makefile
# Provides convenient shortcuts for common development tasks

.PHONY: help install install-dev install-test clean lint format test test-cov test-unit test-integration dev-server db-up db-down db-reset migrate security-check pre-commit-install pre-commit-run docs docs-serve

# Default target
help: ## Show this help message
	@echo "Multi-Tenant Database API - Development Commands"
	@echo "================================================"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Installation and Dependencies
install: ## Install production dependencies only
	uv sync --no-dev

install-dev: ## Install all dependencies including dev tools
	uv sync --all-extras

install-test: ## Install test dependencies only
	uv sync --extra test

# Cleaning
clean: ## Clean build artifacts, cache, and temporary files
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

# Code Quality
lint: ## Run all linting tools
	@echo "Running ruff linter..."
	uv run ruff check src/ tests/
	@echo "Running mypy type checker..."
	uv run mypy src/
	@echo "Running bandit security scanner..."
	uv run bandit -r src/ -f json

format: ## Format code with ruff
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

# Testing
test: ## Run all tests
	uv run pytest

test-cov: ## Run tests with coverage report
	uv run pytest --cov=src/multi_tenant_db --cov-report=html --cov-report=term-missing

test-unit: ## Run only unit tests
	uv run pytest -m "unit"

test-integration: ## Run only integration tests  
	uv run pytest -m "integration"

test-fast: ## Run tests without slow markers
	uv run pytest -m "not slow"

test-tenant: ## Run multi-tenant specific tests
	uv run pytest -m "tenant"

test-parallel: ## Run tests in parallel (faster)
	uv run pytest -n auto

# Development Server
dev-server: ## Start development server with hot reload
	uv run uvicorn src.multi_tenant_db.main:app --host 0.0.0.0 --port 8000 --reload

# Database Management
db-up: ## Start database services (Docker Compose)
	docker compose up -d

db-down: ## Stop database services
	docker compose down

db-reset: ## Reset database (WARNING: destroys all data)
	docker compose down -v
	docker compose up -d
	sleep 5
	$(MAKE) migrate

db-logs: ## Show database logs
	docker compose logs -f postgres

# Database Migrations
migrate: ## Run database migrations
	uv run alembic upgrade head

migrate-auto: ## Generate automatic migration from model changes
	uv run alembic revision --autogenerate -m "Auto-generated migration"

migrate-manual: ## Create empty migration file for manual changes
	@read -p "Enter migration message: " msg; \
	uv run alembic revision -m "$$msg"

migrate-downgrade: ## Downgrade database by one revision
	uv run alembic downgrade -1

migrate-history: ## Show migration history
	uv run alembic history

# Security
security-check: ## Run security vulnerability scan
	uv run bandit -r src/ -f json
	uv run pip-audit

# Pre-commit Hooks
pre-commit-install: ## Install pre-commit hooks
	uv run pre-commit install

pre-commit-run: ## Run pre-commit hooks on all files
	uv run pre-commit run --all-files

# Documentation
docs: ## Build documentation
	uv run mkdocs build

docs-serve: ## Serve documentation with auto-reload
	uv run mkdocs serve

docs-deploy: ## Deploy documentation to GitHub Pages
	uv run mkdocs gh-deploy

# Environment Setup
env-copy: ## Copy .env.example to .env
	cp .env.example .env
	@echo "Copied .env.example to .env - remember to update values!"

# Development Workflow Shortcuts
setup: clean install-dev env-copy db-up migrate pre-commit-install ## Full development environment setup
	@echo "✅ Development environment ready!"
	@echo "Run 'make dev-server' to start the application"

check: lint test-fast ## Quick quality check (lint + fast tests)

full-check: lint test security-check ## Full quality check (lint + all tests + security)

# CI/CD Simulation
ci: clean install-dev lint test-cov security-check ## Simulate CI pipeline locally

# Quick references
dev: dev-server ## Alias for dev-server
test-watch: ## Run tests in watch mode (requires pytest-watch)
	uv run ptw

# Docker shortcuts
docker-build: ## Build Docker image
	docker build -t multi-tenant-db:latest .

docker-run: ## Run application in Docker container
	docker run -p 8000:8000 --env-file .env multi-tenant-db:latest