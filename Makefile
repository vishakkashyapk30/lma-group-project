# `make help` lists the targets. Targets that run Python need .venv: `make setup` creates it (needs-venv says so instead of a stack trace).
PY ?= .venv/bin/python

.PHONY: help needs-venv setup-full data data-check data-bundle data-install data-publish models models-dry-run datasets interim docker-up docker-down docker-build docker-test docker-logs setup stores testsets eval-rq1 eval-rq2 eval-ablations eval-features eval-safety eval-all frontend api lint test test-unit test-integration test-system test-frontend test-e2e test-models test-collect openai-spend hooks check-commits live-smoke

help:             ## list the targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:[^#]*## /\t/' | sort | awk -F'\t' '{printf "  %-20s %s\n", $$1, $$2}'

needs-venv:
	@test -x "$(PY)" || { echo "no $(PY): run 'make setup' first (it creates .venv and installs the package)" >&2; exit 1; }

setup:            ## create .venv (Python 3.11+), upgrade pip, install the package with the light extras (dev,data,testsets; EXTRAS=a,b to change), then install the git hooks (scripts/setup_dev.sh)
	@scripts/setup_dev.sh
	@$(MAKE) --no-print-directory hooks

setup-full:       ## setup plus the heavy extras (lance,eval,nli,ocr,speech: torch, docling, ...; several GB)
	@scripts/setup_dev.sh --full
	@$(MAKE) --no-print-directory hooks

datasets:         ## download the public datasets into data/raw (resumable; scripts/download_datasets.sh; see data/README.md)
	@scripts/download_datasets.sh

interim: needs-venv          ## convert data/raw into data/interim: orders.jsonl, statutes.jsonl, concordance_edges.jsonl, splits, feasibility report
	@scripts/build_interim.sh

data: needs-venv             ## make sure data/ is in place: skip if data-check passes, else install the team bundle (HF token) or explain how (scripts/data_ensure.sh)
	@scripts/data_ensure.sh

data-check: needs-venv       ## table of what is present or missing in data/ (interim, stores, testsets, gaps, hindi_native, kathbath, models); non-zero if required items are missing (REQUIRE_MODELS=1 to require models, REQUIRE_RAW=1 the raw data)
	@$(PY) scripts/_data_check.py $(if $(REQUIRE_MODELS),--require-models,)

data-bundle:      ## compress and checksum the data and raw source archives into ~/vakeel-data-bundle (scripts/data_bundle.sh; no upload)
	@scripts/data_bundle.sh $(BUNDLE)

data-install: needs-venv     ## install a data bundle into data/: make data-install SRC=<dir | URL | hf:repo> [FORCE=1] [RAW=0 skips the raw archive] (scripts/data_install.sh)
	@scripts/data_install.sh $(if $(FORCE),--force,) $(SRC)

data-publish:     ## owner only: upload the bundle folder to the private Hugging Face dataset (scripts/data_publish.sh)
	@scripts/data_publish.sh $(BUNDLE)

stores: needs-venv           ## build the seven shared stores from data/interim/orders.jsonl (plan §5)
	@scripts/build_stores.sh

testsets:         ## construct T1-T9 (plan §15.2)
	scripts/build_testsets.sh

eval-rq1:         ## RQ1 runs (Ada interactive shards; see scripts/ada/run_rq1.sh)
	@echo "TODO: run on Ada via scripts/ada/run_rq1.sh"; exit 1

eval-rq2:         ## RQ2 ingestion comparisons on T2
	@echo "TODO: scripts/ada/run_rq2_full.sh and run_rq2_vision.sh"; exit 1

eval-ablations:   ## A1-A10
	@echo "TODO: scripts/ada/run_ablations.sh"; exit 1

eval-features:    ## F1-F8
	@echo "TODO: scripts/ada/run_features.sh"; exit 1

eval-safety:      ## T7
	@echo "TODO: scripts/ada/run_t6_t7.sh"; exit 1

eval-all: eval-rq1 eval-rq2 eval-ablations eval-features eval-safety

openai-spend: needs-venv     ## OpenAI spend ledger: total spent, remaining, per model and per purpose
	$(PY) -m vakeel_sahayak.models.openai.ledger

api: needs-venv   ## FastAPI backend on :8000 (BACKEND_PORT to change)
	$(PY) -m uvicorn vakeel_sahayak.api.asgi:app --port $${BACKEND_PORT:-8000}

frontend:         ## Next.js dev server on :3000 (npm ci first if node_modules is missing; needs Node 20)
	@command -v npm >/dev/null 2>&1 || { echo "npm not found: install Node.js 20 (the Docker image uses 20) (https://nodejs.org)" >&2; exit 1; }
	cd frontend && { [ -d node_modules ] || npm ci; } && NEXT_PUBLIC_API_BASE=$${NEXT_PUBLIC_API_BASE:-http://localhost:8000} npm run dev

lint:             ## ruff + mypy + frontend lint
	@echo "TODO: ruff check src; mypy src; cd frontend && npm run lint"; exit 1

# Tests (see tests/README.md). Default pytest run skips the `gpu` and `models` markers (see pyproject.toml addopts).
test: test-unit test-integration test-system test-frontend  ## all default-marker tests (Python layers + vitest)

test-unit: needs-venv        ## tests/unit: schemas, contracts, tools, rights, ingestion, stores, agents, eval, ...
	$(PY) -m pytest tests/unit

test-integration: needs-venv ## tests/integration: modules wired together with fakes (no GPU)
	$(PY) -m pytest tests/integration

test-system: needs-venv      ## tests/system: plan §13.6 user flows 1-7 and the T7 safety suite (fakes, no GPU)
	$(PY) -m pytest tests/system

test-frontend:    ## vitest unit tests for the frontend (needs Node 20 and `cd frontend && npm ci`)
	@test -d frontend/node_modules || { echo "frontend/node_modules is missing: run 'cd frontend && npm ci' first (Node 20)" >&2; exit 1; }
	cd frontend && npm test

test-e2e:         ## Playwright specs with the backend mocked by route interception (needs browsers)
	@test -d frontend/node_modules || { echo "frontend/node_modules is missing: run 'cd frontend && npm ci' first (Node 20), then 'npx playwright install chromium'" >&2; exit 1; }
	cd frontend && npm run e2e

models: needs-venv           ## download the model tier in $$VS_MODELS (default T1; see scripts/download_models.sh)
	@scripts/download_models.sh $(MODELS_ARGS)

models-dry-run: needs-venv   ## list model sizes, licences and free disk for the tier; downloads nothing
	@scripts/download_models.sh --dry-run

test-models: needs-venv      ## tests needing real model weights or a GPU (@pytest.mark.models / gpu); run on the laptop or Ada
	$(PY) -m pytest -m "models or gpu" tests

test-collect: needs-venv     ## collection must stay clean
	$(PY) -m pytest --collect-only -q

# Docker (see DOCKER.md)
docker-build:     ## build the default images (backend + frontend)
	docker compose build

docker-up:        ## start the default stack in the background: http://localhost:3000
	docker compose up -d --build --wait

docker-down:      ## stop the stack (named volumes are kept; add -v to delete them)
	docker compose down

docker-test:      ## pytest + Vitest inside containers (Playwright: docker compose --profile test run --rm e2e)
	docker compose --profile test run --rm tests
	docker compose --profile test run --rm frontend-tests

docker-logs:      ## follow the stack's logs
	docker compose logs -f --tail=100

# Evaluation driver smoke runs (offline stand-ins; no GPU, no network, no API key)
smoke: needs-venv            ## run the case-0007 fixture end to end offline: prints the BailBrief grounds and statuses and the SparringRecord verdicts, exits 0
	VS_MODELS=offline VS_LLM_BACKEND=offline $(PY) -m vakeel_sahayak.eval.runners.driver smoke

sarvam-spend: needs-venv     ## show Sarvam spend and the cap in INR (models/sarvam/spend.py)
	$(PY) -m vakeel_sahayak.models.sarvam.spend
eval-smoke-all: needs-venv   ## run every implemented variant offline on 1 T1 dev case, about 40 minutes (writes a pass/fail table)
	VS_MODELS=offline VS_LLM_BACKEND=offline $(PY) -m vakeel_sahayak.eval.runners.driver smoke-all
eval-plan: needs-venv        ## print cases, tokens, cost (USD, INR) and hours of every job without running anything
	$(PY) -m vakeel_sahayak.eval.runners.driver plan --all
eval-smoke: needs-venv       ## run 3 T1 dev cases offline through the Full system (needs data/testsets/t1/dev.jsonl from the T1 builder)
	VS_MODELS=offline VS_LLM_BACKEND=offline $(PY) -m vakeel_sahayak.eval.runners.driver eval-smoke

hooks:        ## install the versioned git hooks (strips AI attribution from commit messages; needs git and perl)
	@git rev-parse --git-dir >/dev/null 2>&1 || { echo "not a git checkout: no hooks installed (clone the repository with git to commit)" >&2; exit 1; }
	@command -v perl >/dev/null 2>&1 || echo "warning: perl not found; the commit-msg hook needs it" >&2
	@git config core.hooksPath scripts/git-hooks
	@echo "hooks installed: core.hooksPath=scripts/git-hooks"

check-commits: ## fail if any commit in origin/main..HEAD names an AI assistant
	@scripts/check_commits.sh

live-smoke: needs-venv ## one tiny live call per hosted capability with public text only (keys from .env or the environment)
	$(PY) scripts/live_smoke.py all
