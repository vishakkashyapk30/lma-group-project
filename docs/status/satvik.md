# Status: Satvik

My tasks (split.md stream B): SA-01 to SA-08. One branch per task, stacked where one needs another. Updated 2026-10-26.

| Task | Branch | State |
|---|---|---|
| SA-04 DOCX application, List of Dates | `feat/export-docx` | done, pushed |
| SA-05 hearing card, objections sheet, PDF, gated `export_case` | `feat/export-hearing-pdf` (on SA-04) | done, pushed |
| SA-08 F5 and F6 evaluation arms | `feat/eval-f5-f6` (on SA-05) | done, pushed |
| SA-02 real-API mode, Settings page, `/healthz` settings | `feat/frontend-real-api` | done, pushed |
| SA-01 Vitest and Playwright reconciled with the redesign | `test/frontend-reconcile` | done, pushed |
| Fix: SSE stream blocked every API request | `fix/sse-nonblocking` | done, pushed (in Shravani's area; please review) |
| SA-06 case flow in the UI against the real API | `feat/frontend-flow` (local, on SA-01 + SA-02) | in progress |
| SA-03 workspace visual QA, DESIGN.md "Workspace principles" | | not started |
| SA-07 onboarding, empty states, Hindi strings, axe audit | | not started |

## Test results (Python 3.10 venv, offline models)
- Export, drafting tools, API, the gate and API-route integration tests and four system test files: 279 passed; the 41 remaining failures also fail on `main` (none new), and 67 that failed on `main` now pass.
- Frontend: Vitest 244 passed (with SA-02); Playwright 64 passed twice on a production build (was 9 of 69).

## Merge notes
- Merge order: `feat/export-docx`, then `feat/export-hearing-pdf`, then `feat/eval-f5-f6` (each contains the one before); `feat/frontend-real-api` and `test/frontend-reconcile` are independent of each other and were checked together (Vitest and Playwright green).
- `feat/frontend-real-api` adds read-only settings to `GET /healthz` in `api/asgi.py` (Shravani's area): models, LLM backend, external-service gates, data folder; never a key.
- Production frontend builds are now in live mode: if the API does not answer, pages show an error and never the sample case. `NEXT_PUBLIC_API_MODE=demo` (or `NEXT_PUBLIC_API_BASE=demo`) builds the sample-data mode.

## For the team
- **Shravani:** the SSE route iterated the blocking `EventLog.subscribe` inside an async route, so the whole API froze once a browser opened a case (see `fix/sse-nonblocking`). Still open in your area: the three `test_sse_*` integration tests read a never-ending stream through TestClient and time out; `tests/system/test_t7_name_leaks.py::test_no_planted_name_in_any_re...` hangs on `main`; the export router writes JSON for the List of Dates, objections and card where `export.exporter.export_case` writes all four as DOCX (and PDFs); there is no route to download the exported files, so the frontend's export links point at server paths.
- **Everyone on Python 3.10:** fixture timestamps ending in `Z` fail `datetime.fromisoformat` (3.11+ accepts them), which errors about 40 API and record tests. The Docker image uses 3.12.
- **Vishak:** `make setup` is still a stub (`uv venv .venv && uv pip install -e ".[data,dev]"` works); the offline feature runs need `VS_MODELS=offline` exported, because `models_mode()` reads the process environment, not `.env`; with offline models Peshkar extracts almost nothing from T1 facts, so F5 offline numbers describe the harness only.
- **Frontend tooling:** Next.js 15 needs Node 18.18 or newer (Ubuntu's apt Node is 12).

## SA-06 next steps
1. Merge `fix/sse-nonblocking` into `feat/frontend-flow`, restart the API, and re-run the browser walk-through (create case, upload a T2 K1 bundle, review and confirm facts, rights, draft, hearing card, approve, export).
2. Fix the frontend issues it shows; list backend issues for Shravani; add a Playwright spec that runs against a live API when one is configured.
