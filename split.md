# split.md: who does what from here (written 2026-10-25)

This replaces the earlier team plan (the former `docs/team/` folder, now removed), because a lot has changed since it was written (hosted LLMs, the redesigned frontend, the literature variants, the eval infrastructure). The PR and review rules, history-sync steps, freeze and definition of done are in the appendices at the end of this file (copied from the old team plan, which has been removed).

**Rules this split follows (the team's original instruction):**
1. The remaining work is divided into four streams that run **in parallel and are as independent as possible**. Each person owns separate directories, so PRs rarely conflict.
2. **Harshita gets noticeably less work** (about half of the others), in well-scoped, low-coordination tasks that are not on the critical path.
3. Every task is delivered as small PRs into `main`, in the merge waves below.
4. No AI-assistant attribution in any commit or PR (a commit-msg hook strips it; see Wave 0).

Day 1 is the day all four of you have finished the history sync (Wave 0). Effort is in person-days and is an estimate.

## 1. Where the project stands

| Area | State |
|---|---|
| Six agents, stores, Rights Radar, privacy, event log | Built, tested offline |
| Hosted LLM clients | OpenAI (hard 5 USD cap, ledger) and Sarvam (INR spend ledger, cap from `VS_SARVAM_CAP_INR`) both pass live smoke tests; the driver has run Full on 3 dev cases with `gpt-6-luna` (about 0.0078 USD per case) |
| Eval infrastructure | Driver with one entry for every variant (`run --system`, `plan`, `smoke-all`), runs.yaml jobs with costs, preregistration template, gold-source sweep job registered; scoring is built (`eval/scoring`, with M5 and the citation and abstention metrics, 2026-10-27); manifests carry `git_sha`, `git_dirty`, `code_tree_hash` and scoring refuses mixed code; the dev-set sweep plan and runner are in `docs/handoff/sweep-dev.md` |
| Literature variants | S1 to S18, P5 to P8, B5 built and switch-gated (S15b built 2026-10-27, so the registry equals the full table; S6 and B5 need a trained store prior; S14b, S14c, S16, S16b are studies, not per-case arms); plan v6 applies the 25 edits and the citations are verified |
| Test sets and gold | T1 to T9 built (T7 safety, driver case rows for T2, T5, T7, native Hindi High Court set for T2); gold G1 to G7 by agreement (primary) with the rule-only gold as a declared secondary |
| Features and ingestion | F1 to F4, F7, F8 and P1 to P6 arms run offline; F5, F6 need the export modules; P3, P4 need Docling and a vision model |
| Graph and API | LangGraph flow and the API routes with Swagger built by Shravani (graph unit tests pass; her API tests pass except 2 traced to a Sutradhar bug) |
| Frontend | Redesigned (shell, landing, guided workspace); old tests fail on purpose; real-API mode not done |
| Data | Stores rebuilt with the current T1 splits, SC metadata and SCC links; statutes (CrPC, NDPS, First Schedule flags) from official PDFs; Kathbath complete; HLDC and indictrans2 access pending; team copy is the private organisation dataset `Vakeel-Sahayak/vakeel-sahayak-data` (`make data`) |
| **Not built** | DOCX export and hearing card, real-API frontend mode, metrics and statistics (Harshita), real-model result numbers, a trained store prior (S6, B5), the model-backed S13 arm, the M18 stopped-too-early replay, the Rights rule verification by Harshita (`last_verified`, PR-46); the rescoring loop of the gold sweep is part of `scoring score --gold-source both` |

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

**Shared files** (`pyproject.toml`, `Makefile`, `compose.yaml`, `tests/conftest.py`, `frontend/lib/types.ts`, `frontend/lib/api.ts`, `orchestration/switches.py`, `progress.md`): small PRs, one owner stewards each (pyproject, Makefile, compose: Vishak; `types.ts`, `api.ts`: Satvik; `switches.py`: Vishak). Ask the steward in the PR rather than editing in parallel. Each person keeps a short status list in their own file under `docs/status/<name>.md` (create it on first use); nobody edits `progress.md` except Vishak.

## 3. Wave 0: before anyone starts (Day 1)

| Task | Owner | Done when |
|---|---|---|
| History sync (backup unpushed work, reset to the new `origin/main`; steps in appendix B) | all four | `git log origin/main..` is empty or only backups |
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

---

# Appendices (carried over from the earlier team plan)

These sections were copied from the former `docs/team/README.md` before that folder was removed. The task IDs inside them (PR-xx, EV-xx, TM-xx, wave tables from the old plan) belong to the OLD plan: use the IDs in section 4 of this file instead. The rules themselves (review, merge, history sync, freeze, definition of done) still apply.

## A. Pull request, review and merge rules

**Integration branch.** `main` is the merged baseline and the only integration branch. Every PR targets `main`. There are no long-lived branches: a branch lives at most three working days and is deleted at merge. `ideation-v1` and `ideation-proposal` become read-only after the sync (nobody pushes or opens PRs against them).

**Branch names.** `feat/<area>-<short>`, `fix/<area>-<short>`, `docs/<short>`, `chore/<short>`, for example `feat/api-gates`, `fix/system-t7`, `docs/qa-manual-script`. The suggested names in the per-person files follow this.

**PR size.** One task ID per PR (a task may use several PRs: "part 1", "part 2"). At most about 400 changed lines excluding generated fixtures and lock files; if a PR will be larger, split it by module. A PR that touches another owner's path says so in its first line ("hook-in, at most 30 lines").

**PR title and template.** Title: `PR-03: wire create_app and dependencies` or `EV-07: thin driver and runners (part 1)`. The template (`.github/pull_request_template.md`, created by TM-02) is:

```
Task IDs: PR-xx / EV-xx / TM-xx (one)
Wave and target day:
What changed (3 to 6 lines, plain English):
Paths touched outside my ownership (hook-in, at most 30 lines, owner reviewed): none / list
Contract change: no / yes (label contract)
Tests run (paste the command and the last line of output):
- ruff check src:
- area tests:
- make test-collect:
- frontend (if UI): npm run typecheck, npm run lint, npm test (and e2e if a flow changed):
Screenshots (required for UI changes; before and after):
Checklist:
- [ ] one task ID, at most about 400 changed lines
- [ ] no "# RECONCILED" without a reason on the same line ("# RECONCILED: <why>")
- [ ] no test made to pass by catching NotImplementedError
- [ ] scripts/check_commits.sh origin/main passes (no AI-attribution lines in commits)
- [ ] my status table is updated after merge
Post-freeze label (after eval-freeze-v1 only): post-freeze:fix / arm / product / behaviour
```

**Review rotation.** A PR needs one approval. The first reviewer follows the rotation, so each person learns another person's area.

| Author | First reviewer | Second reviewer (required for) |
|---|---|---|
| Shravani | Vishak | Satvik, for any PR that touches gates, export or the graph (PR-01, PR-06, PR-07, PR-16) |
| Vishak | Satvik | Shravani, for any PR that changes `Switches`, the freeze or the preregistration |
| Satvik | Shravani | Vishak, for the arms in his packages (EV-12) and for anything that touches `export/` output used by F5 and F6 |
| Harshita | the owner of the area she touched: Vishak for `eval/metrics`, `eval/stats`, statutes and rights; Satvik for frontend hook-ins | none; Shravani reviews her QA and README PRs by following them |

Harshita is also a second reviewer, for docs and QA PRs of the others. The first review comes within one working day; Wave 0 and blockers within four hours. Reviewers check the diff against the task's acceptance line, the tests pasted, and the ownership table.

**Required checks before merge** (the author runs them and pastes the last lines; a reviewer may re-run; the optional CI workflow of TM-02 runs the first three and the commit check):

| Area | Commands |
|---|---|
| Any Python change | `ruff check src`; `make test-collect` (collection stays clean); `scripts/check_commits.sh origin/main` |
| orchestration, record, privacy, tools (Shravani) | `python -m pytest tests/unit/orchestration tests/unit/record tests/unit/privacy -q`; `make test-integration` for graph and gates PRs; `make test-system` once PR-72 is done |
| api and export (Satvik, Shravani) | `python -m pytest tests/unit/api tests/unit/export tests/unit/tools_drafting -q`; `python -m pytest tests/integration/test_api_routes.py -q` |
| agents and truth maintenance | `python -m pytest tests/unit/agents/<name> tests/unit/truth_maintenance -q`; `python -m pytest tests/integration/test_vakeel_abhiyojak_sparring.py -q` |
| ingestion, models, stores, pipelines (Vishak) | `python -m pytest tests/unit/ingestion tests/unit/models tests/unit/stores tests/unit/pipelines -q`; `python -m pytest tests/integration/test_munshi_to_peshkar.py -q` |
| eval, testsets, finetune (Vishak, Harshita) | `python -m pytest tests/unit/eval tests/unit/testsets tests/unit/finetune -q` (only the files of your task; the rest still fail until implemented) |
| rights, configs (Harshita) | `python -m pytest tests/unit/rights tests/unit/config -q` |
| Frontend | `cd frontend && npm run typecheck && npm run lint && npm test`; when a flow changed, `npm run build && npm run e2e` against the production build (not `next dev`) |
| Docker or compose | `docker compose config` and `docker compose build <service>` for the service touched |
| Real models | `make test-models` on the laptop or Ada only; never in CI |

Rules that apply to every PR: no `# RECONCILED` without a reason on the same line (`# RECONCILED: <why>`), and the reviewer must agree with the reason; a test is changed only when it contradicts `docs/plan.md`, never to make it pass; no `# ASSUMPTION:` is silently turned into a fixed value; **no AI-assistant attribution in any commit message, PR description or file** (the shared hook strips it; `scripts/check_commits.sh` fails on it).

**Merge method: squash merge.** One task ID is one commit on `main`: the history reads as a task list, a bad task is reverted with one `git revert`, and the PR title and description become the commit message, so the hook and the check script see only text we control (set GitHub's default for squash to "pull request title and description"). Branch commits inside a PR can be messy. The author merges after approval, updates the branch with `git pull --rebase origin main` (no merge commits into feature branches), and deletes the branch. Nobody force-pushes `main`; protect it (T-D5).

**Co-fix rule.** Integration and system tests are fixed by the owner of the package that fails, labelled `co-fix`, within one working day. Shravani coordinates; she does not fix other people's packages.

## B. History sync after the history rewrite

The commit messages were rewritten to remove a trailer, so every commit hash changed. Vishak force-pushes the rewritten `main`, `ideation-v1` and a new `ideation-proposal` that preserves the old `main` history. **After the push, `main` is the merged baseline (the full current project); `ideation-v1` and `ideation-proposal` are read-only.**

**Rule 1: nobody pushes to `main` or `ideation-v1` (or any branch that still contains old commits) until Vishak writes "force-push done" in the team channel.** A push of an old branch would bring the old hashes back.

#### 5.1 Vishak (D0), in this order

1. Make sure nobody is mid-push; post "freeze pushes".
2. Create `ideation-proposal` from the rewritten old `main`; push it: `git push origin ideation-proposal`.
3. Push the rewritten `main` and `ideation-v1`: `git push --force-with-lease origin main ideation-v1`.
4. Verify: `git ls-remote origin` shows the new tips; `git log origin/main --format=%B | grep -i 'co-authored-by\|generated with'` prints nothing.
5. Re-target any open GitHub PR to `main` or close it; post "force-push done" with the new tip hash of `main`. Then set branch protection on `main` (T-D5).

#### 5.2 Everyone else (run after "force-push done"; about 15 minutes)

Do this in your existing clone. If you would rather re-clone, jump to the last paragraph.

1. **Save what is not on GitHub yet.** For every local branch with commits that were never pushed (including `main` and `ideation-v1`):
   ```
   git status                          # commit or stash local edits first: git stash push -u -m before-sync
   git branch backup/<yourname>-main main
   git branch backup/<yourname>-<branch> <branch>
   git log --format='%H %s' origin/ideation-v1..ideation-v1 > ~/unpushed-<yourname>.txt   # run BEFORE the fetch: it lists your unpushed commits (old hashes)
   ```
2. **Fetch.** `git fetch origin --prune`
3. **Reset local `main` to the new `main`.** `git switch main && git reset --hard origin/main`. **Warning: this discards every local-only commit on `main`.** That is safe only because step 1 saved them under `backup/...`.
4. **Reset the other rewritten branches.** `git switch -C ideation-v1 origin/ideation-v1` and `git switch -C ideation-proposal origin/ideation-proposal` (read-only from now on).
5. **Move your unpushed commits onto the new `main`.** Pick one way:
   - *Rebase onto (keeps the order, easiest for a whole branch).* The old remote tip is still in the reflog of the remote-tracking branch, so:
     ```
     git switch -c feat/<area>-<short> backup/<yourname>-<branch>
     OLD=$(git rev-parse origin/ideation-v1@{1})        # the old pushed tip, before the rewrite
     git rebase --onto origin/main $OLD feat/<area>-<short>
     ```
     If `@{1}` is not what you expect (check with `git reflog show origin/ideation-v1`), take the hash of the last commit you had pushed from `~/unpushed-<yourname>.txt` (the line just above the first unpushed commit in `git log` of the backup branch).
   - *Cherry-pick (best for a few commits).* `git switch -c feat/<area>-<short> origin/main` then `git cherry-pick <hash1> <hash2> ...` using the hashes (oldest first) from `~/unpushed-<yourname>.txt`. A cherry-pick that says "empty" means that change is already in `main`: skip it.
6. **Check.** `git log --oneline origin/main..HEAD` must list only the commits you meant to keep (nothing else, no duplicates of old work); `git diff origin/main --stat` must show only your files; `make test-collect` stays clean.
7. **Install the shared hook** once TM-02 has merged (D1): `make hooks`. Until then the local hook in `.git/hooks/commit-msg` is yours only; it is not shared.
8. Push only your feature branch (`git push -u origin feat/...`), never `main`.

*If your clone is tangled*, clone fresh (`git clone <url> vakeel-fresh`), then bring your commits over from the old clone: `git remote add old ../<old-clone>`, `git fetch old`, and cherry-pick the unpushed hashes. Keep the old clone until your PR is merged.

#### 5.3 The versioned hook (task VI-10, Vishak, Wave 0)

The hook in `.git/hooks/commit-msg` is local only. TM-02 adds `scripts/git-hooks/commit-msg` (strips AI-attribution trailers and lines from the message) and a `make hooks` target that runs `git config core.hooksPath scripts/git-hooks`. `scripts/check_commits.sh <range>` is the same check as a script (fails on any attribution line and on `# RECONCILED` without a reason) and goes into the PR template. Everyone runs `make hooks` once after D1.

## C. Evaluation freeze and definition of done

#### 8.1 Sync points

| What | When | Who | Length |
|---|---|---|---|
| Stand-up sync | Monday and Thursday: D1, D4, D6, D9, D11, D14, D16, D19 | all four | 15 minutes: blockers and cross-owner dependencies due in the next three days; no status reading |
| End-of-week demo | Friday: D5, D10, D15, D20 | all four | 20 minutes: each person shows what merged, live |
| Velocity check | D5 and D10 (inside the demo) | all four | Each person says days spent against plan. If someone is at least 0.5 day ahead, they pull the next stretch item from their queue; if behind, the item on the tail list (section 1.3) drops at once |
| Evaluation decision on Tier B and C | D12 (evaluation plan E-D5) | Vishak, with the measured tokens per case | decided with the numbers of EV-09 |
| Freeze meeting | D14 | all four | the checklist of 8.2 read out, then the tags |
| Feature freeze | end of D18 | all four | D19 and D20 take only fixes |
| Blockers | any time | whoever is blocked | post in the team channel and tag the owner; the owner answers within four working hours |

#### 8.2 The evaluation freeze

**Rule.** The freeze is a commit on `main` that carries the preregistration (`docs/preregistration.md`, git tag `prereg-v1`) and a code tag `eval-freeze-v1`. After it nothing under test is tuned; blind-slice ids are hashed into the preregistration; the scoring entry point refuses blind ids without the tag (EV-07).

**Date.** Evaluation plan section 7.3 puts the freeze at the start of week 2 (D6). That assumed the graph, the exports and the evaluation modules existed; they are stubs today, and the preregistration needs the driver, the metrics, T1 and the dev-tuning run (job 3). The plan therefore proposes **D14 (Thursday of week 3), hard limit D15** (decision T-D1). The Ada window after the freeze is then D15 to D20: about 75 nominal node-hours, about 52 usable after the 30 percent buffer. The preregistration states the floor sizes (RQ1 main at 150 cases and 2 runs for Full and B4, sparring 2x2 at 100 cases) and the claims not run.

**Entry checklist (all must be green on D14):**
1. EV-01 merged; the defaults of `Switches` leave `variant()` equal to `full` (test).
2. EV-02: `tests/unit/eval/test_stats.py` and `test_metrics.py` pass, including the null-agent audit.
3. EV-03: T1 manifests with hashes; the blind ids (80 of the 200) drawn with a seed and hashed; the pool is High Court only.
4. EV-05 baselines and EV-06a wrappers merged.
5. EV-07: the driver completes case-0007 and 10 dev cases with real models on Ada; scripted counsel approves a gate only when the scenario says so; unapproved export still blocked.
6. EV-11 part 1: δ, ε, the pass^3 bar and the answerable-factor rule are written from the 50 dev orders.
7. PR-28 and PR-29 merged (statutes and full stores), so retrieval is the system that will be measured.
8. The measured tokens per case of Full are in `data/eval/token_measure.json`, and the preregistration's run sizes are recomputed from it.

**What may change after the freeze, and how it is tagged.** Every PR after `eval-freeze-v1` that touches a path listed in the preregistration's "systems and sets" carries a label and a title prefix:

| Label | Meaning | Allowed? | Record |
|---|---|---|---|
| `post-freeze:fix` | A bug fix that does not change any system under test | Yes | one line in the "Deviations" section of the preregistration |
| `post-freeze:arm` | Code for a non-default switch value (an arm not yet run: S8, S9, S10, S15, S1, S3, S7, S17); the default Full path is unchanged, proved by the prompt-hash test | Yes, until the arm's first run | a preregistration addendum committed before that arm's first run |
| `post-freeze:product` | API, frontend, export, packaging, documentation (not an input of RQ1 or the ablations) | Yes | none; the numbers do not cover it |
| `post-freeze:behaviour` | Changes how Full behaves | Only for a safety or privacy defect | listed as a deviation in the report; a smoke subset is re-run; tag `eval-patch-<n>` |

Planned post-freeze work and its label: PR-13 and PR-14 are `post-freeze:product` but must merge before the F5 and F6 runs; PR-16, PR-38, PR-39, PR-40 are `product`; PR-23 is `post-freeze:fix` unless it touches the routing ladder (then `behaviour`); EV-12, EV-13, EV-14 are `arm`.

#### 8.3 Definition of done

**A PR is done when:** the acceptance line of the task is met; the required checks of section 4 are pasted in the PR; one approval (two where required); squash-merged to `main`; no attribution line; the author's status table says merged with the day.

**A task is done when** all its parts are merged and the tests named for it in the owner's file pass with the default markers.

**The Preview release v0.9 is done when** (from `docs/product-readiness.md` section 4.3, stop-ship lists): `/api/*` is live and the UI never shows demo data unless asked (PR-03, PR-45); flows 1, 2, 3 and 5 run in a browser against the live backend on the offline stand-ins (PR-04 to PR-07); export is refused before Gate 2 at the HTTP layer and the DOCX and hearing card download after it, both carrying the label (PR-13, PR-14, PR-16, PR-37); open NEEDS_REVIEW, UNANSWERED and UNSUPPORTED items block approval in the browser (PR-38); a sensitive-matter upload is declined and purged (PR-39); the seven rules show a verified source and date (PR-46, PR-47); `NOTICE` lists every dataset, model and font (PR-69); `tests/unit`, `tests/integration` and `tests/system` pass with the default markers (PR-72, PR-73) and the failures that remain are in the known-issues list; the first browser check list is written and each item is fixed or listed (PR-75); the README quick-start works on a clean clone (PR-81). Real models run on the lawyer-class machine only to the extent PR-23 reaches; the rest is labelled experimental. The remaining v1.0 items (PR-22, PR-29 distribution, PR-33, PR-62, the clean-machine QA run) are stretch.

**The evaluation core floor is done when:** the freeze tags exist; RQ1 main (Full, B0, B1, B4, plus B0L, B0S, B6) and the sparring 2x2 with the three new arms have saved outputs and manifests; the open 120 are scored; error analysis is written; the blind slice is opened once; the tables carry intervals and the claims that were not run are named as not run.

## D. Evaluation job map (the 24 must jobs)

Vishak operates every Ada job (EV-11). "Code" is who writes what the job needs. C is committed, S stretch.

| Job | What | EV tasks | Code owner | Tier |
|---|---|---|---|---|
| 1 | Teacher dossiers | EV-08 (pilot in EV-09) | Vishak | S |
| 2 | QLoRA (batch) | EV-08 | Vishak | S |
| 3 | Failure discovery, dev tuning | EV-11 part 1, EV-07, EV-02, EV-03 | Vishak, Harshita | C |
| 4 | RQ1 main | EV-05, EV-07, EV-02, EV-11 part 2 | Vishak, Harshita | C (floor sizes) |
| 5 | B0L, B0S, B6 | EV-05, EV-11 part 2 | Vishak | C |
| 6 | Ablations A1, A3, A4, A6, A7 | EV-06b | Vishak | S |
| 7 | Sparring 2x2 (A2, A8, A9) | EV-06a, EV-11 part 2 | Vishak | C |
| 8 | A5 extractors | EV-08 | Vishak | S |
| 9 | RQ2 vision pages and full system | EV-19, EV-18 | Vishak | S |
| 10 | F2 change sets | EV-20, EV-18 | Vishak | S |
| 11 | F1, F5, F6 baselines and assembly | EV-20 (needs PR-13, PR-14) | Vishak | S |
| 12 | F3 baselines | EV-20 | Vishak | S |
| 13 | F4 no-cache | EV-20 | Vishak | S |
| 14 | T6 tool calling, T7 safety | EV-04, EV-11 | Vishak | S rank 1 (never cut; fallback: the existing `tests/system` T7 scripts) |
| 15 | S8 self-critique repair | EV-12 | Satvik | C |
| 16 | S9 sampling-only critic | EV-13 | Vishak | C |
| 17 | S10 no isolation | EV-12 | Satvik | C |
| 18 | S1 self-critique retrieval | EV-15 | Vishak | S |
| 19 | S3 stopping variants | EV-15 | Vishak | S |
| 20 | S7 gap re-reading | EV-16 | Vishak | S |
| 21 | S15 output formats | EV-14 | Shravani | code C, run S |
| 22 | S17 defences | EV-17 | Shravani | S |
| 23 | Budget sweep (frontier) | EV-11 stretch, needs A7 from EV-06b | Vishak | S |
| 24 | Citation faithfulness by removal | EV-21 | Harshita | S |

Every must job has one owner for its code and Vishak as its operator; the committed ones are 3, 4, 5, 7, 15, 16, 17 (and the code of 21). Tier B and C jobs 25 to 33 are deferred (EV-22).

