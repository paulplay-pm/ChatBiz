# =============================================================================
# credential-management service — Makefile
# All commands assume CWD = services/credential/  (the service root).
# =============================================================================

SERVICE   := credential
IMAGE     := chatbiz/$(SERVICE)
COMPOSE   := docker compose --project-directory ../../infrastructure -f ../../infrastructure/docker-compose.yml

# --- runtime configuration (override on the command line) --------------------
DATABASE_URL ?= postgresql+asyncpg://chatbiz:chatbiz@localhost:5432/credential
REDIS_URL    ?= redis://localhost:6379/0
LOG_LEVEL    ?= info

# Detect whether we're inside a virtualenv; if so prefer in-venv binaries.
VENV ?= .venv
ifeq ($(wildcard $(VENV)/bin/python),)
	PYTHON ?= python3
	PIP    ?= pip3
else
	PYTHON ?= $(VENV)/bin/python
	PIP    ?= $(VENV)/bin/pip
endif

# Always run uvicorn from the project root, with the app package on PYTHONPATH.
export PYTHONPATH := $(CURDIR)

# =============================================================================
# Phony targets
# =============================================================================
.PHONY: help install dev test test-unit test-integration test-e2e migrate \
        run lint fmt sec precommit clean build build-nc docker-up docker-down \
        docker-logs docker-ps

# -----------------------------------------------------------------------------
# help — print available targets
# -----------------------------------------------------------------------------
help: ## Show this help (default target)
	@awk 'BEGIN {FS = ":.*?## "; printf "Usage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
		/^[a-zA-Z0-9_.-]+:.*?## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)

# -----------------------------------------------------------------------------
# install — local virtualenv + dev dependencies
# -----------------------------------------------------------------------------
install: ## Create a local venv and install runtime + dev dependencies
	@if [ ! -d "$(VENV)" ]; then \
		echo ">>> creating venv at $(VENV)"; \
		$(PYTHON) -m venv $(VENV); \
	fi
	$(PIP) install --upgrade pip wheel setuptools
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	@echo ">>> venv ready. Activate with:  source $(VENV)/bin/activate"

# -----------------------------------------------------------------------------
# dev — bring up the full local stack (postgres + redis + credential + migrate)
# -----------------------------------------------------------------------------
dev: docker-up ## Start the full local docker-compose stack in the foreground

docker-up: ## Start stack detached
	$(COMPOSE) up -d postgres redis credential-migrate credential credential-cron
	@echo ">>> Stack up. Tail logs with:  make docker-logs"

docker-down: ## Stop the local stack
	$(COMPOSE) down

docker-logs: ## Tail logs for the credential service
	$(COMPOSE) logs -f --tail=100 credential

docker-ps: ## Show running services
	$(COMPOSE) ps

# -----------------------------------------------------------------------------
# test — unit + integration (testcontainers) tests
# -----------------------------------------------------------------------------
test: ## Run the full test suite (unit + integration via testcontainers)
	$(PYTHON) -m pytest -v

test-unit: ## Run unit tests only (skip integration / e2e markers)
	$(PYTHON) -m pytest -v -m "not integration and not e2e"

test-integration: ## Run integration tests (requires Docker for testcontainers)
	$(PYTHON) -m pytest -v -m integration

test-e2e: ## Run end-to-end tests (requires full stack: `make dev`)
	$(PYTHON) -m pytest -v -m e2e

# -----------------------------------------------------------------------------
# migrate — Alembic schema management
# -----------------------------------------------------------------------------
migrate: ## Apply Alembic migrations to HEAD
	$(PYTHON) -m alembic upgrade head

migrate-down: ## Roll back the most recent migration
	$(PYTHON) -m alembic downgrade -1

migrate-new: ## Create a new migration (usage: make migrate-new MSG="add foo")
	@if [ -z "$(MSG)" ]; then echo "MSG is required, e.g. make migrate-new MSG=add_foo"; exit 1; fi
	$(PYTHON) -m alembic revision --autogenerate -m "$(MSG)"

migrate-history: ## Show migration history
	$(PYTHON) -m alembic history --verbose

# -----------------------------------------------------------------------------
# run — local development server (no docker, assumes DATABASE_URL points at
#       a reachable Postgres; most devs use `make dev` instead).
# -----------------------------------------------------------------------------
run: ## Run uvicorn locally (no docker)
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level $(LOG_LEVEL)

# -----------------------------------------------------------------------------
# lint / fmt — ruff + mypy
# -----------------------------------------------------------------------------
lint: ## Run ruff + mypy
	@echo ">>> ruff check"
	ruff check .
	@echo ">>> ruff format --check"
	ruff format --check .
	@echo ">>> mypy"
	mypy app

fmt: ## Auto-format with ruff
	ruff check --fix .
	ruff format .

# -----------------------------------------------------------------------------
# sec — bandit security scan
# -----------------------------------------------------------------------------
sec: ## Run bandit security scan
	bandit -r app -ll

# -----------------------------------------------------------------------------
# pre-commit — install / run hooks
# -----------------------------------------------------------------------------
precommit: ## Run pre-commit against all files
	pre-commit run --all-files

precommit-install: ## Install pre-commit hooks into .git
	pre-commit install

# -----------------------------------------------------------------------------
# build — container image
# -----------------------------------------------------------------------------
build: ## Build the credential docker image
	docker build -t $(IMAGE):dev -t $(IMAGE):$$(git rev-parse --short HEAD) .

build-nc: ## Build with --no-cache
	docker build --no-cache -t $(IMAGE):dev .

# -----------------------------------------------------------------------------
# clean — throwaway artifacts
# -----------------------------------------------------------------------------
clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
