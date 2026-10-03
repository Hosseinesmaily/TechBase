# TechBase — make targets. See README.md.
# All targets run inside Docker by default. Use LOCAL=1 on machines without Docker
# (runs against the host interpreter/venv; backend needs DB_ENGINE=sqlite for some tasks).

LOCAL ?= 0
COMPOSE ?= docker compose

ifeq ($(LOCAL),1)
  PY  := python
  NPM := npm
else
  PY  := $(COMPOSE) run --rm --no-deps backend python
  NPM := $(COMPOSE) run --rm --no-deps frontend npm
endif

.PHONY: setup run test lint fmt typecheck migrate seed reindex eval down logs

setup: ## create .env, build images, migrate
ifeq ($(LOCAL),1)
	@test -f .env || cp .env.example .env
	@echo "LOCAL=1: run 'pip install -r backend/requirements/dev.txt' and 'npm install' manually."
else
	@test -f .env || cp .env.example .env
	$(COMPOSE) build
	$(MAKE) migrate
endif

run: ## docker compose up (dev stack)
	@test -f .env || cp .env.example .env
	$(COMPOSE) up

test: ## backend + frontend tests
	$(PY) -m pytest
	$(NPM) run test --if-present

lint: ## ruff check + format check + frontend typecheck
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(NPM) run typecheck --if-present

fmt: ## auto-format backend
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

typecheck: ## backend mypy (pure modules) + frontend typecheck
	$(PY) -m mypy apps
	$(NPM) run typecheck --if-present

migrate:
	$(PY) manage.py migrate

seed: ## demo data (Phase 1+)
	$(PY) manage.py seed_demo

reindex: ## reindex search + embeddings (Phase 3/4+)
	$(PY) manage.py reindex

eval: ## RAG evaluation against evals/golden_set.jsonl (Phase 4+)
	$(PY) manage.py run_evals

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f
