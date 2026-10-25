# Skeleton targets; every recipe is a stub until implemented.
PY ?= .venv/bin/python

.PHONY: models models-dry-run datasets interim docker-up docker-down docker-build docker-test docker-logs setup stores testsets eval-rq1 eval-rq2 eval-ablations eval-features eval-safety eval-all frontend api lint test test-unit test-integration test-system test-frontend test-e2e test-models test-collect openai-spend hooks check-commits live-smoke

setup:            ## create .venv and install (scripts/setup_dev.sh)
	@echo "TODO: scripts/setup_dev.sh"; exit 1

datasets:         ## download the public datasets into data/raw (resumable; scripts/download_datasets.sh; see data/README.md)
	@scripts/download_datasets.sh

interim:          ## convert data/raw into data/interim: orders.jsonl, statutes.jsonl, concordance_edges.jsonl, splits, feasibility report
	@scripts/build_interim.sh

stores:           ## build the seven shared stores from data/interim/orders.jsonl (plan §5)
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

openai-spend:     ## OpenAI spend ledger: total spent, remaining, per model and per purpose
	$(PY) -m vakeel_sahayak.models.openai.ledger

api:              ## FastAPI backend
	@echo "TODO: scripts/run_api.sh"; exit 1

frontend:         ## Next.js dev server
	@echo "TODO: cd frontend && npm install && npm run dev"; exit 1

lint:             ## ruff + mypy + frontend lint
	@echo "TODO: ruff check src; mypy src; cd frontend && npm run lint"; exit 1

# Tests (see tests/README.md). Default pytest run skips the `gpu` and `models` markers (see pyproject.toml addopts).
test: test-unit test-integration test-system test-frontend  ## all default-marker tests (Python layers + vitest)

test-unit:        ## tests/unit: schemas, contracts, tools, rights, ingestion, stores, agents, eval, ...
	$(PY) -m pytest tests/unit

test-integration: ## tests/integration: modules wired together with fakes (no GPU)
	$(PY) -m pytest tests/integration

test-system:      ## tests/system: plan §13.6 user flows 1-7 and the T7 safety suite (fakes, no GPU)
	$(PY) -m pytest tests/system

test-frontend:    ## vitest unit tests for the frontend (needs `cd frontend && npm install`)
	cd frontend && npm test

test-e2e:         ## Playwright specs with the backend mocked by route interception (needs browsers)
	cd frontend && npm run e2e

models:           ## download the model tier in $$VS_MODELS (default T1; see scripts/download_models.sh)
	@scripts/download_models.sh $(MODELS_ARGS)

models-dry-run:   ## list model sizes, licences and free disk for the tier; downloads nothing
	@scripts/download_models.sh --dry-run

test-models:      ## tests needing real model weights or a GPU (@pytest.mark.models / gpu); run on the laptop or Ada
	$(PY) -m pytest -m "models or gpu" tests

test-collect:     ## collection must stay clean
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
smoke:            ## run the case-0007 fixture end to end offline: prints the BailBrief grounds and statuses and the SparringRecord verdicts, exits 0
	VS_MODELS=offline VS_LLM_BACKEND=offline $(PY) -m vakeel_sahayak.eval.runners.driver smoke

eval-smoke:       ## run 3 T1 dev cases offline through the Full system (needs data/testsets/t1/dev.jsonl from the T1 builder)
	VS_MODELS=offline VS_LLM_BACKEND=offline $(PY) -m vakeel_sahayak.eval.runners.driver eval-smoke

hooks:        ## install the versioned git hooks (strips AI attribution from commit messages)
	git config core.hooksPath scripts/git-hooks
	@echo "hooks installed: core.hooksPath=scripts/git-hooks"

check-commits: ## fail if any commit in origin/main..HEAD names an AI assistant
	@scripts/check_commits.sh

live-smoke:   ## one tiny live call per hosted capability with public text only (keys from .env or the environment)
	.venv/bin/python scripts/live_smoke.py all
