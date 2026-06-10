# Honeybook Gallery — developer entrypoints.
# `make help` lists everything. Local dev uses a backend venv + npm; the
# Docker path (`make up`) needs nothing but Docker installed.

PY ?= python3.11
VENV := backend/.venv
GALLERY ?= g_001

.DEFAULT_GOAL := help

## ---------------------------------------------------------------------------
## Local toolchain
## ---------------------------------------------------------------------------

.PHONY: install
install: ## Create backend venv + install backend and frontend deps
	$(PY) -m venv $(VENV)
	$(VENV)/bin/python -m pip install -U pip
	$(VENV)/bin/python -m pip install -e "./backend[dev,ai]"
	cd frontend && npm install
	cd frontend && npx playwright install chromium

.PHONY: dev-backend
dev-backend: ## Run the FastAPI backend with reload on :8000
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

.PHONY: dev-frontend
dev-frontend: ## Run the Vite dev server on :5173 (proxies /api + /static to :8000)
	cd frontend && npm run dev

.PHONY: otp
otp: ## Send an OTP for GALLERY (default g_001); code lands in the backend terminal
	cd backend && .venv/bin/python -m app.cli send-otp $(GALLERY)

.PHONY: seed
seed: ## Force re-create seed photos + galleries (idempotent; keeps favorites)
	cd backend && .venv/bin/python -m app.cli reseed

## ---------------------------------------------------------------------------
## Tests — every layer
## ---------------------------------------------------------------------------

.PHONY: test
test: test-backend test-frontend ## Run backend + frontend unit/component suites

.PHONY: test-all
test-all: test-backend test-frontend test-personas personas test-e2e ## Every layer incl. E2E + personas

.PHONY: test-backend
test-backend: ## pytest: unit, contract (schemathesis), property (hypothesis), CLI
	cd backend && .venv/bin/python -m pytest

.PHONY: test-frontend
test-frontend: ## Vitest: composable, api client, components
	cd frontend && npm run test:unit -- --run

.PHONY: test-e2e
test-e2e: ## Playwright: full OTP -> gallery -> favorite flow against the dev stack
	cd frontend && npm run test:e2e

.PHONY: personas
personas: ## AI synthetic-persona suite, in-process (offline; add --live with a key)
	cd ai-testing && ../$(VENV)/bin/python -m persona_suite

.PHONY: test-personas
test-personas: ## pytest the persona framework itself (meta-tests)
	cd ai-testing && ../$(VENV)/bin/python -m pytest tests -q

.PHONY: lint
lint: ## ruff + mypy (backend), ruff (ai-testing), vue-tsc (frontend)
	cd backend && .venv/bin/ruff check . && .venv/bin/mypy app
	$(VENV)/bin/ruff check ai-testing
	cd frontend && npm run typecheck

## ---------------------------------------------------------------------------
## Docker — one command to a running app
## ---------------------------------------------------------------------------

.PHONY: up
up: ## Build + start the full stack (open http://localhost:8080)
	docker compose up --build -d
	@echo ""
	@echo "  App:      http://localhost:8080/galleries/g_001"
	@echo "  Get code: make docker-otp GALLERY=g_001   (then: make docker-logs)"
	@echo ""

.PHONY: down
down: ## Stop the stack (keeps the favorites volume)
	docker compose down

.PHONY: docker-logs
docker-logs: ## Tail the backend logs (this is where OTP codes appear)
	docker compose logs -f backend

.PHONY: docker-otp
docker-otp: ## Send an OTP inside the running backend container
	docker compose exec -T backend python -m app.cli send-otp $(GALLERY)

## ---------------------------------------------------------------------------
## Housekeeping
## ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Remove generated DB, seed photos, build + test artifacts
	rm -rf backend/app.db backend/seed/photos/*.jpg data
	rm -rf frontend/dist frontend/coverage frontend/playwright-report frontend/test-results
	rm -rf ai-testing/reports
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
