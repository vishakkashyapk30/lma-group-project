# Skeleton targets; every recipe is a stub until implemented.
PY ?= .venv/bin/python

.PHONY: setup stores testsets eval-rq1 eval-rq2 eval-ablations eval-features eval-safety eval-all frontend api lint test test-unit test-integration test-system test-frontend test-e2e test-models test-collect

setup:            ## create .venv and install (scripts/setup_dev.sh)
	@echo "TODO: scripts/setup_dev.sh"; exit 1

stores:           ## build the seven shared stores from data/interim/orders.jsonl (plan §5)
	@scripts/build_stores.sh

testsets:         ## construct T1-T9 (plan §15.2)
	@echo "TODO: scripts/build_testsets.sh"; exit 1

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

test-models:      ## tests needing real model weights or a GPU (@pytest.mark.models / gpu); run on the laptop or Ada
	$(PY) -m pytest -m "models or gpu" tests

test-collect:     ## collection must stay clean
	$(PY) -m pytest --collect-only -q
