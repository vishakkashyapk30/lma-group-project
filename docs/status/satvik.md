# Status: Satvik

My tasks (split.md stream B): SA-01 to SA-08. Updated 2026-10-26. All finished work is on `main` (no task branches).

| Task | State |
|---|---|
| SA-04 DOCX application, List of Dates | done |
| SA-05 hearing card, objections sheet, PDF, gated `export_case` | done |
| SA-08 F5 and F6 evaluation arms | done |
| SA-02 real-API mode, Settings page, `/healthz` settings | done |
| SA-01 Vitest and Playwright reconciled with the redesign | done |
| Fix: SSE stream blocked every API request (Shravani's area; please review) | done |
| Fix: Munshi ignored the files the upload route hands over (Vishak's area; please review) | done |
| SA-06 case flow in the UI against the real API | in progress |
| SA-03 workspace visual QA, DESIGN.md "Workspace principles" | not started |
| SA-07 onboarding, empty states, Hindi strings, axe audit | not started |

## Test results (Python 3.10 venv, offline models)
- Export, drafting tools, API, the gate and API-route integration tests and four system test files: 279 passed; the 41 remaining failures also fail on `main` (none new), and 67 that failed on `main` now pass.
- Frontend: Vitest 244 passed (with SA-02); Playwright 64 passed twice on a production build (was 9 of 69).

## Notes
- `api/asgi.py` (Shravani's area) now reports read-only settings in `GET /healthz`: models, LLM backend, external-service gates, data folder; never a key.
- Production frontend builds are in live mode: if the API does not answer, pages show an error and never the sample case. `NEXT_PUBLIC_API_MODE=demo` (or `NEXT_PUBLIC_API_BASE=demo`) builds the sample-data mode.

## For the team
- **Shravani:** the SSE route iterated the blocking `EventLog.subscribe` inside an async route, so the whole API froze once a browser opened a case (fixed on `main`: `EventLog.follow`). Still open in your area: the three `test_sse_*` integration tests read a never-ending stream through TestClient and time out; `tests/system/test_t7_name_leaks.py::test_no_planted_name_in_any_re...` hangs on `main`; the export router writes JSON for the List of Dates, objections and card where `export.exporter.export_case` writes all four as DOCX (and PDFs); there is no route to download the exported files, so the frontend's export links point at server paths.
- **Everyone on Python 3.10:** fixture timestamps ending in `Z` fail `datetime.fromisoformat` (3.11+ accepts them), which errors about 40 API and record tests. The Docker image uses 3.12.
- **Vishak:** `make setup` is still a stub (`uv venv .venv && uv pip install -e ".[data,dev]"` works); the offline feature runs need `VS_MODELS=offline` exported, because `models_mode()` reads the process environment, not `.env`; with offline models Peshkar extracts almost nothing from T1 facts, so F5 offline numbers describe the harness only.
- **Frontend tooling:** Next.js 15 needs Node 18.18 or newer (Ubuntu's apt Node is 12).

## SA-06 next steps
1. The upload route runs only Munshi; Peshkar (facts, List of Dates, rights report) must follow it, as the LangGraph flow does. The upload, draft, chat and desk routes run agents inside async handlers and freeze the API while they work; run them in a worker thread.
2. Fix the frontend issues it shows; list backend issues for Shravani; add a Playwright spec that runs against a live API when one is configured.
