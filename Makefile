.DEFAULT_GOAL := help

VENV ?= .venv
PYTHON  := $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
UVICORN := $(if $(wildcard $(VENV)/bin/uvicorn),$(VENV)/bin/uvicorn,uvicorn)
PYTEST  := $(if $(wildcard $(VENV)/bin/pytest),$(VENV)/bin/pytest,pytest)
RUFF    := $(if $(wildcard $(VENV)/bin/ruff),$(VENV)/bin/ruff,ruff)
MYPY    := $(if $(wildcard $(VENV)/bin/mypy),$(VENV)/bin/mypy,mypy)
ALEMBIC := $(if $(wildcard $(VENV)/bin/alembic),$(VENV)/bin/alembic,alembic)

.PHONY: help dev dev-backend dev-frontend build test lint format typecheck db-migrate docker-up docker-down docker-logs

help: ## Show this help message
	@echo "Exam Study System - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""

dev: ## Start backend (:8000) and frontend (:5173) concurrently with hot-reload
	@./scripts/dev.sh

dev-backend: ## Run only FastAPI backend with auto-reload
	@$(UVICORN) app.main:app --reload --port 8000

dev-frontend: ## Run only Vite frontend dev server
	@cd frontend && bun run dev

build: ## Build React frontend SPA into frontend/dist
	@cd frontend && bun run build

test: ## Run backend unit & integration tests
	@$(PYTEST)

lint: ## Run Python (Ruff) and frontend (Oxlint) linters
	@echo "==> Linting backend (Ruff)..."
	@$(RUFF) check .
	@echo "==> Linting frontend (Oxlint)..."
	@cd frontend && bun run lint

format: ## Format code with Ruff
	@$(RUFF) format .
	@$(RUFF) check --fix .

typecheck: ## Run Mypy static type checking on app/
	@$(MYPY) app

db-migrate: ## Run Alembic database migrations to latest head
	@$(ALEMBIC) -c app/alembic.ini upgrade head

docker-up: ## Build and start the full stack with Docker Compose
	@docker compose up -d --build

docker-down: ## Stop all Docker Compose containers
	@docker compose down

docker-logs: ## Follow Docker Compose container logs
	@docker compose logs -f
