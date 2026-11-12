# Status: Satvik

## Current assignment (13 Nov 2026)
Open the PR for `satvik-companies-act-212` (rebased on `main`); one statute store rebuild with the BNSS s.58 and s.212 fixes (with Shravani's CrPC/NDPS texts if ready) and a bundle refresh, never touching the frozen run worktree; rerun `win_loss_tie.py` on every family and confirm the M6a test runs.
Full list: `docs/handoff/team-todo-2026-11-02.md`, section "What each person does next (13 November)".

## Earlier assignment (2 Nov 2026, to the freeze on 10 Nov)
Metrics, statistics and Rights: DONE 2 Nov (PR #6). Next: Companies Act s.212 from the official text by script; rerun the win/loss/tie table and the M6a test once the architecture search is merged; statute store rebuild after the search. Details in `docs/handoff/team-todo-2026-11-02.md`.
Full list, dates and rules: `docs/handoff/team-todo-2026-11-02.md`. The tables below are the earlier state.

**2 Nov, branch `satvik-metrics-rights`: all five done** (details, results and the steps left for others in `docs/handoff/metrics-rights-2026-11-02.md`). Rights: 6 of 7 rules match the statute store (`antil_category` cites the Companies Act s.212(6), not in the store); BNSS s.58 from the Gazette; no arm beats every baseline on every metric yet; consistency checks find two numbers in the pre-registration that disagree with `dev_stats.json`.

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
| SA-06 case flow in the UI against the real API | done (`frontend/e2e/live_flow.spec.ts`, run with `E2E_LIVE_API=1`) |
| SA-03 workspace visual QA, DESIGN.md "Workspace principles" | done |
| SA-07 onboarding, empty states, Hindi strings, axe audit | done, except a Hindi translation of the interface (see below) |
| Frontend merge: `frontend-endeavours` into `main` (2026-11-01) | merged on local branch `frontend-merge` (clean, no conflicts; SA-06 was already on `main`); waits for the owner's go-ahead before it goes to `main` |
| Rights rule verification in the UI (`docs/handoff/code-final.md` §6) | done on `frontend-merge`: every check's "Why" shows "Verified against the bare act on <date>" or "Rule text not yet verified against the bare act" beside the rule text; one line at the top of Check rights names the unverified checks; reads `verification` / `unverified_checks`, falls back to `last_verified` on an older backend. The sample case mirrors `configs/rights_rules.yaml` after the automatic Rights check (6 of 7 verified 2026-11-02, PR #6; was all 7 on a made-up date) |

## Test results (Python 3.10 venv, offline models)
_Checked by Vishak 2026-10-27: Python 3.11 is now the minimum (`docs/handoff/python-and-defaults.md`), and `make setup` (the "still a stub" line below) is real (`docs/handoff/fresh-clone-fixes.md`)._
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

## What is left
- **Hindi interface strings (SA-07):** every Hindi text the app shows is marked `lang="hi"`, but the interface itself is English only. Translating its labels (legal terms such as Gate, objection, default bail) needs a Hindi-speaking teammate to write or review them; a machine translation could mislead counsel, so none was added.
- **Backend follow-ups found by SA-06** (Vishak/Shravani): the hearing card can pick a quoted paragraph number as a concern (`agents/vakeel/hearing.first_sentence`; the client falls back to the factor); on offline models, Vakeel's claim checks can refuse a sentence as "not safe to send to Ada" when a name is not pseudonymised, which then shows as an open issue.
