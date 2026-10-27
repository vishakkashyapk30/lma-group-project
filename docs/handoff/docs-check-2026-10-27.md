# Docs check, 2026-10-27 (Vishak)

Scope: every tracked Markdown file except `docs/report/**`, `docs/handoff/code-final.md`, `docs/handoff/sweep-openai-teammate.md` (other agents) and `src/**`, `tests/**` (code docs). Edits are surgical (a dated "Checked by Vishak 2026-10-27" line or a one-sentence fix); nothing committed. Verified against `make help`, `pyproject.toml`, `.env.example`, `src/vakeel_sahayak/models/openai/config.py`, `make openai-spend`, `make sarvam-spend`, `pytest --collect-only` (4,944 of 4,951 collected, 7 deselected), `data/stores`, and a script that greps every backticked repo path, every `make <target>` and every relative Markdown link.

## Checks that came out clean
- Commands: every `make` target named in AGENTS.md, README.md and data/README.md exists in the Makefile; every script named there exists (`scripts/*.sh` are executable; `sweep_dev.py` and `extract_gap_statutes.py` are run as `python scripts/...`, so no exec bit is needed). Every `VS_*` name used in the docs appears in code or `.env.example`.
- Dataset repo name is `Vakeel-Sahayak/vakeel-sahayak-data` everywhere (18 mentions, no variant). Python minimum is 3.11 in `pyproject.toml`, Makefile help, README and AGENTS (older 3.10 text survives only in dated notes, now annotated). `.env.example` has `VS_MODELS=offline`, and the code default is offline.
- Budgets: OpenAI hard max 5.00, default cap 4.50 (`models/openai/config.py`), sweep ceiling 4.90 (`configs/eval/sweep_dev.yaml`, set by exporting `VS_OPENAI_CAP_USD=4.90`); Sarvam cap default 25 INR via `VS_SARVAM_CAP_INR` (ceiling 500 per `.env.example`); the owner's Sarvam key is limited to INR 30 in total by the owner's correction (`sweep_dev.yaml`). Spent on 2026-10-27: OpenAI 2.2008 USD (of 4.50), Sarvam INR 5.4945 (of 25).
- No broken relative Markdown links. Store sizes in `data-and-models.md` match `data/stores/MANIFEST.json` except statutes (below).

## Per file
| File | Result |
|---|---|
| AGENTS.md | edited: test count 4,700 to about 4,950; "known failing (stubs)" replaced by the verified state (export, metrics, stats and ingestion tests pass; finetune and frontend not re-run); regression line points to the 2026-10-27 per-file results; budget line adds the 4.90 sweep ceiling and the Sarvam cap and `make sarvam-spend`; two rows added to the read-first table. The "API routes are stubs" wording the first-day text once had is already gone in HEAD. |
| CLAUDE.md | OK (imports AGENTS.md) |
| README.md | edited: status line no longer says DOCX export, hearing card and real-API mode are unbuilt; layout adds `compose.yaml`, `docs/handoff`, `docs/status`, `docs/results` |
| DOCKER.md | OK (Python 3.12 image; no API token option mentioned; `compose.yaml` only passes `HF_TOKEN`, so nothing to fix). Whether the full stack works end to end in live mode was not re-run (unverified). |
| NOTICE | not read in full (licence text); flagged below |
| split.md | edited: section 1 "Not built" row and the Frontend row corrected; header note with the VI task state (from `docs/status/vishak.md`) and the list of promised files that do not exist |
| progress.md | edited: banner that everything below 0f is a log and the "A. Make the system run end to end" list and the Docker "routes are stubs" note are outdated; 0f open decisions (three red tests resolved) and spend corrected |
| data/README.md | edited: `sweep-runs/` folder noted; commands, scripts and repo name verified |
| docs/plan.md | OK (v6 header present) |
| docs/evaluation-plan.md | edited: header (plan is v6; scoring, variants and sweep plan exist), the v5 reference, "runners are stubs" and the Section 7 stub audit annotated |
| docs/product-readiness.md | edited: dated banner (API, export, model download script and statutes are no longer stubs/missing; what is still open); stale `TopNav.tsx` path fixed (which component now holds the local-only indicator is unverified). The 2026-10-24 task list is kept as written. |
| docs/preregistration.md, docs/literature-*.md, docs/architecture/skeleton.md, docs/proposal/**, docs/research/**, docs/course/** | not edited; only the path/link check was run (clean). Their numbers were not re-verified. |
| docs/handoff/dev-baselines.md | edited: banner (t1dev-017 fixed, hosted b0l duplicate of b0 and real B0L is Sarvam-105B, Qwen3-32B Ada plan dropped, old runs superseded, ledger now 2.2008) |
| docs/handoff/regression-2026-10-26-b.md | edited: the "Still red (3 tests)" heading says resolved (the later section was already correct) |
| docs/handoff/regression-2026-10-26.md | edited: banner pointing to the -b note |
| docs/handoff/pilot-hosted-model.md | edited: banner (pilot numbers old; superseded by the caption-name and spotlight-tag fixes; current spend) |
| docs/handoff/ada-qwen32b.md | edited: banner (dropped; B0L on Sarvam) |
| docs/handoff/data-and-models.md | edited: banner (bundle layout: derived + raw archives, `sweep-runs/`, org dataset; chronological note) and a flag for the stale statutes manifest |
| docs/handoff/fresh-clone-fixes.md | edited: Python 3.11 minimum, collected count |
| docs/handoff/eval-features.md | edited: "metrics/export are stubs" lines annotated |
| docs/handoff/sweep-dev.md, sweep-satvik.md, eval-jobs.md, product-complete.md, eval-complete.md, python-and-defaults.md, citation-sc-metadata.md, others | OK as far as checked; eval-jobs.md already names the 4.90 and INR 30 correction |
| docs/status/satvik.md | edited: dated line (Python 3.11 minimum, `make setup` is real); no words rewritten |
| docs/status/harshita.md | edited: dated line (`unsupported_fact.py` is implemented now) |
| docs/status/vishak.md | edited: dated line (spend; "dev-set sweep on hold" row outdated) |
| docs/status/shravani.md | OK (nothing clearly outdated found) |
| frontend/README.md | edited: "Skeleton only" replaced by the built state |
| frontend/FOUNDATION_NOTES.md | edited: "still stubs" annotated |
| frontend/DESIGN.md, .github/pull_request_template.md | OK (not changed) |
| docs/results/** | no README exists (`docs/results/dev-sweep/` is empty on this machine) |

## Flagged for owners
1. `data/stores/MANIFEST.json` still says statutes 1,411 rows and "CrPC, NDPS missing", but `data/stores/law/statutes.sqlite` has 1,426 rows (CrPC 10, NDPS 5). Owner: Vishak (refresh the manifest, rebuild the data bundle and `make data-publish`; whether the published bundle holds the 1,426-row store is unknown).
2. Promised files that do not exist: `docs/api/contract.md`, `docs/api/openapi.json`, `docs/api/README.md` (SH-02, SH-06, Shravani), `docs/qa/manual-test.md` and `docs/qa/rights-verification.md` (HA-03, HA-06, Harshita).
3. Rights rule verification (`last_verified`, PR-46) by Harshita: all seven rules report `unverified` (`product-complete.md`).
4. `tests/unit/finetune` (82 failed on 2026-10-26) and the frontend Vitest/Playwright suites were not re-run today; AGENTS.md says so. Owner: Vishak and Satvik.
5. Which frontend file now holds the local-only indicator (PR-32) is unverified (Satvik).
6. NOTICE entries "to verify" need a licence check (`data-and-models.md` item 6); not re-read today.
7. The `docs/status/*.md` and `docs/handoff/*.md` of other teammates were annotated, not rewritten; owners may want to refresh their own notes.
8. `docs/handoff/code-final.md` and `sweep-openai-teammate.md` were not checked (being written by another agent); `docs/report/**` not checked.

## Contradictions found, and which doc is authoritative
| Topic | Contradiction | Authoritative |
|---|---|---|
| API and export built or stub | `product-readiness.md`, old `progress.md` sections and `frontend/*` said stub; `split.md` and README said unbuilt | the code and tests (API 42 routes, export tests pass), then `split.md` section 1 (now corrected) |
| Python minimum | `fresh-clone-fixes.md`, `docs/status/satvik.md` say 3.10 | `python-and-defaults.md` and `pyproject.toml`: 3.11 |
| OpenAI cap | 4.50 default (AGENTS, code) vs 4.90 (sweep) | code default 4.50, hard max 5.00; 4.90 is the sweep ceiling set in the shell (`sweep-dev.md`); `eval-jobs.md` already states the correction |
| OpenAI spent | 0.2 (progress 0f earlier), 1.51 (sweep notes), 2.2008 now | `make openai-spend` |
| Owner's Sarvam budget | default cap 25 (code, `.env.example`) vs INR 30 in total (owner correction) | INR 30 for the owner's key (`sweep-dev.md`); 25 is the code default |
| B0L | hosted `b0l` stand-in, Qwen3-32B on Ada, Sarvam-105B | Sarvam-105B single pass (`sweep-dev.md`); the stand-in is a duplicate of b0 |
| Dev sweep state | `docs/status/vishak.md` "on hold" vs `sweep-dev.md` "baselines rerun on the pinned tag" | `sweep-dev.md` |
| Statutes rows | `data/stores/MANIFEST.json` 1,411 vs the store 1,426 | the store itself (flag 1) |
| Three red tests | `regression-2026-10-26-b.md` table vs its own later section; `progress.md` 0f open decisions | the later section of the -b note (tests reconciled, code left as is) |
| Plan version | `evaluation-plan.md` header cites plan v5 | `docs/plan.md` is v6 |
| Test count | AGENTS 4,700, fresh-clone-fixes 4,678, regression notes 4,227/4,288 (different scopes) | `pytest --collect-only`: 4,944 collected on 2026-10-27 |
