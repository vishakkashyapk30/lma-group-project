# Product readiness: what is left to present Vakeel-Sahayak.ai as a finished product

Status date: 2026-10-24. Branch `ideation-v1`. This document is a planning note. It changes no code. Task IDs `PR-01` to `PR-86` are stable and are used by the team-plan document that follows.

<!-- SECTION:0 -->
## 0. Summary
**The short version.** The research core is built: six agents, ten stores, the privacy layer, the Rights Radar and a frontend that passes 233 unit and 69 browser tests on mock data. The product is not usable yet, for five reasons that are all measurable:

1. **The API is a stub.** `/api/*` answers 503, so the UI shows demo data of case-0007 (section 2.2).
2. **There is no case flow.** `orchestration/graph.py` and the fallback raise `NotImplementedError`; there is no end-to-end driver.
3. **There is no output.** The DOCX, List of Dates, hearing-prep card and PDF are stubs; 26 export tests fail, 9 error.
4. **Nothing real runs.** The default stack uses stand-in models. No weights are downloaded, `scripts/download_models.sh` prints "TODO", the 14B model does not fit an 8 GB laptop, and the real-model paths and the full stores have never run.
5. **Nobody has used it.** No person has opened the UI in a browser; all 7 Rights Radar rules still read `last_verified: null`.

**What this document gives the team.** Acceptance criteria tied to the seven user flows (section 1), a gap analysis in eleven areas (section 3), a four-week release plan with stop-ship checklists and a cut list (section 4), and a backlog of 86 tasks `PR-01` to `PR-86` (section 5).

**Numbers (estimates).** 86 tasks: 31 P0 (88.5 person-days), 46 P1 (93.5), 9 P2 (15.0); 27 S, 50 M, 9 L; 197 person-days in all. Critical path: PR-01 (graph), PR-06 (chat and draft routes), PR-72 (integration tests), PR-73 (system tests), 17.5 days of serial work; export joins it through PR-07 and PR-16.

**The hard finding.** The P0 list needs about 73.5 person-days charged to the product, and the team can spend about 40 to 52 on it while also building the evaluation. The plan therefore defines a **Preview release (v0.9)** of about 54 charged days, and treats the rest of P0 as v1.0 if capacity allows. Decision D1 in section 8 is the first one to take.

**Not in this document:** the evaluation, test-set and fine-tuning code (`docs/evaluation-plan.md` owns it; it defines no `EV-xx` IDs, so the boundary is its section 8.3 table).

<!-- /SECTION:0 -->

<!-- SECTION:1 -->
## 1. What "finished product" means (acceptance criteria)
**One-sentence definition.** On a legal-aid lawyer's own machine, one command starts the stack. The lawyer then uploads a messy bundle, reviews and approves the dossier, gets a brief whose citations they can check, spars with the prosecution agent, resolves every open item, approves, and downloads a court-ready DOCX, all in the browser and without touching a terminal after startup. Nothing leaves the machine unless the lawyer turned an external service on and consented.

**Scope of v1** (from plan section 1 and section 13): regular bail in an Indian High Court (CrPC s.439 / BNSS s.483), one generic High Court format, English and Hindi documents, six agents, the batch desk and the library. Users are the lawyer and the supervised student. Not users: accused persons, the public, judges.

### 1.1 Acceptance criteria, tied to the user flows of plan section 13.6

Each criterion is written so that a teammate who did not write the code can pass or fail it from the manual QA script (PR-77). "Live mode" means the real backend answered; demo data never counts.

| ID | Flow | The product passes when | Main tasks |
|---|---|---|---|
| AC-0 | Install and start | On a clean Windows (Docker Desktop), macOS or Linux machine with Docker, one command (`./install.sh`, or `docker compose up` after `install`) ends with a working URL on `127.0.0.1`. The script checks Docker, free disk, GPU and ports, fetches the models for the detected tier and the stores, and says in plain words what is missing. No terminal is needed afterwards. Restart keeps all cases. | PR-62, PR-21, PR-30, PR-20, PR-03, PR-81 |
| AC-1 | Flow 1: messy bundle | A lawyer drops one 14-page PDF (scanned Hindi FIR, two remand orders, a Sessions Court rejection). Within the time budget of PR-78 they see documents split and labelled with route badges, one question about an unreadable page, the dossier with a source link on every field, the List of Dates, and the Rights Radar chips. Red fields can be fixed. Gate 1 cannot be passed while a field is `UNSUPPORTED` and unacknowledged. An encrypted, corrupt or huge file gives a plain message, never a crash. | PR-05, PR-33, PR-34, PR-07, PR-38, PR-36 |
| AC-2 | Flow 2: quick question | In the chat, "Days in custody?" returns a one-line cited answer with store and tool chips. A request for an outcome prediction, a grant rate or lay advice is refused in fixed wording. An unanswerable question says what is missing. | PR-06, PR-40 |
| AC-3 | Flow 3: brief, spar, export | *Draft bail brief* shows the live plan and progress. Every ground carries `[F:]` facts and `[A:]` authorities rendered from corpus metadata, each clickable to its source paragraph. Abhiyojak's objections are listed and answered. `NEEDS_REVIEW` and `UNANSWERED` items must be resolved or acknowledged before Gate 2. Export before Gate 2 returns 403 and the button is disabled. After Gate 2 the lawyer downloads the application DOCX and the hearing-prep card. Both carry the "AI-generated draft. Not legal advice." banner. The DOCX opens in Word and LibreOffice with synopsis, List of Dates, grounds, prayer and annexure index. | PR-06, PR-07, PR-13, PR-14, PR-16, PR-38, PR-37 |
| AC-4 | Flow 4: the case moves on | Uploading a new order highlights the changed dossier fields, requires Gate 1 again, and redrafts only the affected grounds. The other grounds are unchanged word for word. A duplicate upload creates no duplicate. | PR-07, PR-10, PR-01 |
| AC-5 | Flow 5: dictated case | Hindi dictation (microphone or file) is transcribed, dates and sections are read back for confirmation, and the facts are marked `USER_STATED`. The brief says "per counsel, not on record". Audio is deleted after transcription unless the lawyer keeps it. | PR-05, PR-07, PR-34 |
| AC-6 | Flow 6: batch desk | A folder or zip of 120 files gives a triage board within minutes. Full briefs run in urgency order in the background and survive a restart. There is no bulk export; each case needs its own approval. | PR-08, PR-57, PR-11 |
| AC-7 | Flow 7: library | Search needs a `before` date that the server enforces. Hits show `sc_root` and good-law badges. The IPC to BNS bridge shows a text diff. The data-cut date is on screen. | PR-09, PR-50 |
| AC-S | Safety | Export is blocked before Gate 2 in code. Planted instructions in documents are never followed. Sexual-offence, POCSO and juvenile matters are declined at intake and their files are purged. No outcome prediction or grant rate appears anywhere. The `tests/system/test_t7_*` suites pass. | PR-16, PR-39, PR-40, PR-73 |
| AC-P | Privacy | With Sarvam off (the default), a network capture over a full run shows no outbound traffic. Logs hold only pseudonymised text. The lawyer can see where each model runs and can delete a case completely. A Sarvam mode above `public` needs a per-case consent event. | PR-67, PR-66, PR-42, PR-44 |
| AC-L | Legal content | Every Rights Radar rule shows its text, source, the dates used and a "last verified" date, and has been re-checked against the bare act. Unsettled law returns `CHECK`. The Gate 2 screen lists what counsel must verify. | PR-46, PR-47, PR-48, PR-49 |
| AC-Q | Quality | `tests/unit`, `tests/integration` and `tests/system` pass with the default markers. The Playwright suite passes against a production build. One person has used the UI in a browser against the live backend and every defect on their list is fixed or in the known-issues list. | PR-72, PR-73, PR-74, PR-75, PR-80 |
| AC-D | Documentation and licences | A README quick-start, a lawyer guide, an admin guide and an FAQ on limits exist. Every dataset, model and font is listed with its licence and attribution. | PR-81 to PR-86, PR-69 |

### 1.2 What v1 deliberately does not need

No accounts or login (local use; PR-71 is an optional lock). No court-specific formats beyond the generic one. No mobile app. No e-filing. No predictions, ever. No user study (there is no legal collaborator); the evaluation plan's level-4 proxies (`docs/evaluation-plan.md` section 4.9) stand in for it, and the product says so.
<!-- /SECTION:1 -->

<!-- SECTION:2 -->
## 2. Where the product stands today
Sources: `progress.md` (sections 0, 0b, 5, 5b, 5c), `DOCKER.md`, and a read-only grep for `raise NotImplementedError` per package on 2026-10-24. Many remaining hits in "finished" packages are abstract base methods or guards that catch the error, so the table separates real stubs from those.

### 2.1 Built and green (no work except real-model validation)

| Part | State |
|---|---|
| Foundations: config, schemas, event log, case record, evidence contracts, tool registry with gated export, privacy layer, Rights Radar (7 rules), concordance | Done, unit-tested (Phases 1 to 4 regression: 2,590 passed, 16 skipped, 0 failed, at the last recorded run) |
| Stores and data pipelines (ten stores, builders, good-law check, gold labels) | Done; only a 2,000-order sample build has run (36 MB in `data/stores_sample`); the full build is not run |
| Munshi ingestion (ladder, bundles, Hindi, voice) | Done and tested offline; real OCR, vision, translation and speech libraries are not installed; PyMuPDF missing (16 tests skip) |
| Six agents: Munshi, Peshkar, Sutradhar, Vakeel, Abhiyojak, Pairokar (plus truth maintenance and the batch desk) | Done, each run offline on case-0007 in a scratch script; no end-to-end driver exists |
| Sarvam integration (off by default, four modes) | Done against mocked HTTP only; no live call has been made |
| Frontend: landing, cause list, workspace (rail, three panes, gate modal, trace), desk, library, about | Done and automated-checked (Vitest 233/233, Playwright 69/69 on a production build); runs on demo data when the API answers 5xx; nobody has looked at it in a browser |
| Docker: `docker compose up` gives a healthy backend (381 MB) and frontend (245 MB), hardened (non-root, read-only root, caps dropped, ports on 127.0.0.1) | Done; cold build about 16 minutes, warm start about 12 seconds; `real`, `test` and e2e profiles not run |

### 2.2 Not built: what stands between us and a usable product

| Part | Evidence | Failing tests that wait on it (last recorded) |
|---|---|---|
| LangGraph flow and plain fallback | `orchestration/graph.py`: 13 `NotImplementedError` (nine nodes, the router, `build_graph`); `fallback_state_machine.py`: 2 | about 34 unit tests (`test_graph.py` about 30, `test_fallback_state_machine.py` about 4) |
| API routes | `api/app.py`, `deps.py`, `sse.py` and all eight routers are stubs: 34 `NotImplementedError` across 12 files (the one in `asgi.py` is only the catch for the deliberate 503 switch). `/api/*` answers 503. | `tests/unit/api`: 116 failing; `tests/integration/test_api_routes.py` |
| Export | `export/application.py`, `exporter.py`, `hearing_card.py`, `list_of_dates.py` and `pdf.py` are stubs (5 hits in 5 files). `sections.py` is real but only lists the eleven section names and their order. `tools/drafting/application.py` turns the stub into a `not_implemented` tool error. `export/templates/` holds only a README. | `tests/unit/export`: 26 failing, 9 errors |
| System tests | one file per flow and per T7 suite | `tests/system`: 257 failing before |
| Integration tests | eight files | `tests/integration`: 107 failing before |
| Real model weights | `scripts/download_models.sh` prints "TODO" and exits 1; no weights are downloaded anywhere | six real-model system variants are skipped |
| Full stores, missing statutes | no CrPC 1973, no NDPS s.37, no bailable/cognisable table | none (data, not code) |
| Model-labeler client, two evaluation helpers | `models/labeler.py` (wired by guard), `pipelines/order_splitter.py` rescue path | evaluation only |

### 2.3 Out of scope of this document

The evaluation, test-set and fine-tuning packages are the research deliverable, not the product: `eval/` has 56 stub files (91 hits), `testsets/` 13 (21), `finetune/` 6 (7); failing tests: `tests/unit/eval` 175, `tests/unit/finetune` 70. They are owned by `docs/evaluation-plan.md`. Where the product needs the same thing (a thin end-to-end driver, real-model validation, the full store build, latency numbers), this document says so and gives one task that both sides use. The evaluation plan defines no `EV-xx` task IDs; it uses claim IDs (C1 to C17), variant names (S1 to S17), jobs and a table of code to build (its section 8.3). The boundary is therefore: anything that appears in that section 8.3 table is evaluation work and is not repeated here. Product tasks that overlap are marked "shared with evaluation" in section 3.
<!-- /SECTION:2 -->

<!-- SECTION:3 -->
## 3. Gap analysis by area
Effort classes: S up to 1 person-day, M 2 to 3, L 4 to 6, XL more than 6. All effort numbers are estimates made from reading the stubs and the tests, not measured. Priority: P0 blocks any real use, P1 is needed for a credible product, P2 is polish. "Dep" lists other task IDs.

### 3.1 Core flow wiring

| Gap | Why a lawyer cares | Files | Dep | Effort | Pri | Task |
|---|---|---|---|---|---|---|
| The LangGraph flow does not exist (nine node functions, the gate router and `build_graph` raise). Nothing runs Munshi, then Peshkar, then the gate, as one case. | Without it the product is six agents with no case flow, no gates and no resume. | `orchestration/graph.py`, `state.py`, `gates.py` (done), `record/checkpoint.py` | none | L | P0 | PR-01 |
| The plain-Python fallback with the same gate rules | A machine without the right LangGraph version must still honour the gates. | `orchestration/fallback_state_machine.py` | PR-01 | S | P1 | PR-02 |
| `create_app()` and the dependencies (config, event log, gate guard) are stubs; `/api/*` answers 503 and the UI shows demo data | Today a lawyer sees a pretty demo of someone else's case. | `api/app.py`, `deps.py`, `asgi.py` | none | M | P0 | PR-03 |
| Session persistence and resume: cases must survive a container restart, and a half-finished run must resume from the checkpoint | A power cut or a closed laptop lid in the middle of a 20-minute draft cannot lose the work. | `record/*`, `orchestration/graph.py`, the `vs_data` volume | PR-01, PR-03 | (inside PR-01, PR-03) | P0 | PR-01, PR-03 |
| Read routes (cause list, ingestion report, dossier with field edit, timeline, rights, budget). The API must pin the shapes of the rights report and the hearing-prep card, which the frontend fixtures only tolerate loosely. `CaseSummary` needs `last_activity`. | The cause list must show the most recently touched case first and the urgent flags; the right pane must not break on a real response. | `api/routers/cases.py`, `api/models.py`, `schemas/rights_report.py`, `frontend/lib/types.ts`, `frontend/lib/mock/*` | PR-03 | M | P0 | PR-04 |
| Upload and dictation routes, a background job runner and the SSE event stream (events: stage, page n of N, tool call, gate reached, error) | Ingestion and drafting take minutes. The lawyer must see progress and be able to leave and come back. | `api/routers/upload.py`, `events.py`, `api/sse.py`, `frontend/lib/useEventStream.ts` | PR-03 (soft: PR-01) | L | P0 | PR-05 |
| Chat, draft, brief, spar and hearing-prep routes | Flows 2 and 3 are the daily work. | `api/routers/chat.py`, `cases.py` | PR-03, PR-01 | L | P0 | PR-06 |
| Gate routes: Gate 1 and Gate 2 approval, resolving checklist items, counsel's answers to Munshi's questions, dictation read-back confirmation, the ChangeSet route. The tests record that no route lets counsel resolve a Gate 2 item and that flow 4 reads the ChangeSet only from SSE. | The gates are the safety promise. They must work, not only render. | `api/routers/gates.py`, `orchestration/gates.py` | PR-03, PR-01 | M | P0 | PR-07 |
| Desk routes (zip or folder upload, triage board, overnight queue) | Flow 6 for an office. | `api/routers/desk.py`, `batch/*` | PR-05 | M | P1 | PR-08 |
| Library routes with the server-side `before` date. Today the filters run in the browser, search hits lack `sc_root` and `good_law`. | The `before` date is the leakage guard; the browser must not be trusted to apply it. A bad precedent without a good-law badge is a risk to the lawyer. | `api/routers/library.py`, `stores/*` | PR-03 | S | P1 | PR-09 |
| Reconcile leftovers: the wording of `request_approval(...).unresolved`, Munshi reading each page twice and starting with an empty shelf, duplicate documents on re-ingest, optional `SourceRef` fields | A lawyer who uploads the same file twice must not get two copies of every event. | `tools/drafting`, `agents/munshi/toolkit.py`, `ingestion/filing.py`, `schemas` | none | S | P1 | PR-10 |
| Concurrency and long jobs: one GPU means one heavy job at a time; cancel; two browser tabs on one case; idempotent re-ingest | A second tab or a click on "draft" twice must not start two 20-minute runs or corrupt the event log. | `api/deps.py`, `record/event_log.py`, `batch/queue.py` | PR-05 | M | P1 | PR-11 |
| Server-side before-date enforcement everywhere a shared store is searched through the API | Leakage control is in the stores already (every shared search needs `before`); the API must pass it, and the chat must set it to the case's own date. | `api/routers/*`, `stores/leakage_guard.py` | PR-09 | (inside PR-09, PR-06) | P1 | PR-09 |
| An end-to-end smoke driver (case-0007 through the real agents, scripted counsel, gates auto-approved only when the scenario says so) | It is the fastest way to tell whether any change broke the chain. Shared with the evaluation driver (`eval/runners/driver.py`, evaluation-plan 7.3 and 8.3). | `eval/runners/driver.py` (evaluation), `Makefile`, `scripts/` | none | S | P1 | PR-12 |
### 3.2 Output: the court-ready application and the hearing card

| Gap | Why a lawyer cares | Files | Dep | Effort | Pri | Task |
|---|---|---|---|---|---|---|
| The DOCX builder: cause title with placeholders, s.483 BNSS heading, synopsis, List of Dates and Events (every date from `case.timeline` with its source), brief facts, earlier bail applications, numbered grounds, statutory position, prayer, verification and affidavit placeholders, annexure index (one entry and page range per uploaded document), the banner, and a cover note of what counsel must verify. There is no template file yet. | This is the thing the lawyer files. Nothing else in the product matters if it does not open cleanly in Word. | `export/application.py`, `list_of_dates.py`, `sections.py`, `export/templates/`, `tools/drafting/application.py` | none | L | P0 | PR-13 |
| Hearing-prep card: likely concerns from comparable orders, three points to lead with, conditions courts impose (the tests note that nothing serves "conditions courts impose" yet), open issues; one page; no prediction | Prepares the lawyer for the bench. | `export/hearing_card.py`, `agents/vakeel/hearing.py`, `stores/caselaw_similar.py` | none | M | P0 | PR-14 |
| PDF export and print layout (one-page card, page numbers on the application, Devanagari fonts embedded) | Some courts and clerks want a PDF; print must not clip. | `export/pdf.py` | PR-13, PR-14 | M | P1 | PR-15 |
| Gated export route, file names and a stamp with the brief version | The 403-before-Gate-2 rule has to hold at the HTTP layer too. | `api/routers/export.py`, `export/exporter.py` | PR-03, PR-07, PR-13, PR-14 | S | P0 | PR-16 |
| Editing before export: today the brief is read-only in the UI. A lawyer will rewrite sentences. An edited sentence must be re-checked (support, good law) and must show who changed it. Version history and undo or redo. | Lawyers do not file machine text unedited. Without editing the product is a read-only viewer. | `agents/vakeel/*`, `truth_maintenance/*`, `api/routers/cases.py`, `frontend/components/workspace/tabs/*` | PR-06 | M + M | P1 | PR-17 (backend), PR-18 (editor) |
| Court-specific formats. v1 ships one generic High Court format. | Each High Court has its own rules. The banner says "check against your court's rules". | `export/templates/` | PR-13 | S (a note, no new format) | P2 | PR-19 |

What a court-specific format would need (documented in PR-19, not built): the court's cause-title block and party description conventions; its prescribed order of paragraphs and heading wording; page size, margins, font and line spacing rules; filing-index and affidavit formats; whether a synopsis and List of Dates are required for bail; language requirements; its e-filing portal's file-type and size limits; and a lawyer from that court to confirm all of it. We have no legal collaborator, so we cannot verify any of this.

### 3.3 Real models in the loop

The default stack runs `VS_MODELS=offline`: stand-in models that return canned or rule-based output. A lawyer using the default would get plausible-looking nonsense. The finished product must run real models on the lawyer's machine, and the plan puts the 14B agents on the Ada cluster (`configs/models.yaml`: `agents_14b ... where: ada`), which a lawyer does not have. Qwen3-14B-AWQ needs about 9 to 10 GB for weights alone (estimate), so it does not fit an 8 GB laptop GPU. The `real` profile is written for a 24 GB card and has only been checked with `docker compose config`.

| Tier | Hardware | Models (estimate of the fit) | Expected quality | Status |
|---|---|---|---|---|
| T0 offline | any | stand-ins | none; used for tests and the sample case only | works |
| T1 laptop | RTX 4060 8 GB | Qwen3-8B or 4B int4 for all agents; Qwen3-VL-4B 4-bit only when a page needs vision; BGE-M3, NLI and OCR loaded in turn, not together | the plan calls it "lower quality"; the size of the loss is not measured | not run |
| T2 GPU box | one 24 GB card | Qwen3-14B-AWQ through vLLM plus the same small models | the quality the evaluation reports for Full | profile unvalidated |
| T3 remote | Ada tunnel (demo) or Sarvam | 14B on a 2080 Ti session (6-hour limit), or Sarvam-105B on pseudonymised text | as T2 | tunnel works in principle; Sarvam untested live |
| CPU | no GPU | 4B int4 on CPU | very slow (estimate: hours per brief) | not built |

| Gap | Why a lawyer cares | Files | Dep | Effort | Pri | Task |
|---|---|---|---|---|---|---|
| Tier definitions, hardware auto-detect (`VS_MODELS=auto`), role mapping per tier, a visible statement of which tier is running | The lawyer must know whether the output came from a small or a large model. | `models/factory.py`, `configs/models.yaml`, `config.py` | none | M | P0 | PR-20 |
| Model download and first-run setup: `scripts/download_models.sh` is a stub. Needs resumable downloads, checksums, a disk-space check, licences shown, a volume that survives upgrades. The weights run to tens of GB across all roles. | A lawyer cannot run `huggingface-cli`. A silent 40 GB download that fills the disk is a product failure. Shared with evaluation (Ada also needs the weights). | `scripts/download_models.sh`, `docker/`, `compose.yaml` | PR-20 | M | P0 | PR-21 |
| Serving container: a laptop-sized container (quantised 8B or 4B) validated on the 4060; the 14B profile checked on a 24 GB card; start-up time stated (estimate: 1 to 3 minutes to load from disk on T1) | The `real` profile cannot be started on the lawyer's own machine today. | `compose.yaml`, `docker/backend.Dockerfile` | PR-20, PR-21 | L | P0 | PR-22 |
| Real-model paths on case-0007: OCR (Surya, Tesseract fallback), vision, BGE-M3, NLI, IndicTrans2, Whisper; install PyMuPDF; load and unload models so that they fit in 8 GB in turn. Shared with evaluation. | The real paths are written against the library APIs and never run. | `ingestion/routes/*`, `models/*`, `pyproject.toml` extras | PR-21 | L | P0 | PR-23 |
| No-GPU path: say what is lost. Intake and the dossier may run on CPU in minutes per page; the brief and the spar will take hours (estimate). Show an estimate before the run and a banner on the result. | A lawyer without a GPU is the common case. Better a slow honest run than a crash. | `models/factory.py`, `ui banner` | PR-20 | M | P1 | PR-24 |
| Progress and streaming UX: step and page progress, estimate, cancel, "safe to leave", completion notification. Latency is minutes, not seconds. Expected per-step times are unknown until measured (PR-27); a first guess for T1 is 5 to 15 minutes for a 14-page intake, 2 to 5 for the dossier, 20 to 45 for a full brief with the spar. These are guesses. | A spinner for 30 minutes looks like a hang. | `frontend/lib/useEventStream.ts`, `components/workspace/*` | PR-05 | M | P1 | PR-25 |
| Sarvam optional path: off by default; UI to turn on, the four modes explained, a per-case consent event, a banner "data leaves this machine" while on, a live smoke test with a key, and the dashboard retention checklist (retention cannot be enforced from code) | The privacy promise holds only if the lawyer cannot turn Sarvam on by accident. | `models/sarvam/*`, `frontend` (settings and consent screens), `configs/models.yaml` | PR-32 | S (live test) + M (UI, in PR-42) | P2 / P1 | PR-26, PR-42 |
| Latency and memory measurements per step and per tier; ETA table; performance budgets. Shared with evaluation (M45). | Every "time" in the UI and the docs needs a measured source. | `eval/` metrics, new `scripts/` | PR-23 | M | P1 | PR-27 |

### 3.4 Data in the product

What exists: a 36 MB sample store (`data/stores_sample`, from 2,000 orders) and an 887 MB interim folder; the full build (about 2 GB, about 85 minutes, about 200K reasoning paragraphs) has never run because the laptop lacks disk. Open India Law v2026.08.1 is CC BY 4.0. The statute table has 1,411 rows (IPC, BNSS, BNS, UAPA 43D, PMLA 45).

| Gap | Why a lawyer cares | Files | Dep | Effort | Pri | Task |
|---|---|---|---|---|---|---|
| Missing statutes: CrPC 1973, NDPS s.37, the CrPC and BNSS First Schedule (bailable, cognisable). Until then "bailable" and "cognisable" are unset. | Older cases are still under the CrPC, and NDPS twin conditions are among the hardest bail questions. A statutory position with "bailable: unknown" is not usable. Shared with evaluation (T1 inputs). | `data/interim/statutes.jsonl`, `pipelines/store_builders/statutes.py`, `configs/bail_sections.yaml` (5 rows marked TODO) | none | M | P0 | PR-28 |
| Full store build, plus Supreme Court metadata wired into the citation index (citation resolution is about 17% and none of SCC or AIR) | Citation links and good-law badges are only as good as the graph. Thin graph means many "unresolved" badges. Shared with evaluation. | `pipelines/store_builders/*`, `pipelines/citation_graph/*` | PR-28 | L | P0 | PR-29 |
| Shipping the index: how does a lawyer get about 2 GB? A release artefact (GitHub release or Hugging Face dataset) with a checksum and a manifest (data-cut date, row counts, licence), fetched by the installer into `vs_data`; a 36 MB starter index as fallback so the product opens even offline-at-first-run. Attribution for CC BY 4.0 must travel with it. | A lawyer on a slow link needs resume and a progress bar. | `scripts/build_stores.sh`, `compose.yaml` (`data` profile), `data/README.md` | PR-29 | M | P0 | PR-30 |
| Update path for new judgments: incremental shard, version bump, rollback | Law moves. A three-month-old index misses recent High Court orders. | `pipelines/*`, `stores/registry.py` | PR-29 | M | P2 | PR-31 |
| Data-cut and rule "last verified" dates shown in the UI | A lawyer must know that the index ends at a date and which courts have no BNS-era orders (Madhya Pradesh 0, Kerala 3). | `frontend` footer and library, `api` settings | PR-32, PR-46 | S | P1 | PR-50 |
| Coverage honesty: show "citation not in index" instead of a badge when a citation did not resolve; per-court coverage note | Absence of a badge must not read as "good law". | `tools/caselaw/citations.py`, `frontend/components/library/*` | PR-29 | (inside PR-50) | P1 | PR-50 |
| Licence of IPC2BNS-Verify is unclear (no LICENSE file despite an MIT badge). The concordance bridge depends on it. | We cannot redistribute the 544 edges until the authors say yes. | `data/raw/ipc2bns*`, `NOTICE` | none | (inside PR-69) | P0 | PR-69 |

### 3.5 Ingestion robustness on real files

| Gap | Why a lawyer cares | Files | Dep | Effort | Pri | Task |
|---|---|---|---|---|---|---|
| Real libraries not installed: PyMuPDF (16 tests skip), OCR, vision, translation, speech | Today the ladder is tested on generated PDFs only. | `pyproject.toml`, `ingestion/routes/*` | PR-23 | (inside PR-23) | P0 | PR-23 |
| Hostile or ordinary bad inputs: encrypted PDFs (ask for the password or say so), corrupt PDFs, 300-page PDFs, images, phone HEIC, DOCX, zip; page and size caps; timeouts | A legal-aid office receives exactly these. A crash with a stack trace loses trust. | `ingestion/ladder.py`, `routes/*`, `api/routers/upload.py` | PR-23 | M | P0 | PR-33 |
| Low confidence, Hindi and handwriting: confidence thresholds; "I cannot read this page reliably, please type the date" prompts; confidence shown next to fields | Handwritten Hindi FIR copies are common and the model will often be wrong; asking is the safe behaviour. | `ingestion/questions.py`, `agents/munshi/decisions.py`, `agents/peshkar/*` | PR-23 | M | P1 | PR-34 |
| A sweep of real-like files: bundles from public orders, phone photos, skewed scans, mixed languages; table of failures by input kind with a fix or a known issue. The T2 test set of the evaluation overlaps; this task consumes its renderers and does not build new ones. | We have not seen the system on a real scan. | `testsets/rendering.py`, `degrade.py` (evaluation) | PR-33 | M | P1 | PR-35 |
| Error messages a lawyer understands: a catalogue of error codes with "what happened, what to do", in English and later Hindi | "503" and "model_unavailable" mean nothing to a lawyer. | `frontend/lib/errors.ts`, `api/models.py` | PR-04 | M | P1 | PR-36 |

### 3.6 Trust and safety UX

Much of this exists as components (status chips, source chips, gate modal, trace) and is checked by automated tests on mock data. The gaps are the parts that need the real backend or that were never designed.

| Gap | Why a lawyer cares | Files | Dep | Effort | Pri | Task |
|---|---|---|---|---|---|---|
| "AI-generated draft. Not legal advice." label on every UI view of a brief and on every export; first-run terms and disclaimer accepted once | Professional-conduct risk if a draft is passed off as final. | `frontend/components`, `export/*` | none | S | P0 | PR-37 |
| `NEEDS_REVIEW`, `UNANSWERED`, `UNSUPPORTED` workflow with real resolution and acknowledgement, logged | This is what makes the gates mean something. | `frontend/components/workspace/GateModal.tsx`, `api/routers/gates.py` | PR-07 | M | P0 | PR-38 |
| Sensitive-matter decline: a message that says why (victim and child identity laws), points to NALSA 15100 and legal-aid resources, and removes the uploaded files | A lawyer who uploads a POCSO file must not end up with it stored. | `privacy/sensitive_matters.py`, `frontend` | PR-05 | S | P0 | PR-39 |
| Refusals and abstention in chat: predictions, grant rates, lay advice, bulk export, pressure ("just export it"); an unanswerable factor is stated as a gap, not filled. The literature review adds when to ask counsel (rank questions by the fields they unlock, at most three per round) and visible abstention. | A system that invents support for a missing factor is worse than none. | `agents/sutradhar/chat_router.py`, `agents/vakeel/*`, `ingestion/questions.py` | PR-06 | M | P0 | PR-40 |
| Pseudonymisation visible to the lawyer: the alias map, and a clear rule that real names go into the DOCX cause title only on the lawyer's machine and only after they confirm | The lawyer must know what the models saw. | `privacy/*`, `export/application.py` | PR-13 | M | P1 | PR-41 |
| Local-only indicator and the per-case Sarvam consent screen | "Where did my client's text go" must be answerable at a glance. | `frontend/components/common/TopNav.tsx`, `api` settings | PR-32 | M | P1 | PR-42 |
| Audit trail export: approvals, sources, model versions, times, hashes, as a readable PDF and JSON | A lawyer may need to show what they checked. | `record/event_log.py`, `export/*` | PR-03 | M | P1 | PR-43 |
| Case retention and deletion: delete one case or all, remove files, caches and audio; export and import a case bundle | Client confidentiality after the matter ends. | `record/*`, `api/routers/cases.py`, `vs_data` | PR-03 | M | P1 | PR-44 |
| Demo-mode guard: the frontend falls back to case-0007 on any 5xx or network error and keeps that mode for the session. In a product build that is dangerous: a crashed backend would show someone else's case as if it were the lawyer's. Make real builds strict, with a visible banner and a clear error. | A silent switch to fake data is the worst failure mode for a legal tool. | `frontend/lib/api.ts` (`NEXT_PUBLIC_DEMO_FALLBACK=strict` already exists), `compose.yaml` | none | S | P0 | PR-45 |
| Undo and redo of edits; source-linked everything on real data | Part of PR-17 and PR-18; source links must be checked in the browser run (PR-75). | `frontend` | PR-17 | (inside PR-17, PR-18, PR-75) | P1 | PR-18 |
| Disclaimers and terms text; a plain-English limits page in the app (also in the FAQ) | Sets expectations. | `frontend/app/about`, docs | none | (inside PR-37, PR-86) | P1 | PR-37 |

Predictions: the plan forbids outcome predictions and grant rates anywhere (plan 1.3, 16). The product must also not show them indirectly: the hearing card lists "factors courts discussed", never rates; the library shows reasoning, never counts of grants. PR-14 and PR-40 carry this as an acceptance item and the T7 suites test it.

### 3.7 Legal-content correctness

The Rights Radar (seven rules: default bail, undertrial limit, notice of appearance, grounds of arrest, production within 24 hours, Antil category, statutory bar) is what a lawyer is most likely to act on. In `configs/rights_rules.yaml` every rule has `last_verified: null`: the week-0 check against the bare acts was never done. The UI mock shows a verified date that the real config does not have.

| Gap | Why a lawyer cares | Files | Dep | Effort | Pri | Task |
|---|---|---|---|---|---|---|
| Re-check all seven rule texts against the bare acts (BNSS, CrPC, Constitution) and the cited judgments; set `last_verified`, source and version per rule; expose them through the API | A wrong day count or threshold in a flag sends a lawyer to the wrong conclusion about a client's liberty. | `configs/rights_rules.yaml`, `rights/rules/*`, `docs/plan.md` Appendix C | none | M | P0 | PR-46 |
| Cases cited from memory: *Kapil Wadhawan* and *M. Ravindran* (progress.md); also check *Mihir Rajesh Shah* and *Vihaan Kumar* (2025) and *In Re Inhuman Conditions in 1382 Prisons (2024)*, and every case name in fixtures, UI text and mock data | A misquoted citation in a tool for lawyers is embarrassing and harmful. | `configs/rights_rules.yaml`, `frontend/lib/mock/*`, `tests/fixtures` | none | S | P0 | PR-47 |
| Open legal-reading choices (below): decide each, write the UI wording, keep a decision log | The lawyer must know when the tool is picking one side of an unsettled question. | `rights/rules/*`, `configs/*`, `docs/` | PR-46 | S | P1 | PR-48 |
| "What counsel must verify" checklist at Gate 2 and in the DOCX cover note | Makes the lawyer's own verification duty explicit. | `frontend` Gate 2, `export/application.py` | PR-38 | S | P1 | PR-49 |
| "Last verified" and data-cut dates shown in the UI | Shows how old each rule and the index are. | `frontend`, `api` | PR-32, PR-46 | S | P1 | PR-50 |

**Open legal-reading choices** (from `progress.md` sections 0 and 5; each needs a recorded decision): (1) a bare "10 years" maximum counts as `CHECK`, like "may extend to ten years"; (2) missing communication of the grounds of arrest is always `FLAG`, with the retroactivity question only in the detail text; (3) IPC 420 to BNS 318(4) is treated as `SAME` and 436A to 479 as `REWORDED`; (4) the Antil category D list of economic-offence sections is an assumption; (5) the sexual-offence decline list is deliberately broad, so some legitimate matters will be declined; (6) an "overruled" treatment taken from cue words alone still raises the good-law flag, labelled "unconfirmed"; (7) five extra rows in `bail_sections.yaml` are marked TODO; (8) whether the limit of three questions to counsel is per round or per case; (9) the IPC2BNS-Verify file format is guessed; (10) Devanagari and Latin spellings of one name get two aliases.

What the lawyer must always verify, and the product must say so: every date against the original document; every authority against the reported judgment; the Rights Radar flags against the current law; the court's own filing format; that the facts are the client's facts. The system never replaces that check.

### 3.8 UX completeness

| Gap | Why a lawyer cares | Files | Dep | Effort | Pri | Task |
|---|---|---|---|---|---|---|
| First-run onboarding: terms, hardware and tier check, a short tour, the sample case | First impression and honest expectations. | `frontend/app`, `components/` | PR-32, PR-52 | M | P1 | PR-51 |
| Importable sample case (case-0007 with precomputed outputs, runs without a model) | Lets a lawyer try everything without risking client data. | `tests/fixtures/case-0007`, `api` | PR-03 | S | P1 | PR-52 |
| Settings page (tier, Sarvam mode, data folder, versions, disk use) and a health page | Where the lawyer sees and controls what the product does. | `frontend/app/settings` (new), `api` settings | PR-32 | M | P1 | PR-53 |
| Empty, error, offline and busy states on every page | Real data hits states the mock never shows. | `frontend/components/*` | PR-36 | M | P1 | PR-54 |
| Accessibility audit with axe on real data and a keyboard-only walk through all seven flows (the automated suite passes on mock data only) | WCAG 2.1 AA is a plan commitment; keyboard use matters in a courtroom corridor. | `frontend/` | PR-05 | M | P1 | PR-55 |
| Deadline notifications for default-bail clocks (60/90 days) and under-trial limits: a cause-list banner and a browser notification; local only, no email | The most valuable thing the tool can do is warn about a closing window. | `frontend/app/cases`, `api` rights | PR-04 | M | P1 | PR-56 |
| Batch desk workflow in the UI against the real routes | Flow 6 for an office. | `frontend/components/desk/*` | PR-08 | M | P1 | PR-57 |
| Hindi UI strings (the documents are already Hindi-capable) and Devanagari input checks | Many legal-aid lawyers work in Hindi. English UI is acceptable for v1; key screens in Hindi are polish. | `frontend/` i18n | none | M | P2 | PR-58 |
| Search inside a case (documents, dossier, chat history); library search polish | Finding "where did it say the arrest date" in 300 pages. | `frontend/` | PR-04 | M | P2 | PR-59 |
| Tablet and mobile layout (768 px) | The stack is local; a tablet over the office network is a plausible use. | `frontend/` | none | M | P2 | PR-60 |
| Help page and glossary (stages, chips, gates, status names) | The chips and Roman numerals need a key. | `frontend/app/help`, docs | none | S | P2 | PR-61 |

### 3.9 Packaging and operations

| Gap | Why a lawyer cares | Files | Dep | Effort | Pri | Task |
|---|---|---|---|---|---|---|
| One-command install: `docker compose up` works today only for the demo stack. A real install must check Docker, free disk, GPU and ports, create `.env`, fetch models and stores, and explain failures in plain words. | A lawyer will not edit YAML. | `scripts/`, `Makefile`, new `install.sh`, `install.ps1` | PR-21, PR-30 | M | P0 | PR-62 |
| Images: cold build is about 16 minutes. Publish images to GHCR (amd64 and arm64) and ship a release compose file that pulls pinned tags | A 16-minute build on a lawyer's laptop is not a product. | `compose.yaml`, `docker/*`, CI | none | M | P1 | PR-63 |
| Windows and macOS: Docker Desktop and WSL2 notes; GPU passthrough on WSL2; Apple Silicon has no NVIDIA GPU, so it is the CPU tier; one real test on one such machine | Many lawyers use Windows laptops. | `DOCKER.md`, docs | PR-62 | M | P1 | PR-64 |
| Backups and upgrades: backup and restore of the `vs_data` volume, versioned data schema, migration of event logs between releases | An upgrade must not orphan cases. | `record/*`, `scripts/` | PR-03 | M | P1 | PR-65 |
| Logs and diagnostics: structured logs with pseudonymised text only, rotation, a "download diagnostics" bundle for support | Support without seeing client text. | `api/`, `compose.yaml` | PR-32 | S | P1 | PR-66 |
| Resource limits and offline operation: the backend is limited to 2 GB and 2 CPUs, too small for real models; set limits per tier; verify with a network capture that nothing goes out with Sarvam off | The privacy promise needs a test, not a sentence. | `compose.yaml` | PR-22 | M | P1 | PR-67 |
| Versioning, changelog and release notes | The lawyer must know which build wrote a draft. | repo root | none | S | P1 | PR-68 |
| Licences and attributions: Open India Law (CC BY 4.0, attribution), IPC2BNS-Verify (unclear), model licences (Qwen, BGE-M3, DeBERTa, Surya, IndicTrans2, Whisper, Llama only for evaluation), HLDC non-commercial (not shipped), fonts (OFL), Sarvam terms. NOTICE file and an in-app Licences page. | Redistribution without a licence is a legal problem for a legal product. | `NOTICE` (new), `frontend/app/about`, `data/raw/MANIFEST.json` | none | M | P0 | PR-69 |
| Security review and a written threat model for local use: bind to 127.0.0.1 (done), non-root and read-only containers (done), upload hardening (zip bombs, path traversal, PDF parser bugs), host-header and DNS-rebinding check, SSE and CORS, secrets only from the environment | A local tool still opens a port that a web page in the same browser can try to reach. | `api/`, `compose.yaml`, `docs/` | PR-05 | M | P1 | PR-70 |
| Optional passphrase lock for a shared office machine (auth is otherwise not needed locally) | A shared laptop holds several clients' files. | `api/deps.py` | PR-03 | S | P2 | PR-71 |

### 3.10 Quality assurance

| Gap | Last recorded state | Dep | Effort | Pri | Task |
|---|---|---|---|---|---|
| Unit tests for orchestration (about 34), API (116 failing), export (26 failing, 9 errors) | Fail until the modules exist; each is part of the acceptance of PR-01 to PR-16 | PR-01 to PR-16 | (inside those) | P0 | PR-01 to PR-16 |
| Integration tests | 107 failing before | PR-01, PR-06, PR-07 | M | P0 | PR-72 |
| System tests (flows 1 to 7, T7 suites; the 120-file desk is marked slow; six real-model variants carry `models` or `gpu`) | 257 failing before | PR-72, PR-16, PR-40 | L | P0 | PR-73 |
| Playwright setup (wants chromium-1248, 1243 installed and symlinked; one landing scroll spec flakes under `next dev` with 8 workers; the e2e container's image pull was cancelled; the `real` profile never run) | open | none | S | P1 | PR-74 |
| A browser check of the frontend by a person on live data: visuals, landing scenes, workspace, mobile layout. All checks so far are automated. | nobody has done it | PR-05, PR-06 | M | P0 | PR-75 |
| Live Playwright against the real backend for flows 1 to 3 and 7 (the current specs mock the backend) | not written | PR-06, PR-16 | L | P1 | PR-76 |
| Manual QA script: step-by-step cases a teammate can run (outline below); run on a clean machine | not written | none (draft), run late | M | P0 | PR-77 |
| Performance budgets and measurements | not defined | PR-27 | S | P1 | PR-78 |
| Demo script, a 6-minute video plan, the demo environment (Ada tunnel runbook and a recorded fallback) | not written | PR-75 | M | P1 | PR-79 |
| Known-issues list | not written | PR-77 | S | P1 | PR-80 |

**Manual QA script outline (PR-77).** About 40 cases, each with steps, expected result and a pass or fail box:
1. Install on a clean machine, start, restart, stop, and `down -v` warning (AC-0).
2. Flow 1 with the 14-page bundle, a phone-photo FIR, an encrypted PDF, a 300-page PDF, a Word file, an unreadable page (AC-1).
3. Flow 2: ten questions including a prediction request, a lay-advice request and an unanswerable one (AC-2).
4. Flow 3: draft, open every source link, spar, leave one `NEEDS_REVIEW` open and try to approve, approve, export, open the DOCX in Word and LibreOffice, print the card (AC-3).
5. Flow 4 with a conflicting charge-sheet order and a duplicate upload (AC-4).
6. Flow 5 with a Hindi dictation, a wrong date in the read-back, and audio deletion (AC-5).
7. Flow 6 with 20 files and an interrupted run (AC-6); flow 7 with a search missing its `before` date (AC-7).
8. Safety: a POCSO upload, planted instructions in a scanned page, "export without approval", a request for the grant rate (AC-S).
9. Privacy: Sarvam off, network capture; turn Sarvam on and check the banner and consent; delete a case and list the volume (AC-P).
10. Failure modes: stop the backend mid-run (the UI must show an error, not demo data), fill the disk, kill the model container, upload while another run is busy.

### 3.11 Documentation

| Gap | Dep | Effort | Pri | Task |
|---|---|---|---|---|
| README quick-start (the current README describes the repository layout) | PR-62 | S | P0 | PR-81 |
| User guide for lawyers, flows 1 to 7 with screenshots | PR-75 | M | P1 | PR-82 |
| Admin guide: install, tiers, backups, upgrade, Sarvam, troubleshooting by error code | PR-62, PR-65 | M | P1 | PR-83 |
| Architecture guide (condensed `docs/architecture/skeleton.md`, one diagram) | none | S | P2 | PR-84 |
| "How it was evaluated" page, in the app's About and as a document, tied to `docs/evaluation-plan.md`: each headline number links to its table and says which claim it supports, which claims were not run, the blind-slice rule, and the proxies that replace a user study | evaluation results | S | P1 | PR-85 |
| FAQ on limits (what it will not do, what to verify, which courts, why Hindi handwriting is hard, what Sarvam sees) | none | S | P1 | PR-86 |

<!-- /SECTION:3 -->

<!-- SECTION:4 -->
## 4. Release plan and milestones
Dates: week 1 starts Monday 26 October 2026 (the same calendar as `docs/evaluation-plan.md` section 7.1); week 4 ends Sunday 22 November. All effort figures are estimates in person-days (S = 1, M = 2.5, L = 5 for sums).

### 4.1 The capacity problem, stated plainly

| Quantity | Estimate |
|---|---|
| Whole backlog (86 tasks) | about 197 person-days |
| P0 only (31 tasks) | about 88.5 person-days |
| P0 that is also needed by the evaluation (PR-21, PR-23, PR-28, PR-29) | about 15, so P0 charged to the product is about 73.5 |
| Team capacity: 4 people, 4 weeks | 80 person-days in total |
| Share left for the product after the evaluation plan's own code (about 75 stub files in `eval/`, `testsets/`, `finetune/`) and Ada runs | about 40 to 52 (50% to 65%) |

**Conclusion.** The full P0 list does not fit in the product's share of 3 to 4 weeks. Three honest options (decision D1 in section 8): add capacity (a fifth person for three weeks); move the product deadline by a week or more; or ship a defined **Preview** release and say so. The plan below follows the third option and keeps the first two open.

**Preview release (v0.9).** The smallest thing a supervised lawyer could really use: flows 1, 2, 3 and 5 on one hardware tier, live API, real models, gated export, court-ready DOCX and hearing card, safety gates, legal content verified, and the defects found in the browser check (PR-75) written down. It takes PR-01, 03, 04, 05, 06, 07, 13, 14, 16, 20, 21, 23, 28, 37, 38, 39, 40, 45, 46, 47, 69, 72, 75, 81, which is about 64 person-days, of which about 10 are shared with the evaluation (PR-21, PR-23, PR-28), so about 54 charged to the product (estimate). The README (PR-81) documents a three-step manual install instead of waiting for PR-62 (the one dependency the Preview waives); the index is the starter index, and the laptop tier is documented as experimental if PR-22 slips.

**v1.0** adds the rest of P0 (PR-22, PR-29, PR-30, PR-33, PR-62, PR-73, PR-77) and as much P1 as capacity allows.

### 4.2 Interaction with the evaluation freeze

`docs/evaluation-plan.md` section 7.3 freezes the code at the start of week 2 (tag after commit `prereg-v1`) and tunes nothing afterwards. The reported numbers describe the pipeline at that tag. Therefore: any product task that changes agent, retrieval, drafting or export behaviour must land before the freeze or be reported as a post-freeze change not covered by the numbers. Affected tasks: PR-13 and PR-14 (the DOCX and the card are measured in F5 and F6), PR-23, PR-33, PR-34 (ingestion paths), PR-40 (refusals). The evaluation uses its own thin driver (evaluation-plan decision D2), so API, frontend, packaging and documentation work is not frozen. Recommendation: land PR-13 and PR-14 in week 1 and keep PR-23, PR-33, PR-34 and PR-40 as small, separately tagged patches after the freeze.

### 4.3 Week by week

Suggested assignment of skills to four people: person 1 backend-agents (and ML-eval for PR-27 and PR-35); person 2 backend-api; person 3 frontend; person 4 devops, data and docs-qa. Person 4 carries the most (about 73 person-days across devops, data and docs-qa), so docs-qa tasks should be shared with whoever is idle.

| Week | Build | Product at the end of the week | Stop-ship checklist for the week |
|---|---|---|---|
| 1: 26 Oct to 1 Nov | PR-03, 04, 05, 01 (started), 13, 14, 20, 21 (started), 28, 37, 45, 47, 46 (started), 69 (started), 72 (draft), 77 (draft the script) | **The API is live.** `docker compose up` shows live mode on the offline stand-ins: case list, upload, SSE events, dossier, rights, Gate 1 over HTTP. DOCX and card exist as files from a scripted brief. The UI never shows demo data silently. | `/api/*` no longer returns 503. Demo fallback is opt-in. Export route refuses before Gate 2 (unit test). DOCX opens in Word and LibreOffice. Statutes loaded. PR-13 and PR-14 merged before the evaluation freeze. |
| 2: 2 to 8 Nov | PR-01 (finished), 06, 07, 16, 38, 39, 40, 23, 29 (on a big-disk machine), 46, 47, 69, 72 (started), 75 (first look), P1 as room allows: PR-02, 10, 36 | **Flows 1 to 5 run in a browser** with the offline stand-ins, and flow 3 on real models on T2 or T3 (Ada tunnel). Preview-alpha for the team, not for lawyers. | No path exports before Gate 2. NEEDS_REVIEW and UNSUPPORTED block approval in the UI. Sensitive-matter upload leaves no file. Integration tests mostly green. The first browser check is done and its list written. |
| 3: 9 to 15 Nov | PR-72 (finished), 73 (started), 75 (fixes), 22 (serving), 33, 34, 30, 62 (install), 48, 49, 50, 53, 32, 25, 18 and 17 if capacity | **Preview (v0.9).** Real models on the lawyer-class machine (T1, or T2 if T1 slips), a documented install, the starter or full index, clear error messages. | Manual QA draft run end to end by someone who did not write the code. Rights rules verified with dates. Network capture with Sarvam off is clean. Licences page complete. Known-issues list started. |
| 4: 16 to 22 Nov | PR-73 (finished), 77 (run on a clean machine), 79, 80, 81, 82, 83, 85, 86, 68, release tag; P1 polish by capacity: PR-42, 43, 44, 51, 52, 54, 55, 56, 65, 66, 67, 70 | **v1.0 or Preview plus known issues.** README, guides, FAQ, demo script and video, release notes. | All AC criteria that the release claims pass in the manual QA run; the ones that do not are listed in known issues and in the release notes. `tests/unit`, `integration`, `system` pass with default markers. Feature freeze on day 3 of the week: only bug fixes after that. |

### 4.4 What is cut first if time runs short

Order of cuts, with the estimated saving. The rule is the team rule: reduce depth, never drop the safety core.

1. All P2 (nine tasks, about 15 days): court formats, Hindi UI, search, tablet, help, store updates, lock, Sarvam live test, architecture guide.
2. P1 polish that has no safety content: PR-18 and PR-17 (editing; the lawyer edits in Word instead; about 5), PR-51, PR-52 (onboarding and sample; about 3.5), PR-15 (PDF; about 2.5), PR-76 (live Playwright; about 5), PR-70 and PR-64 (about 5).
3. Shrink P0 scope (about 11.5 saved in total): PR-22 to the `local` runtime, no vLLM on T1 (2.5); PR-33 to encrypted and corrupt files only (1.5); PR-40 to wiring only because the agents already refuse (1); PR-46 to the four highest-impact rules first (1); PR-69 to a NOTICE file only (1); PR-73 without slow and real-model variants (2); PR-77 to the 15 most important cases (1); PR-62 to a three-step documented install (1.5).
4. Ship the 36 MB starter index (PR-30 and PR-29 become known issues) and say so in the UI. This costs retrieval quality, so it is the last cut before dropping scope.
5. Drop flow 6 (the desk) from the claimed release: PR-08 and PR-57 (about 5) become "preview".

**Never cut:** (a) gates enforced in code, including the 403 before Gate 2 and the checklist that blocks approval (PR-01, PR-07, PR-16, PR-38); (b) the privacy boundary: pseudonymisation before anything leaves, Sarvam off by default, the leak check, the injection guard, the sensitive-matter decline with purge (PR-05, PR-39, PR-42 consent part, PR-67 egress test); (c) source links on every field and authority, and citations rendered from corpus metadata; (d) the "AI-generated draft. Not legal advice." label (PR-37); (e) no outcome predictions; (f) the demo-mode guard (PR-45); (g) the licences page and attributions (PR-69); (h) the verified Rights Radar rules with dates, or the rules switched off (PR-46, PR-47).

<!-- /SECTION:4 -->

<!-- SECTION:5 -->
## 5. Prioritised backlog
IDs are stable. "Owner" is a skill, not a person: backend-agents, backend-api, frontend, ML-eval, data, docs-qa, devops. Effort classes are estimates (S up to 1 day, M 2 to 3, L 4 to 6). "Dep" means the task cannot be finished before the listed ones; most tasks can start earlier against a stub. Tasks on or next to the critical path (section 6.2) are marked "(critical path)" in the title. Tasks that overlap the evaluation are marked "shared with evaluation" in section 3; the evaluation plan itself defines no `EV-xx` IDs, so everything in its section 8.3 stays there and is not duplicated.

| ID | Title | Area | Pri | Effort | Depends on | Owner | Acceptance (one line) |
|---|---|---|---|---|---|---|---|
| PR-01 | LangGraph flow: Munshi, Peshkar, Gate 1 interrupt, Sutradhar/Vakeel/Abhiyojak loop, Gate 2 interrupt, export, SQLite checkpointer keyed by case id, change-set path (critical path) | Core flow | P0 | L | none | backend-agents | graph.py implements all nodes; `tests/unit/orchestration/test_graph.py` passes; export blocked before Gate 2; a killed process resumes from the checkpoint |
| PR-02 | Plain-Python fallback state machine with the same gate rules (`VS_ORCHESTRATOR=plain`) | Core flow | P1 | S | PR-01 | backend-agents | `test_fallback_state_machine.py` passes; same gate outcomes as the graph on the case-0007 script |
| PR-03 | App wiring: `create_app()`, config / event-log / gate-guard dependencies, case service layer, per-case locks, session resume after restart (critical path) | Core flow | P0 | M | none | backend-api | `/api/*` no longer returns 503; `tests/unit/api/test_app*` pass; a case survives `docker compose restart` |
| PR-04 | Read routes: cases, ingestion report, dossier and field edit, timeline, rights report, budget; pinned shapes for rights report and hearing card; `last_activity` on CaseSummary | Core flow | P0 | M | PR-03 | backend-api | routes return the typed models; frontend fixtures validate against the pinned JSON schema; cause list sorts by last_activity |
| PR-05 | Upload and dictation routes, background job runner, SSE event stream with progress events (step, page n of N) (critical path) | Core flow | P0 | L | PR-03 | backend-api | a 14-page bundle uploads, runs in the background and streams events; guard rejects planted instructions; sensitive matters are declined and purged |
| PR-06 | Chat (Sutradhar router), draft start, brief, spar and hearing-prep routes (critical path) | Core flow | P0 | L | PR-03, PR-01 | backend-api | flows 2 and 3 run through HTTP; every answer carries store and tool chips; budget stop visible |
| PR-07 | Gate 1 and Gate 2 routes: checklist resolve, counsel answers to Munshi questions, dictation read-back confirm, ChangeSet route (critical path) | Core flow | P0 | M | PR-03, PR-01 | backend-api | approval refused while UNSUPPORTED / NEEDS_REVIEW / UNANSWERED items are open; flows 4 and 5 run through HTTP |
| PR-08 | Batch desk routes: zip or folder upload, triage board, overnight queue, resume after interruption | Core flow | P1 | M | PR-05 | backend-api | 120-file desk (slow test) finishes a triage board; no bulk export route exists |
| PR-09 | Library routes: server-enforced `before` date, `sc_root`, `good_law`, IPC to BNS bridge | Core flow | P1 | S | PR-03 | backend-api | a search without `before` is rejected with 422; hits carry sc_root and good_law; `tests/unit/api` library tests pass |
| PR-10 | Settle reconcile items: `request_approval(...).unresolved` wording, Munshi double page read and empty shelf, duplicate documents on re-ingest, optional SourceRef fields | Core flow | P1 | S | none | backend-agents | the listed tests agree with the code; re-ingesting a file creates no duplicate document or event |
| PR-11 | Long-job control: single-GPU job queue, cancel, resume, idempotent re-ingest, two browser tabs on one case | Core flow | P1 | M | PR-05 | backend-api | cancel stops a run within one step; two tabs do not corrupt the event log |
| PR-12 | Smoke driver CLI: case-0007 end to end, offline and real (shares the evaluation driver, evaluation-plan 8.3) | Core flow | P1 | S | none | backend-agents | `make smoke` exits 0 and prints the export path |
| PR-13 | Court-ready DOCX: cause title placeholders, synopsis, brief facts, earlier applications, List of Dates, grounds, statutory position, prayer, verification placeholders, annexure index, banner, cover note of what counsel must verify | Output | P0 | L | none | backend-agents | `tests/unit/export` DOCX tests pass; opens in Word and LibreOffice; every date traces to a timeline event |
| PR-14 | Hearing-prep card builder and one-page layout, conditions from operative orders, no outcome prediction | Output | P0 | M | none | backend-agents | card has four parts of plan 8.3 on one page; no grant rate anywhere |
| PR-15 | PDF export and print layout for the application and the card | Output | P1 | M | PR-13, PR-14 | backend-agents | PDF renders Devanagari correctly; page count matches DOCX within one page |
| PR-16 | Export route: gated download, 403 before Gate 2, file names, stamp with brief version (critical path) | Output | P0 | S | PR-03, PR-13, PR-14, PR-07 | backend-api | 403 before Gate 2 in a test; the DOCX downloads from the browser |
| PR-17 | Editable brief: edit events, re-check on edit, version history, undo and redo | Output | P1 | M | PR-06 | backend-api | an edited ground is re-checked; the previous version can be restored |
| PR-18 | Editor UI: inline edit, diff against previous version, undo and redo, version list | Output | P1 | M | PR-17 | frontend | edit, undo, redo and restore work by keyboard |
| PR-19 | Court-format extension point and a note on what each High Court format would need (documentation plus template folder only) | Output | P2 | S | PR-13 | backend-agents | templates folder with a README; generic format unchanged |
| PR-20 | Model tiers: T0 offline stand-in, T1 laptop 8 GB, T2 24 GB GPU, T3 remote tunnel or Sarvam; auto-detect; role mapping per tier | Models | P0 | M | none | backend-agents | `VS_MODELS=auto` picks a tier and says so; each tier lists its roles in `configs/models.yaml` |
| PR-21 | Real model download and first-run installer replacing the stub `scripts/download_models.sh`: resumable, checksums, disk check, licences shown | Models | P0 | M | PR-20 | devops | one command fetches the tier's weights into a volume; a second run is a no-op |
| PR-22 | Serving container for the `real` profile fitted to 8 GB (quantised 8B or 4B), validated on the 4060, 14B profile checked on 24 GB | Models | P0 | L | PR-20, PR-21 | devops | `docker compose --profile real up` answers a chat on the 4060 without out-of-memory |
| PR-23 | Validate real-model paths on case-0007: OCR, vision, BGE-M3, NLI, IndicTrans2, Whisper; install PyMuPDF; load and unload so models fit in 8 GB in turn | Models | P0 | L | PR-21 | backend-agents | case-0007 runs end to end with `VS_MODELS=real`; 16 skipped ingestion tests run |
| PR-24 | No-GPU CPU path with a visible quality and speed banner | Models | P1 | M | PR-20 | backend-agents | a CPU-only run completes the intake and dossier stages and shows its estimate |
| PR-25 | Progress UX while an agent runs: step and page progress, time estimate, cancel, safe to leave the page, completion notification | Models | P1 | M | PR-05 | frontend | a 10-minute run shows live progress; closing the tab and reopening resumes the view |
| PR-26 | Sarvam live smoke test with a real key, json_schema check, retention checklist | Models | P2 | S | none | backend-agents | one real call per capability succeeds or the fallback is documented |
| PR-27 | Latency and memory measurements per step and per tier; ETA table | Models | P1 | M | PR-23 | ML-eval | table of seconds per page and per stage for T0, T1, T2, CPU |
| PR-28 | Fill statute gaps from India Code: CrPC 1973, NDPS s.37, CrPC/BNSS First Schedule (bailable, cognisable); rebuild statute and concordance stores | Data | P0 | M | none | data | `get_statute("CrPC 439")` and `bailable` resolve; statute tests updated |
| PR-29 | Full store build on a big-disk machine; wire Supreme Court metadata into the citation index; build report; manifest with data-cut date | Data | P0 | L | PR-28 | data | manifest lists row counts, sizes, data-cut date; citation resolution re-measured |
| PR-30 | Store distribution: release artefact, checksum, `make stores` or a compose init job, sample-store fallback, disk check | Data | P0 | M | PR-29 | devops | a clean machine reaches a working library search with one command |
| PR-31 | Store update path: add new judgments incrementally, version bump, rollback | Data | P2 | M | PR-29 | data | a new shard is added without a full rebuild; old version restorable |
| PR-32 | Settings, health and version API: tier, Sarvam mode, data folder, store manifest, rule dates, diagnostics | Data | P1 | S | PR-03 | backend-api | `/api/settings` and `/api/health` return typed data; Sarvam mode change needs confirmation |
| PR-33 | Ingestion hardening: encrypted, corrupt and huge PDFs, images, DOCX, zip, page caps, timeouts | Ingestion | P0 | M | PR-23 | backend-agents | each bad input gives a typed error, never a crash; a 300-page PDF finishes or stops with a message |
| PR-34 | Low-confidence, Hindi and handwriting handling: thresholds, "cannot read this, please type it" prompts, confidence data for the UI | Ingestion | P1 | M | PR-23 | backend-agents | an unreadable page always produces a question to counsel, never a silent guess |
| PR-35 | Real-file sweep: public-order-derived bundles including phone photos; triage failures (boundary with T2 of the evaluation plan) | Ingestion | P1 | M | PR-33 | ML-eval | a failure table by input kind with a fix or a known-issue entry for each |
| PR-36 | Error-code catalogue and plain-language messages across API and UI | Ingestion | P1 | M | PR-04 | frontend | every ApiError code has a message that says what happened and what to do |
| PR-37 | "AI-generated draft. Not legal advice." label in UI, DOCX, PDF and card; first-run terms acceptance | Trust | P0 | S | none | frontend | the label is present on every export; terms must be accepted once |
| PR-38 | NEEDS_REVIEW, UNANSWERED and UNSUPPORTED workflow in the UI with the gate checklist and acknowledgements | Trust | P0 | M | PR-07 | frontend | Gate modal cannot be passed with an open item; each resolution is logged |
| PR-39 | Sensitive-matter decline UX: message, resources (NALSA 15100), purge of the uploaded files | Trust | P0 | S | PR-05 | frontend | a POCSO or sexual-offence upload shows the decline and leaves no files on disk |
| PR-40 | Refusal and abstention wording through chat: predictions, lay advice, bulk export, pressure; T7 suites | Trust | P0 | M | PR-06 | backend-agents | `tests/system/test_t7_*` pass; an unanswerable factor is stated as a gap |
| PR-41 | Pseudonymisation visible to counsel: alias map view; real names filled into the DOCX cause title only locally | Trust | P1 | M | PR-13 | backend-agents | the alias map is shown; exported cause title carries real names only when counsel confirms |
| PR-42 | Privacy indicator in the nav (where each model runs, Sarvam state) and the per-case Sarvam consent screen | Trust | P1 | M | PR-32 | frontend | consent is a logged event; with Sarvam off the indicator says "this machine only" |
| PR-43 | Audit trail export (readable PDF and JSON): approvals, sources, model versions | Trust | P1 | M | PR-03 | backend-api | the export lists every gate decision with time, user text and hashes |
| PR-44 | Case deletion, retention setting, case bundle export and import | Trust | P1 | M | PR-03 | backend-api | deleting a case removes its event log, files, caches and audio; confirmed by a test that lists the volume |
| PR-45 | Demo-mode guard: a product build never falls back silently to demo data; visible banner; strict mode by default | Trust | P0 | S | none | frontend | with the backend down the UI shows an error, not case-0007; demo is opt-in |
| PR-46 | Re-verify the seven Rights Radar rules against the bare acts; store source, date and version per rule | Legal | P0 | M | none | docs-qa | each rule has a verified source link and date in `configs/rights_rules.yaml` |
| PR-47 | Verify the cases cited from memory (Kapil Wadhawan, M. Ravindran) and every case reference in configs, UI text and fixtures | Legal | P0 | S | none | docs-qa | each reference has a checked citation or is removed |
| PR-48 | Decide the open legal readings and write the UI wording; decision log | Legal | P1 | S | PR-46 | docs-qa | five open readings each have a recorded decision |
| PR-49 | "What counsel must verify" checklist at Gate 2 | Legal | P1 | S | PR-38 | frontend | checklist appears at Gate 2 and cannot be hidden |
| PR-50 | Sources and dates panel: rule last-verified dates and store data-cut dates in the UI | Legal | P1 | S | PR-32, PR-46 | frontend | every Rights chip shows its verified date; library shows the data-cut date |
| PR-51 | First-run onboarding: hardware check, terms, short tour, sample case | UX | P1 | M | PR-32, PR-52 | frontend | a new user reaches the sample case in under 2 minutes |
| PR-52 | Importable sample case (case-0007 with precomputed outputs) | UX | P1 | S | PR-03 | backend-api | "Try the sample case" creates a case that runs without any model |
| PR-53 | Settings page and health or diagnostics page | UX | P1 | M | PR-32 | frontend | tier, Sarvam mode, data folder, versions and disk use are visible; changing Sarvam mode asks for confirmation |
| PR-54 | Empty, error, offline and busy states across all pages | UX | P1 | M | PR-36 | frontend | each page has a designed empty state and a failure state |
| PR-55 | Accessibility audit with axe on real data, keyboard-only walk through flows 1 to 7, fixes | UX | P1 | M | PR-05 | frontend | zero serious axe violations on the workspace with live data |
| PR-56 | Deadline notifications for default-bail clocks: cause-list banner, browser notification, desk | UX | P1 | M | PR-04 | frontend | a case 3 days from a 60/90-day mark shows a banner on the cause list |
| PR-57 | Batch desk workflow in the UI against the real routes | UX | P1 | M | PR-08 | frontend | flow 6 works in the browser; each case still needs its own approval |
| PR-58 | Hindi UI strings for key screens and Devanagari input checks | UX | P2 | M | none | frontend | navigation, gates and errors have Hindi strings; typing Devanagari in chat works |
| PR-59 | In-case search (documents, dossier, chat history) and library search polish | UX | P2 | M | PR-04 | frontend | a search finds text in any page of any uploaded document |
| PR-60 | Tablet and mobile layout pass | UX | P2 | M | none | frontend | workspace usable at 768 px width |
| PR-61 | Help page and glossary | UX | P2 | S | none | docs-qa | every stage has a help link |
| PR-62 | One-command install: preflight script (Docker, disk, GPU, ports), `.env` generation, `install.sh` and `install.ps1` | Packaging | P0 | M | PR-21, PR-30 | devops | on a clean machine `./install.sh` ends with a working URL and a message on what is missing |
| PR-63 | Publish images to GHCR for amd64 and arm64, a release compose file that pulls pinned tags | Packaging | P1 | M | none | devops | `docker compose pull && up` needs no local build; first start under 10 minutes on a fast link |
| PR-64 | Windows (Docker Desktop and WSL2) and macOS notes and one real test; CPU-only tier on Apple Silicon | Packaging | P1 | M | PR-62 | devops | one Windows or macOS machine runs the sample case |
| PR-65 | Backup and restore of `vs_data`, upgrade path and data-schema migration | Packaging | P1 | M | PR-03 | devops | restore on a clean volume reproduces cases; v1 to v1.1 upgrade keeps cases |
| PR-66 | Logs (pseudonymised text only), rotation, diagnostics bundle | Packaging | P1 | S | PR-32 | devops | a log grep for a planted client name returns nothing |
| PR-67 | Resource limits per tier (the 2 GB backend limit is too small for real models), offline egress test | Packaging | P1 | M | PR-22 | devops | with Sarvam off, a packet capture over a full run shows no outbound traffic |
| PR-68 | Versioning, CHANGELOG and release checklist | Packaging | P1 | S | none | docs-qa | tag v1.0.0 has notes and a signed-off checklist |
| PR-69 | Licences and attributions: NOTICE, Licences page, IPC2BNS-Verify decision, model licences, fonts | Packaging | P0 | M | none | docs-qa | every shipped dataset, model and font is listed with licence and attribution; IPC2BNS-Verify either licensed or excluded |
| PR-70 | Security review and threat-model document for local use; upload hardening tests (zip bombs, path traversal), host-header and DNS-rebinding check | Packaging | P1 | M | PR-05 | devops | threat model published; tests for the listed attacks pass |
| PR-71 | Optional passphrase lock for shared machines | Packaging | P2 | S | PR-03 | backend-api | with a passphrase set, the API refuses calls without the session token |
| PR-72 | Integration tests green (107 failing before) (critical path) | QA | P0 | M | PR-01, PR-05, PR-06, PR-07 | docs-qa | `tests/integration` passes |
| PR-73 | System tests green (257 failing before), including T7 safety (critical path) | QA | P0 | L | PR-72, PR-16, PR-40 | docs-qa | `tests/system` passes (slow tests included) |
| PR-74 | Playwright fixes: pin 1.59 or `npx playwright install`, e2e on `next start`, run the e2e container | QA | P1 | S | none | frontend | 69 e2e tests pass in the container with no flake in three runs |
| PR-75 | A person uses the frontend in a browser with the real backend; written fix list | QA | P0 | M | PR-05, PR-06 | frontend | a list of visual and flow defects, each fixed or in known issues |
| PR-76 | Live (unmocked) Playwright for flows 1 to 3 and 7 | QA | P1 | L | PR-06, PR-16 | docs-qa | four specs pass against the real backend in offline-model mode |
| PR-77 | Manual QA script (step by step) and a run of it on a clean machine | QA | P0 | M | none | docs-qa | a teammate who did not write the code completes every case and records pass or fail |
| PR-78 | Performance budgets and measurement (Lighthouse, API p95, per-step times) | QA | P1 | S | PR-27 | docs-qa | budgets written; measured values beside them |
| PR-79 | Demo script, video plan and demo-environment runbook (tunnel and recorded fallback) | QA | P1 | M | PR-75 | docs-qa | a 6-minute script that runs on the laptop; a recorded backup video |
| PR-80 | Known-issues list and stated limits | QA | P1 | S | PR-77 | docs-qa | every failed manual case has an entry |
| PR-81 | README quick-start | Docs | P0 | S | PR-62 | docs-qa | a new reader starts the stack from the README alone |
| PR-82 | Lawyer user guide | Docs | P1 | M | PR-75 | docs-qa | covers flows 1 to 7 with screenshots |
| PR-83 | Admin guide: install, tiers, backup, upgrade, Sarvam, troubleshooting | Docs | P1 | M | PR-62, PR-65 | docs-qa | each troubleshooting entry matches an error code |
| PR-84 | Architecture guide (condensed from the skeleton map, one diagram) | Docs | P2 | S | none | docs-qa | two pages, links to the plan sections |
| PR-85 | "How it was evaluated" page (in-app About and a document) tied to the evaluation results | Docs | P1 | S | none | docs-qa | each headline number links to its table in the evaluation report; unrun claims are stated as not run |
| PR-86 | FAQ on limits | Docs | P1 | S | none | docs-qa | answers the ten questions a lawyer asks first |

<!-- /SECTION:5 -->

<!-- SECTION:6 -->
## 6. Effort totals and the critical path
All figures are estimates. Sums use S = 1, M = 2.5, L = 5 person-days. They were produced by a script over the table in section 5, so they match it.

### 6.1 Totals

**By priority and effort (task counts):**

| Priority | S | M | L | XL | Tasks | Person-days |
|---|---|---|---|---|---|---|
| P0 | 6 | 17 | 8 | 0 | 31 | 88.5 |
| P1 | 16 | 29 | 1 | 0 | 46 | 93.5 |
| P2 | 5 | 4 | 0 | 0 | 9 | 15.0 |
| **All** | **27** | **50** | **9** | **0** | **86** | **197.0** |

**By owner skill (all tasks, and the P0 part):**

| Owner skill | Tasks | Person-days, all | Person-days, P0 | P1 | P2 |
|---|---|---|---|---|---|
| backend-agents | 16 | 40.0 | 25.0 | 13.0 | 2.0 |
| backend-api | 15 | 35.0 | 18.5 | 15.5 | 1.0 |
| frontend | 21 | 43.5 | 8.0 | 28.0 | 7.5 |
| devops | 10 | 26.0 | 12.5 | 13.5 | 0 |
| docs-qa | 19 | 37.5 | 17.0 | 18.5 | 2.0 |
| data | 3 | 10.0 | 7.5 | 0 | 2.5 |
| ML-eval | 2 | 5.0 | 0 | 5.0 | 0 |
| **Total** | **86** | **197.0** | **88.5** | **93.5** | **15.0** |

**By area:** Core flow 12 tasks, 31.5 days; Output 7, 17.0; Models 8, 23.5; Data 5, 13.5; Ingestion 4, 10.0; Trust 9, 18.0; Legal 5, 6.5; UX 11, 24.5; Packaging 10, 20.5; QA 9, 23.0; Docs 6, 9.0.

**Balance for four people.** Frontend has little P0 (8 days) and a lot of P1 (28): the frontend person should start on the demo guard, labels, the review workflow and the browser check, then take backend-adjacent work (error catalogue, progress UI) so as not to idle while the routes are written. Devops, data and docs-qa together come to 73.5 days, more than any single person can carry, so docs-qa tasks (manual QA, guides, licences, legal checks) must be shared. The product's share of capacity is about 40 to 52 person-days against P0 of about 73.5 charged to the product (section 4.1).

### 6.2 Critical path

The longest dependency chain, which no amount of parallel work shortens:

**PR-01 (LangGraph flow, L) then PR-06 (chat, draft, brief, spar, hearing-prep routes, L) then PR-72 (integration tests, M) then PR-73 (system tests, L): 17.5 person-days of serial work.** It is the whole chain "graph, then API, then export, then system tests". The export part joins it through PR-07 (gate routes, M, after PR-01) and PR-16 (export route, S, also needs PR-13 and PR-14): PR-01 then PR-07 then PR-16 then PR-73 is 13.5 days, so it is near-critical rather than critical. PR-03 (app wiring, M) then PR-05 (upload and SSE, L) then PR-72 is 15 days and is also near-critical. PR-13 (DOCX, L) and PR-14 (card, M) are off the longest chain but must be done before PR-16 can finish, and before the evaluation freeze (section 4.2).

Because 17.5 days of serial work in a 15 to 19 working-day window leaves no slack, three rules apply. First, freeze the node and event interface of the graph (`orchestration/state.py`) on day 2 so PR-03, PR-05, PR-06 and PR-07 start against it before PR-01 ends. Second, PR-72 and PR-73 are not done at the end: fix the unit, integration and system tests of each route as that route lands (the tests are written). Third, PR-77 (the manual QA run on a clean machine) and PR-80 (known issues) come last, after PR-73, and together take 3.5 days; they are the final gate for a release.

**Second chain (runs on real files, on the lawyer's hardware):** PR-20 (tiers) then PR-21 (model download) then PR-23 (real-model paths) then PR-33 (ingestion hardening) then PR-35 (file sweep): 15 days. PR-22 (serving container) branches after PR-21: PR-20, PR-21, PR-22, PR-67 (limits and egress test) is 12.5 days.

**Third chain (a clean install):** PR-28 (statutes) then PR-29 (full stores) then PR-30 (store distribution) then PR-62 (install) then PR-81 (README): 13.5 days. PR-28 and PR-29 can run on a machine with disk space while the others code, because they are data jobs.

**Suggested start order on day 1:** PR-01, PR-03, PR-13, PR-20, PR-28, PR-37, PR-45, PR-46 (eight tasks with no dependency, spread over four people).

### 6.3 Tasks with no dependencies (can start at once)

PR-01, 03, 10, 12, 13, 14, 20, 26, 28, 37, 45, 46, 47, 58, 60, 61, 63, 68, 69, 74, 77 (draft), 84, 85, 86 (24 tasks). This is what makes four parallel streams possible in the first week.

<!-- /SECTION:6 -->

<!-- SECTION:7 -->
## 7. Risks to a usable product, and what we will not claim
### 7.1 Risks

| # | Risk | Likelihood and impact (judgement) | Mitigation | Tasks |
|---|---|---|---|---|
| R1 | Capacity: the P0 list needs about 73.5 product-charged person-days against a share of 40 to 52 | High, high | Preview release definition (section 4.1), cut list (4.4), decision D1; run data jobs on a big-disk machine in parallel | all |
| R2 | The default stack runs stand-in models; real quality on an 8 GB laptop is unmeasured and the small model may draft badly | High, high | Tiers with a visible tier label; more `NEEDS_REVIEW` rather than confident text; measure per tier; allow T2 or T3 for the demo; say the loss in the UI and the guide | PR-20, 22, 23, 24, 27 |
| R3 | A run takes 20 to 45 minutes on T1 (a guess) and looks like a hang | Medium, high | Progress events, estimates, cancel, resume from checkpoint | PR-05, 25, 11 |
| R4 | The demo-mode fallback shows case-0007 as if it were the lawyer's case when the backend fails | Medium, very high | Strict mode and banner in product builds | PR-45 |
| R5 | A rule text in the Rights Radar is wrong or out of date and no legal collaborator can check it | Medium, very high | Re-check against bare acts, show source and date, return `CHECK` for unsettled law, state in the guide that counsel verifies; if a rule cannot be verified it is switched off | PR-46, 47, 48, 49 |
| R6 | Few citations resolve (about 17%; none of SCC or AIR), so good-law badges are sparse | High, medium | Show "not in index" instead of a badge; per-court coverage note; wire the Supreme Court metadata | PR-29, 50 |
| R7 | Real scans, Hindi handwriting and phone photos break the ladder (never tried on real files) | High, high | Ingestion hardening, low-confidence prompts, a file sweep, ask counsel instead of guessing | PR-23, 33, 34, 35 |
| R8 | Privacy regression: a log line or a Sarvam call carries client text | Low, very high | Pseudonymisation before any call, leak check, a logs test with a planted name, an egress capture, consent as an event | PR-42, 66, 67, 40 |
| R9 | Product patches after the evaluation freeze change the pipeline whose numbers are reported | Medium, high | Land PR-13 and PR-14 before the freeze; tag later agent changes as post-freeze and re-run a smoke subset | section 4.2 |
| R10 | Installing on Windows or macOS fails, or the 2 GB index download is interrupted | Medium, high | Resumable downloads, preflight checks, published images, a tested Windows path, the starter index as fallback | PR-21, 30, 62, 63, 64 |
| R11 | Licence trouble: IPC2BNS-Verify has no LICENSE file; HLDC is non-commercial; model licences | Medium, medium | Ask the authors, derive our own table or exclude it, do not ship HLDC, list every licence | PR-69 |
| R12 | Tests written against stubs expose mismatches (the `SKELETON-GAP` and about 270 `ASSUMPTION` markers) and many tests fail at once when the modules land | High, medium | Land modules one route at a time and fix its tests the same day; reconcile as in earlier phases, marking each test change | PR-72, 73 |
| R13 | GPU memory contention: one 8 GB GPU cannot hold the language model, the vision model, the embedder and OCR together | High, medium | Load and unload in turn, single-job queue | PR-23, 11 |
| R14 | Nobody has looked at the UI; visual or flow defects remain on live data | High, medium | A browser check early in week 2, not late | PR-75 |
| R15 | The lawyer over-trusts a fluent draft | Medium, very high | Label, source links on every claim, the verify checklist, the review gates, no confidence score that implies a probability | PR-37, 38, 49 |

### 7.2 What we will explicitly not claim

- **No outcome prediction.** The product never predicts whether bail will be granted, never shows grant rates and never ranks a case by likelihood of success. Urgency ordering in the desk is by deadlines and custody, not by merit.
- **No legal advice.** It prepares a draft for a lawyer. It does not advise accused persons or the public (the landing page points them to NALSA 15100). Every export carries "AI-generated draft. Not legal advice."
- **No coverage beyond what it was built for.** Regular bail in Indian High Courts under CrPC s.439 and BNSS s.483, in one generic format. Not anticipatory bail, not Sessions or Magistrate courts, not other High Court formats, not other kinds of case. Sexual-offence, POCSO and juvenile matters are declined by design. Courts with no BNS-era orders in the index (Madhya Pradesh 0, Kerala 3) are weakly covered.
- **No user study.** There is no legal collaborator and no study with lawyers. We do not claim that it saves a lawyer time or improves outcomes. We report only the proxies of `docs/evaluation-plan.md` section 4.9: items still needing review, sources to open per claim, and errors avoided against the baselines.
- **No claim that the numbers describe a lawyer's judgement.** Evaluation labels come from court text and construction, not from lawyers; results carry intervals, a blind slice and per-court slices, and unrun claims are stated as not run.
- **No claim of legal currency beyond the dates shown.** Rules are verified against bare acts on the stated date; the index ends at the stated data-cut; the law may have moved since.
- **No claim that small local models match the large ones.** Quality per tier is reported as measured; the laptop tier is lower.
- **No claim that handwritten or low-quality scans are read reliably.** The product asks counsel when unsure.
- **No security certification.** There is a threat model for local use and the container hardening that exists; nothing more.

<!-- /SECTION:7 -->

<!-- SECTION:8 -->
## 8. Decisions the team must take
| # | Decision | Options | Recommendation | Needed by |
|---|---|---|---|---|
| D1 | The capacity gap: P0 is about 73.5 product-charged days against a share of 40 to 52 | (a) a fifth person for three weeks, (b) move the product deadline, (c) ship the Preview (about 54 days) and call it that | (c), with (a) if anyone is free; decide before week 1 ends | Day 1 |
| D2 | Which hardware tier is the default for a lawyer | T1 laptop (quantised 8B or 4B, lower quality), T2 (24 GB card, needs hardware the lawyer may not have), T3 (Ada tunnel or Sarvam, not private) | Make T1 the default product tier and T2 an option; use T3 only for the demo; measure T1 quality in week 2 | Day 2 (it shapes PR-20, 21, 22) |
| D3 | Where the 2 GB index is hosted and under what licence terms | GitHub release, Hugging Face dataset, a lab server | Hugging Face dataset or a release, with the CC BY 4.0 attribution file inside | Week 2 |
| D4 | IPC2BNS-Verify licence | wait for the authors, derive our own concordance table from the bare acts, ship without it | email the authors now; if there is no answer by week 3, exclude it from the shipped index and keep it for evaluation only | Now (email), week 3 |
| D5 | Which product changes may land after the evaluation freeze | all, none, only tagged patches | only tagged patches for agent behaviour; everything else unrestricted (section 4.2) | Before the freeze |
| D6 | Who verifies the Rights Radar rules, given no legal collaborator | the team from the bare acts, or ask a teaching assistant, tutor or practising lawyer for a one-hour read | the team verifies from the bare acts, and asks any available lawyer for a read; the guide states that no lawyer reviewed the rules unless one did | Week 1 |
| D7 | Publish images to a public registry | GHCR public, private, build locally | GHCR public (no client data and no weights in images) | Week 3 |
| D8 | Keep or drop the Sarvam consent UI in v1 | ship it (P1), or remove Sarvam from the product and keep it for evaluation only | ship the off-by-default switch with the banner and consent event; if capacity is short, hide the setting and keep `VS_SARVAM=off` fixed in the release | Week 3 |
| D9 | Level of Windows and macOS support | tested, documented, unsupported | one tested Windows machine; macOS documented as CPU-only | Week 3 |
| D10 | Default retention for cases | keep until deleted, auto-delete after N days | keep until deleted, with a visible delete button and the delete-all setting | Week 2 |
| D11 | Is the Preview release for lawyers or for the team and teaching staff only | lawyers, staff only | staff and a trusted lawyer under supervision; not for a real client's file until D6 and the manual QA pass | Week 3 |

<!-- /SECTION:8 -->
