# split.md: who does what from here (written 2026-10-25)

This replaces the task assignments in `docs/team/*.md` where they differ, because a lot has changed since that plan was written (hosted LLMs, the redesigned frontend, the literature variants, the eval infrastructure). The ownership rules, PR template and history-sync steps in `docs/team/README.md` still apply.

**Rules this split follows (the team's original instruction):**
1. The remaining work is divided into four streams that run **in parallel and are as independent as possible**. Each person owns separate directories, so PRs rarely conflict.
2. **Harshita gets noticeably less work** (about half of the others), in well-scoped, low-coordination tasks that are not on the critical path.
3. Every task is delivered as small PRs into `main`, in the merge waves below.
4. No AI-assistant attribution in any commit or PR (a commit-msg hook strips it; see Wave 0).

Day 1 is the day all four of you have finished the history sync (Wave 0). Effort is in person-days and is an estimate.

## 1. Where the project stands

| Area | State |
|---|---|
| Six agents, stores, Rights Radar, privacy, event log | Built, tested offline (3,351 unit tests pass) |
| Hosted LLM clients | Sarvam (mocked tests) and OpenAI with a hard 5 USD cap (mocked tests); no live call yet |
| Eval infrastructure | Driver, baselines B0 to B6, ablations A1 to A10, T1 test set built on real data |
| Literature variants | S1 to S5, S7 to S11, S14, S15, S17, P7 built, off by default; S6, S12, S13, S16 started (sweep 4 was cut off) |
| Frontend | Redesigned (shell, landing, guided workspace); old tests fail on purpose |
| Data | Stores built (1.76 GB); Kathbath done; statutes, HLDC, e-SCR need a person |
| **Not built** | LangGraph flow, real API routes, DOCX export, metrics and statistics, T2 to T9 builders, features F1 to F8, real model runs, any result number |

## 2. Streams and owners

| Stream | Owner | Why this person (suggestion; swap freely) |
|---|---|---|
| A. Critical path: graph, API, integration and system tests | **Shravani** | Built the core, Munshi routing and Sarvam; knows the agents and tools |
| B. Product surface: frontend, DOCX export, hearing card, real-API integration | **Satvik** | Built the workspace, pages and frontend tests |
| C. Evaluation and runs: variants, builders, runs, the freeze | **Vishak** | Owns the eval infrastructure, models, data and the API keys |
| D. Metrics, legal content, documents, QA (lighter) | **Harshita** | Isolated, well-scoped tasks; tests already exist for the metrics |

### Directory ownership (one owner per directory; shared files are listed after)

| Path | Owner |
|---|---|
| `src/vakeel_sahayak/orchestration/{graph,fallback_state_machine}.py`, `api/**`, `tools/runtime.py` | Shravani |
| `tests/integration/**`, `tests/system/**`, `tests/unit/{api,orchestration}/**` | Shravani |
| `frontend/**`, `src/vakeel_sahayak/export/**`, `tests/unit/export/**` | Satvik |
| `src/vakeel_sahayak/{eval,testsets,finetune}/**` (except `eval/metrics/**`, `eval/stats/**`), `agents/**`, `batch/**`, `models/**`, `pipelines/**`, `stores/**`, `ingestion/**`, `configs/**`, `scripts/**`, `docker/**`, `data/**` (except `data/gaps/**`) | Vishak |
| `src/vakeel_sahayak/eval/metrics/**`, `eval/stats/**`, `rights/**` (rules text only), `data/gaps/**`, `docs/proposal/**`, `README.md`, `docs/qa/**` | Harshita |

**Shared files** (`pyproject.toml`, `Makefile`, `compose.yaml`, `tests/conftest.py`, `frontend/lib/types.ts`, `frontend/lib/api.ts`, `orchestration/switches.py`, `progress.md`): small PRs, one owner stewards each (pyproject, Makefile, compose: Vishak; `types.ts`, `api.ts`: Satvik; `switches.py`: Vishak). Ask the steward in the PR rather than editing in parallel. Each person updates only their own status table in `docs/team/<name>.md`; nobody edits `progress.md` except Vishak.

## 3. Wave 0: before anyone starts (Day 1)

| Task | Owner | Done when |
|---|---|---|
| History sync (backup unpushed work, reset to the new `origin/main`; steps in `docs/team/README.md`) | all four | `git log origin/main..` is empty or only backups |
| Contract PR: freeze the API response shapes the frontend and backend share (rights report, hearing card, library search with `sc_root` and `good_law`, `CaseSummary.last_activity`, gate checklist), `docs/api/contract.md` | Shravani + Satvik, Vishak reviews | merged by noon Day 1 |
| Shared commit-msg hook (`scripts/git-hooks/commit-msg`, `make hooks`), PR template, `scripts/check_commits.sh` | Vishak | merged Day 1 |

## 4. Tasks per person

### Shravani: critical path (17 days)

| ID | Task | Files | Acceptance | Tests that must go green | Depends on | Branch | Days |
|---|---|---|---|---|---|---|---|
| SH-01 | LangGraph flow: Munshi → Peshkar → Gate 1 (interrupt) → Sutradhar ⇄ Vakeel ⇄ Abhiyojak → Gate 2 (interrupt) → export; SQLite checkpointer; change-set path | `orchestration/graph.py` | A case runs end to end and pauses at both gates; resumes after a restart | `tests/unit/orchestration/test_graph.py` | Wave 0 | `feat/graph` | 4 |
| SH-02 | Plain-Python fallback with the same gate rules | `orchestration/fallback_state_machine.py` | Same results as SH-01 on the same input | `test_fallback_state_machine.py` | SH-01 | `feat/graph-fallback` | 1 |
| SH-03 | API: app wiring (`create_app` mounts every router), cases, upload, ingestion, dossier (read and patch), dates, rights | `api/**` | Frontend strict mode loads a real case | `tests/unit/api/**` (cases, upload) | SH-01 interface | `feat/api-read` | 3 |
| SH-04 | API: chat, draft, brief, spar, prep, SSE events, budget | `api/routers/{chat,events,...}` | A draft is produced and streamed | `tests/unit/api/**` | SH-03 | `feat/api-agents` | 3 |
| SH-05 | API: gates, export route (blocked before Gate 2), desk and library (with the server-side `before` date) | `api/routers/{gates,export,desk,library}` | Export is rejected before Gate 2 | `tests/unit/api/**` | SH-03 | `feat/api-gates` | 2 |
| SH-06 | **Swagger / OpenAPI documentation**: `/docs` and `/openapi.json` live, exported `docs/api/openapi.json`, `docs/api/README.md` | `api/app.py`, `docs/api/**` | The spec lists every route with examples and error shapes | none (docs check) | SH-03 to SH-05 | `docs/api-swagger` | 1 |
| SH-07 | Integration tests green | `tests/integration/**` | All 107 pass or are marked with a reason | the folder | SH-01 to SH-05 | `test/integration` | 1.5 |
| SH-08 | System tests green (flows 1 to 7, T7 safety) | `tests/system/**` | All pass offline | the folder | SH-07 | `test/system` | 1.5 |
| SH-09 | Live smoke of the two hosted backends once keys are set; policy gate check | `scripts/` | One call per capability passes under `VS_EXTERNAL=public`; the OpenAI ledger stays under cap | none | Vishak's keys | `chore/live-smoke` | 0.5 |

Shravani depends on Satvik for the real-API client (SH-03 shapes) and on Satvik's DOCX for the export route (SH-05). Everything else can start on Day 2.

### Satvik: product surface (16 days)

| ID | Task | Files | Acceptance | Tests | Depends on | Branch | Days |
|---|---|---|---|---|---|---|---|
| SA-01 | Frontend tests updated to the redesigned shell, landing and workspace (Vitest then Playwright), `# RECONCILED` reasons | `frontend/tests`, `frontend/e2e` | Vitest and Playwright green on a production build | both | none | `test/frontend-reconcile` | 2.5 |
| SA-02 | Real-API mode: strict mode in product builds (no silent fallback to case-0007), clear error states, settings page (model mode, Sarvam mode, data folder) | `frontend/lib/api.ts`, `frontend/app/settings` | A failed API call shows an error, never someone else's case | Vitest | Wave 0 contract | `feat/frontend-real-api` | 2 |
| SA-03 | Workspace review by eye: mobile layout, source panel, chat and Details drawers, confirm dialogs; fix what is wrong; add the missing "Workspace principles" to `DESIGN.md` | `frontend/components/workspace/**` | Screenshots of every step at 390 and 1440 px reviewed and fixed | Playwright | SA-01 | `fix/workspace-visual-qa` | 2 |
| SA-04 | DOCX court-ready application: synopsis, List of Dates, grounds, prayer, annexure index, AI-draft label | `export/application.py`, `list_of_dates.py`, `sections.py`, `templates/` | A brief produces a valid DOCX that opens in Word | `tests/unit/export/**` | Wave 0 | `feat/export-docx` | 3 |
| SA-05 | Hearing-prep card render and PDF export | `export/hearing_card.py`, `pdf.py` | Card and PDF download | `tests/unit/export/**` | SA-04 | `feat/export-hearing-pdf` | 1.5 |
| SA-06 | Case-end-to-end UI flow against the real API (upload → facts → rights → draft → export) | `frontend/**` | Flow 1 and flow 3 complete in a browser | Playwright | SH-03 to SH-05 | `feat/frontend-flow` | 2 |
| SA-07 | Onboarding and empty states, Hindi UI strings, keyboard shortcuts, axe accessibility audit and fixes | `frontend/**` | Zero serious axe violations | Playwright axe | SA-03 | `fix/frontend-a11y` | 1.5 |
| SA-08 | Features F5 (application assembly check) and F6 (hearing card) evaluation arms | `eval/features/f5*.py`, `f6*.py` (agreed with Vishak) | Both write results to the contract path | `tests/unit/eval/test_features.py` (F5, F6) | SA-04, SA-05 | `feat/eval-f5-f6` | 1.5 |

### Vishak: evaluation, runs and models (19 days)

| ID | Task | Files | Acceptance | Tests | Depends on | Branch | Days |
|---|---|---|---|---|---|---|---|
| VI-01 | Finish literature sweep 4 (S6/B5 router, S12 topology, S16 chunking, S13 workflow search); handoff note is `docs/handoff/literature-sweep-4.md` | `agents/sutradhar/store_prior.py`, `stores/chunk_strategies.py`, `eval/**` | Each variant switch-gated, cited, tested | the sweep's new tests | none | `feat/literature-sweep-4` | 1.5 |
| VI-02 | Sweep 5: apply the 25 proposed edits to `docs/plan.md`; check every citation in `docs/literature-to-code-map.md` against the official page | `docs/plan.md`, `docs/literature-*.md` | Plan matches the code; every row has a verified link | none | VI-01 | `docs/plan-v6` | 1.5 |
| VI-03 | `runs.yaml` jobs and driver dispatch for the implemented variants (S1 to S5, S7 to S11, S14, S15, S17, P7, B5); preregistration file | `configs/eval/runs.yaml`, `eval/runners/**`, `docs/preregistration.md` | `make eval-smoke` runs every variant offline | `tests/unit/eval` | VI-01 | `feat/eval-jobs` | 1.5 |
| VI-04 | Non-Qwen labeler for gold (OpenAI or Sarvam on public data), agreement report, rule-only comparison | `pipelines/gold/**`, `models/labeler.py` | G1 and G3 agreed labels with kappa; coverage table | `tests/unit/pipelines/gold` | keys | `feat/gold-labeler` | 1 |
| VI-05 | Wire the Supreme Court metadata into the citation index; re-measure resolution (was 19%, and 0 of 80 in T1) | `pipelines/citation_graph/**`, `pipelines/store_builders/**` | Resolution rate reported; G2 coverage up | `tests/unit/pipelines` | none | `feat/citation-sc-metadata` | 1.5 |
| VI-06 | Test-set builders T2 (messy bundles), T3 (change sets), T5 (batch), T6 (chat), T8 (speech), T9 (citation formats) | `testsets/**` | Each builds on the real data | `tests/unit/testsets/**` | none | `feat/testsets-t2-t9` | 5 |
| VI-07 | Feature evaluations F1 to F4, F7, F8 and ingestion pipelines P1 to P6 | `eval/features/**`, `eval/ingestion/**` | Arms run offline; results written to the contract path | `tests/unit/eval/test_features.py`, `test_ingestion_pipelines.py` | VI-06 | `feat/eval-features` | 4 |
| VI-08 | Pilot with a hosted model: tokens per case on 10 dev cases, price check against the 5 USD cap | `eval/runners`, `data/eval/token_measure.json` | Mean tokens and dollars per case are known | none | keys, SH-01 not needed | `chore/pilot` | 1 |
| VI-09 | The freeze (`prereg-v1`, `eval-freeze-v1` tags) and the real runs (RQ1 main, B0L, B0S, B6, sparring 2×2, must variants) on Sarvam and within the OpenAI cap | runs | Outputs for the floor sizes saved with manifests | none | VI-03, VI-04, Harshita's metrics | operational | 3 |
| VI-10 | Shared hook, PR template, `make hooks` (Wave 0) and `docker/` real profile checks | `scripts/`, `docker/` | `make hooks` works | none | none | `chore/hooks` | 0.5 |
| VI-11 | Fine-tuning (stretch): teacher dossiers, span filter, QLoRA | `finetune/**` | Only if the freeze is met early | `tests/unit/finetune` | VI-09 | `feat/finetune` | stretch |

### Harshita: lighter stream (9.5 days)

| ID | Task | Files | Acceptance | Tests | Depends on | Branch | Days |
|---|---|---|---|---|---|---|---|
| HA-01 | Metrics and statistics: factor recall and precision, recall@k, MRR, nDCG, unsupported-fact rate, McNemar, paired bootstrap, Wilcoxon, Holm; null-agent audit | `eval/metrics/**`, `eval/stats/**` | The existing tests pass (about 70 currently fail on stubs) | `tests/unit/eval/test_metrics.py`, `test_stats.py` | none | `feat/metrics-stats` | 4 |
| HA-02 | Statutes by hand: save CrPC and NDPS PDFs from India Code in a browser, extract s.41, 41A, 50, 57, 167, 436, 436A, 437, 438, 439, the First Schedule and NDPS s.37 into `data/gaps/statutes/*.jsonl` with a source URL on each row; then `scripts/build_stores.sh --only statutes` | `data/gaps/**` | Rows load; statute tool tests pass | `tests/unit/stores`, `tools_law_case` | none | `data/statutes-gap` | 1.5 |
| HA-03 | Verify the Rights Radar rule texts against the bare acts and fill `last_verified` dates in `configs/rights_rules.yaml` (coordinate edits with Vishak) | `configs/rights_rules.yaml`, `docs/qa/rights-verification.md` | Each of the 7 rules has a source and date, or an open question | `tests/unit/rights` | none | `docs/rights-verification` | 1.5 |
| HA-04 | Access requests: HLDC on Hugging Face (IL-TUR `bail`), IPC2BNS-Verify licence email, optional e-SCR permission request; record outcomes in `data/README.md` | `data/README.md` | Requests sent; status written down | none | none | `docs/data-requests` | 0.5 |
| HA-05 | Proposal `.tex` and `.pdf` brought to v5 (use `docs/proposal/figures/architecture_v5`), new references checked | `docs/proposal/**` | PDF builds and matches `proposal.md` | none | none | `docs/proposal-v5` | 1 |
| HA-06 | README quick-start (the docker one-liner, ports, optional keys), manual QA script `docs/qa/manual-test.md` (step-by-step test cases a teammate can run) | `README.md`, `docs/qa/**` | A teammate can follow it from a clean machine | none | SH-04 for the final steps | `docs/readme-qa` | 1 |

## 5. Load

| Person | Committed days | Share of the heaviest |
|---|---|---|
| Vishak | 19 | 100% |
| Shravani | 17 | 89% |
| Satvik | 16 | 84% |
| Harshita | 9.5 | 50% |

Capacity is about 3.5 to 4 weeks, so about 17 to 20 days each. Vishak's stretch item (fine-tuning) is dropped unless the freeze is met early.

## 6. Pull requests and merges

- **Integration branch:** `main`. Every PR targets `main`; no long-lived branches. Squash-merge.
- **PR size:** small, one task ID each, about 400 changed lines or fewer. Branch names are in the tables (`feat/…`, `fix/…`, `docs/…`, `test/…`, `chore/…`).
- **PR template:** task ID, what changed, the test commands run (and their counts), screenshots for UI changes, any `# RECONCILED` with its reason.
- **Review rotation:** Vishak reviews Shravani; Shravani reviews Satvik; Satvik reviews Vishak; Harshita's PRs are reviewed by whoever owns the touched directory, and Harshita is second reviewer on docs and QA PRs.
- **Required before merge:** the area's test command from `progress.md` section 5; `ruff check src`; for the frontend `tsc`, `lint`, Vitest; no AI attribution in any commit.
- **Waves (merge order and what each unlocks):**

| Wave | PRs | Unlocks |
|---|---|---|
| 0 | history sync, contract PR, commit hook | everyone |
| 1 | SH-01, SH-02, SA-01, SA-04, VI-01, VI-04, VI-05, HA-01, HA-02, HA-04 | graph, tests, DOCX, metrics, statutes (independent of each other) |
| 2 | SH-03, SH-04, SA-02, SA-05, VI-02, VI-03, VI-06, HA-03 | real API, real-API frontend, jobs, builders |
| 3 | SH-05, SH-06, SA-03, SA-06, VI-07, VI-08, HA-05 | gates and export route, Swagger, end-to-end UI, features, pilot |
| 4 | SH-07, SH-08, SA-07, SA-08, VI-09 (the freeze and runs), HA-06 | green integration and system tests, a11y, results, README and QA |

- **Freeze:** the evaluation freeze (`prereg-v1`, `eval-freeze-v1`) happens when VI-03, VI-04 and HA-01 are merged and the pilot (VI-08) has measured the budget. Product changes after the freeze that touch evaluated behaviour are tagged `post-freeze`.
- **Cuts if time runs short:** fine-tuning first, then features F7, F8 and ingestion P4 to P6, then S13 and S16 runs; never the gates in code, the privacy boundary or the source links.

## 7. Decisions to confirm before Day 1

1. Branch protection on `main` and squash merge (recommended).
2. Where the OpenAI key lives (Vishak's environment only) and who may spend from it; Sarvam is the default for the big runs.
3. Whether `agents_14b` should use Sarvam or OpenAI by default for the real runs (recommended: Sarvam, with OpenAI for the cap-checked pilot and the labeler).
4. Which teammate reviews Harshita's metrics PR (recommended: Vishak, since he owns the evaluation).
