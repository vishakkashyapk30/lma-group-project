# AGENTS.md: start here (for coding agents and new teammates)

Vakeel-Sahayak.ai is an agentic bail-preparation engine for Indian legal-aid lawyers (LMA Group Project 2026, team of four). Six agents (Munshi intake, Peshkar dossier and Rights Radar, Sutradhar orchestrator, Vakeel drafter, Abhiyojak prosecution sparring, Pairokar batch desk) work over ten typed stores, with two human approval gates enforced in code. The research contribution is the agent harness, evaluated against simpler baselines.

## First day (copy these, in order)
```bash
make setup         # needs Python 3.11+; creates .venv, upgrades pip, installs `.[dev,data,testsets]` (no torch, no GPU libraries), copies .env.example to .env, installs the git hooks. Safe to re-run.
                   # `make setup-full` (or EXTRAS=dev,data,eval make setup) adds the heavy extras (torch, docling, ...; several GB). `make help` lists every target
make test-collect  # optional check: collection must be clean (about 4,700 tests); `.venv/bin/pytest tests/unit/scripts -q` checks the data scripts offline
make data          # data/ in place? skip. Else installs the team bundle (needs HF_TOKEN in .env or hf auth login, and membership of the Hugging Face organisation Vakeel-Sahayak), else tells you how to rebuild.
                   # It checks the token before the 1 GB download, retries 3 times, shows progress; tight disk: TMPDIR=/bigger/disk make data. A fresh clone needs no FORCE=1
                   # The bundle holds the raw source data too (Open India Law shards, IPC2BNS-Verify, Kathbath audio; about 1.8 GB): never refetch it from the web. RAW=0 skips it to save disk
make models        # the T1 helper models (BGE-M3, DeBERTa NLI, MiniCheck, Whisper small; about 5.5 GB); `make models-dry-run` lists sizes first
make data-check    # table of present/missing items (interim, stores, testsets, gaps, hindi_native, kathbath, models); non-zero if required items are missing
```
Handoff notes (what is done, not done, next steps) are in `docs/handoff/*.md`; data and model notes: `docs/handoff/data-and-models.md`, `data/README.md`.

## Read in this order
1. `split.md`: who does what now, file ownership, merge waves, PR and review rules (appendices).
2. `progress.md`: sections 0 to 0e hold the master to-do list, the data assessment, the plans written, the decisions, and the status of every workstream; section 5 has the per-phase test commands.
3. `docs/plan.md` (the design; v6, which applies the 25 edits of `docs/literature-review-and-usage.md` §7), `docs/architecture/skeleton.md` (module map and conventions).
4. `docs/evaluation-plan.md` (claims, baselines, metrics, the S/A/B/P variants) and `docs/literature-to-code-map.md` (which paper each variant comes from, with switch, module and test).
5. `docs/product-readiness.md` (what a finished product still needs), `docs/handoff/*.md` (per-workstream status notes: done, not done, next steps), `frontend/DESIGN.md` (design rules for the UI).

## Handoff notes hold decisions you cannot get from the code: read them before you edit
`docs/handoff/*.md` records, per workstream, what is done, what is not, known bugs, measurements and decisions (for example privacy-boundary policy choices, budget numbers, store-build caveats). Before you touch an area, read its note; when you stop, write or update one (done / not done / next steps / how to check background jobs).

| If you work on | Read first |
|---|---|
| hosted models, driver, privacy boundary, token and cost numbers, BM25 pruning | `pilot-hosted-model.md` |
| PDF intake, Munshi, citation index | `munshi-real-pdf-reading.md`, `data-and-models.md` |
| eval switches and variants | `ev-01-switches.md`, `eval-infrastructure.md`, `literature-sweep-1.md` to `literature-sweep-4.md` |
| test sets T2 to T9 | `testsets-t2-t9.md` |
| frontend | `workspace-redesign.md`, `landing-colour-motion.md`, `frontend/DESIGN.md` |

## Hard rules (do not break these)
- **No manual annotation or hand-made datasets.** Ground truth comes from court text, official tables, existing datasets, construction, or non-Qwen labeler agreement. No LLM-judge scores.
- **No AI attribution anywhere**: no `Co-Authored-By` trailer, no "Generated with ..." line, no AI mention in commits, PRs or documents. Only the four teammates are contributors. Commit as yourself. Run `make hooks` once after cloning (it installs a hook that strips such lines) and `make check-commits` before opening a PR.
- **Privacy:** raw client files stay on the user's machine. External model services (Sarvam, OpenAI) are OFF by default and gated by `VS_EXTERNAL=off|public|pseudonymised|consented` plus per-case consent; every external payload must pass the pseudonymisation boundary.
- **API keys only in environment variables** (`SARVAM_API_KEY`, `OPENAI_API_KEY`) or an untracked `.env`. Never commit, print or log a key. OpenAI spend is capped at 5 USD in code (default 4.50); check with `make openai-spend`.
- **Approvals only from counsel, enforced in code.** Export is impossible before Gate 2. No outcome predictions, no grant rates, no advice to the public.
- **Every new variant is opt-in** (a field in `src/vakeel_sahayak/orchestration/switches.py`), with default behaviour byte-identical, a paper citation in its docstring, and a row in `docs/literature-to-code-map.md`.
- **Frontend:** it must feel like a product. Follow `frontend/DESIGN.md` including "Things we do not do": no status dots, no stylised numerals, no eyebrow labels, no gradient or glow, short motion only (150 to 300 ms), no scroll-jacking, and none of the banned fonts.

## Run it
- Python: `make setup` (creates `.venv`), then use `.venv/bin/python` and `.venv/bin/pytest`. Offline stand-in models are the default (`models_mode()` is `offline` when `VS_MODELS` is unset, with or without a `.env`; the code never reads `.env`), so nothing needs a GPU or a key. Real or hosted models need an explicit `VS_MODELS=auto` (or `real`); see `docs/handoff/python-and-defaults.md`.
- One command for the whole stack: `docker compose up` (UI http://localhost:3000, API http://localhost:8000). The production UI is in live mode (an unreachable API shows an error, never sample data); build with `NEXT_PUBLIC_API_MODE=demo` for the sample case-0007 only. Ports: `FRONTEND_PORT`, `BACKEND_PORT`. Details in `DOCKER.md`.
- Without Docker (Node 20): `cd frontend && npm ci && npm run build && NEXT_PUBLIC_API_BASE=http://localhost:8000 npx next start -p 3000`, and `.venv/bin/python -m uvicorn vakeel_sahayak.api.asgi:app --port 8000`.
- Hosted model (OpenAI or Sarvam) for the evaluation driver: load the keys from the untracked `.env` only (`set -a; . ./.env; set +a`), then `VS_MODELS=auto VS_LLM_BACKEND=openai VS_EXTERNAL=pseudonymised VS_OPENAI_RUN_CAP_USD=0.30 .venv/bin/python -m vakeel_sahayak.eval.runners.driver eval-smoke --n 1 --out <dir>`. Use `pseudonymised`, not `public`: every agent role declares client text, and the driver pseudonymises each case's facts like the production intake (details in `docs/handoff/pilot-hosted-model.md`). For the real DeBERTa claim checker on CPU, install torch and `.[nli]`; without them `auto` falls back to the offline NLI and records it in the manifest.
- End to end offline: `make smoke` (case-0007 through the agents, Gate 1 approved, Gate 2 left closed, export blocked) and `make eval-smoke`.

## Tests (the full suite is slow; run by area)
- Per-area commands are in `progress.md` section 5. The broad regression (about 12 minutes, last result 3,351 passed, 16 skipped) is the command in `docs/handoff/literature-sweep-3.md`.
- Known failing until built (stubs): `tests/unit/export`, `tests/unit/eval/{test_metrics,test_stats}.py` (Harshita's metrics and statistics), 3 tests in `tests/unit/eval/test_ingestion_pipelines.py` that wait for helpers in `eval/metrics/ingestion.py`, parts of `tests/integration` and `tests/system` that still reach an export or API stub, and the old frontend tests (`frontend/tests`, `frontend/e2e`), which describe the earlier design.
- Each test gets its own data dir through `tests/conftest.py` (`VS_DATA_DIR`); do not make tests depend on `data/`.
- Tests encode the plan. Fix the code first; change a test only if it contradicts the plan, and mark it `# RECONCILED: <reason>`. Never weaken or delete tests.

## If data or models are missing: install them yourself, on your own machine
Never wait for someone to hand you data. Check, then install the bundle or build what is missing, in this order, and never commit any of it (it is gitignored):
0. **First try the team bundle** (a private Hugging Face dataset, the owner grants read access): `hf auth login` (or `HF_TOKEN` in the untracked `.env`), then
   `make data-install SRC=hf:Vakeel-Sahayak/vakeel-sahayak-data` (or `SRC=<folder or URL the owner shares>`; `FORCE=1` to overwrite). It verifies checksums, unpacks
   `interim`, `stores`, `testsets`, `gaps`, `eval` and, in a second archive, the raw source data (`data/raw`: Open India Law shards, IPC2BNS-Verify, Kathbath audio; `RAW=0` or `--no-raw` skips it to save about 1.8 GB), and checks row counts. Models are not in it (`make models`). Only if you have no bundle, rebuild with steps 1 to 4:
1. Check what exists: `ls data/raw data/interim data/stores models`, `df -h .` (you need about 10 GB free for the data and stores, more for model weights), and `cat data/raw/MANIFEST.json`.
2. Public datasets: `make datasets` (resumable; Open India Law bail shards, IPC2BNS-Verify, Kathbath). Then `make interim` and `make stores` (quick check first: `SAMPLE=2000 EMBEDDER=hashed-ngram make stores`; the full build took about 35 minutes). Helper models if a task needs them: `make models-dry-run`, then `make models`.
3. Items that need a person (HLDC on Hugging Face, the CrPC and NDPS statutes from India Code, API keys): do not guess or invent them. Record what is blocked in your handoff note under `docs/handoff/` and carry on with offline stand-ins and the small fixtures under `tests/fixtures`.
4. Run the area's tests after rebuilding to confirm nothing depends on the old state, and write down in your handoff note what you rebuilt and how long it took.

## What is NOT in the repository (you must recreate it)
- `data/` contents, `models/` weights, `.env` and `frontend/node_modules` are gitignored. Rebuild data with `make datasets`, `make interim`, then `make stores` (a quick sample: `SAMPLE=2000 EMBEDDER=hashed-ngram make stores`; the full build took about 35 minutes). Hugging Face gated sets (HLDC) and India Code statutes need a person; see `data/README.md`.
- The session's scratch paths named in `docs/handoff/*.md` (`/tmp/...`: screenshots, logs, snapshots) do not exist on your machine.
- The project owner's agent memory (preferences and decisions) lives outside the repo; everything that matters is restated above.

## Working habits that avoid trouble
- Prefer a few parallel agents at most, one per directory owner (see `split.md`); save as you go and write a short handoff note in `docs/handoff/` when you stop.
- Never stop a process with `pkill -f` or `pgrep -f` patterns that appear in your own command line (it kills your shell); find the PID by port with `ss -ltnp`.
- Start long jobs (store builds, downloads) in the background with `setsid nohup` and log to a file.
- Small PRs into `main`, squash-merged, one task ID each (see `split.md`).
