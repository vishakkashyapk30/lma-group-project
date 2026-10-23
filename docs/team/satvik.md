# Satvik: frontend, DOCX and hearing-card export, real-API integration

Part of the team plan in `docs/team/README.md` (read sections 2 to 8 first). This file is the only place you update your own status. Do not edit `progress.md`.

Calendar: Day 1 (D1) is the Monday after the history sync; weeks are D1 to D5, D6 to D10, D11 to D15, D16 to D20. Effort is in person-days (estimates).

## 1. Role summary

You make the product real in the browser: the API app wiring, read routes, upload, dictation and the event stream (the "real-API integration", PR-03, PR-04, PR-05); the court-ready DOCX and the hearing-prep card (PR-13, PR-14, the output the lawyer files); the Gate and checklist UI against live routes (PR-38) and the sensitive-matter decline (PR-39); and the two variant arms that live in the Vakeel and Abhiyojak packages you now own (EV-12). You are the frontend owner and the steward of `frontend/lib/types.ts` and `frontend/lib/api.ts`.

Committed: **19.5 person-days** (W1 5.0, W2 5.0, W3 5.0, W4 4.5). Capacity: 17.5 days at 3.5 weeks, 20 at 4 weeks. W4 keeps 0.5 day for the fixes that come out of Harshita's browser check (PR-75).

## 2. Owned paths

| Path | Notes |
|---|---|
| `frontend/` (everything except Harshita's: `components/landing/`, `components/about/`, `app/about/`, `app/help/`, `app/welcome/`, `components/onboarding/`, `components/legal/`, `components/workspace/tabs/`, `lib/i18n/`, `messages/`) | Next.js app, Vitest, Playwright |
| `frontend/lib/types.ts`, `frontend/lib/api.ts` | shared files; you are the steward (README section 2) |
| `src/vakeel_sahayak/api/app.py`, `asgi.py`, `deps.py`, `sse.py`, `models.py` (shared add-only), `routers/cases.py`, `routers/upload.py`, `routers/events.py`, `routers/desk.py`, `routers/library.py` | Shravani owns `routers/chat.py`, `gates.py`, `export.py`, `brief.py` |
| `src/vakeel_sahayak/export/` | DOCX, List of Dates, hearing card, PDF, templates |
| `src/vakeel_sahayak/agents/vakeel/`, `agents/abhiyojak/` | drafting, claim checking, hearing, sparring, isolation |
| `src/vakeel_sahayak/truth_maintenance/` | dependencies, staleness, redraft |
| Tests that follow your packages: `tests/unit/{api (except test_chat_router.py, test_gates_router.py, test_export_router.py), export, truth_maintenance}`, `tests/unit/agents/{vakeel, abhiyojak}`, `tests/integration/test_vakeel_abhiyojak_sparring.py`, `frontend/tests/`, `frontend/e2e/` | |

## 3. Week-by-week tasks (committed)

Test names are the tests that must go green for the task. PR branch names are suggestions; the target day is the day of the squash merge. Frontend checks for every UI task: `cd frontend && npm run typecheck && npm run lint && npm test` and, when a flow changed, `npm run build && npm run e2e` on the production build.

### Week 1 (D1 to D5): 5.0 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| PR-03 | `create_app()`, config, event-log and gate-guard dependencies, case service layer, per-case locks, session resume after restart; `/api/*` stops answering 503 | `docker compose up` shows a live `/api/cases`; a case survives `docker compose restart` | `tests/unit/api/test_app_and_deps.py`, `tests/unit/api/test_events_router.py` (wiring part) | Contract PR (Vishak, D1) | `feat/api-app-wiring`, D3 | 2.5 |
| PR-04 | Read routes: cases, ingestion report, dossier and field edit, timeline, rights report, budget; the pinned shapes of the rights report and the hearing card; `last_activity` on `CaseSummary`; update `frontend/lib/types.ts`, `lib/mock/*` and the e2e fixtures to the pinned shapes | Routes return typed models; the cause list sorts by `last_activity`; frontend fixtures validate against the pinned shapes | `tests/unit/api/test_cases_router.py`, `tests/integration/test_api_routes.py` (read parts), Vitest and `npm run typecheck` | PR-03, contract PR | `feat/api-read-routes`, D5 | 2.0 (scoped from 2.5) |
| EV-12 (part 1) | S8 arm: `repair_mode` of `grounded`, `self_critique`, `none` in `agents/vakeel/agent.py` and `claims.py` (Vakeel re-reads its own draft with no NLI or tool check) | Default `grounded` behaviour unchanged (prompt hash test); `self_critique` runs the repair step with no outside verifier | `tests/unit/agents/vakeel` | EV-01 (Vishak, D2) | `feat/arm-self-critique-repair`, D5 | 0.5 (of 1.5) |

### Week 2 (D6 to D10): 5.0 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| EV-12 (part 2) | Finish S8; S10 arm: `abhiyojak_isolation: bool = True`, a wider allow-list when False | With False Abhiyojak sees Vakeel's notes; with True the default arm still raises `ContextIsolationError` | `tests/unit/agents/abhiyojak`, `tests/unit/agents/vakeel`, `tests/unit/orchestration/test_switches.py`, `tests/integration/test_vakeel_abhiyojak_sparring.py` | EV-01 | `feat/arm-no-isolation`, D7 | 1.0 |
| PR-05 | Upload and dictation routes, one-job-at-a-time background runner calling the graph entry points, SSE events with progress (step, page n of N); guard rejects planted instructions; sensitive matters are declined and purged through `privacy/` | A 14-page bundle uploads, runs in the background and streams events; reconnect with `Last-Event-ID` resumes | `tests/unit/api/test_upload_router.py`, `tests/unit/api/test_events_router.py`, `tests/system/test_flow1_messy_bundle.py`, `tests/system/test_flow5_dictated_hindi.py` (route parts), `tests/system/test_t7_planted_instructions.py` | PR-03, graph entry points frozen D2 and PR-01 nodes D4 (Shravani) | `feat/api-upload-sse`, D10 | 4.0 (scoped from 5.0; hardening is PR-33) |

### Week 3 (D11 to D15): 5.0 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| PR-14 | Hearing-prep card builder and one-page layout: likely concerns from comparable orders, three points to lead with, conditions from operative orders, open issues; no prediction or grant rate; banner "AI-generated draft. Not legal advice." | The card has the four parts of plan 8.3 on one page and no grant rate anywhere | `tests/unit/export/test_hearing_card.py`, `tests/unit/agents/vakeel` (hearing) | none | `feat/export-hearing-card`, D13 | 2.0 (scoped from 2.5) |
| PR-13 (part 1) | DOCX builder: cause title placeholders, s.483 BNSS heading, synopsis, brief facts, earlier applications, grounds from the brief, statutory position (uses Harshita's statute data), prayer, verification placeholders; `export/templates/` | Sections 1 to 7 render from the case-0007 brief | `tests/unit/export/test_application.py`, `tests/unit/export/test_sections.py` | PR-28 (Harshita, D10) for bailable and cognisable | `feat/export-docx-application`, D15 (draft) | 3.0 (of 4.5) |

### Week 4 (D16 to D20): 4.5 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| PR-13 (part 2) | List of Dates (every date from the timeline with its source), annexure index, cover note of what counsel must verify, banner, `tools/drafting/application.py` stops returning `not_implemented` (hook-in of at most 30 lines, Shravani reviews) | Opens in Word and LibreOffice; every date traces to a timeline event; the DOCX carries the label | `tests/unit/export/test_application.py`, `test_list_of_dates.py`, `tests/unit/tools_drafting`, `tests/system/test_flow3_brief_spar_export.py` (export step), `tests/system/test_t7_draft_label.py` | PR-13 part 1, PR-14 | `feat/export-docx-list-of-dates`, D17 | 1.5 |
| PR-38 | NEEDS_REVIEW, UNANSWERED and UNSUPPORTED workflow against the live gate routes: the gate checklist, acknowledgements logged, Gate modal cannot be passed with an open item | Open items block approval in the browser against the real backend | Vitest, `frontend/e2e/gate2.spec.ts`, `flow3_brief_spar.spec.ts`; `tests/unit/api/test_gates_router.py` (Shravani's) stays green | PR-07 (Shravani, D9), PR-06 | `feat/ui-gate-checklist`, D19 | 2.0 |
| PR-39 | Sensitive-matter decline: message, NALSA 15100 and legal-aid resources, purge of uploaded files (upload route and UI) | A POCSO or sexual-offence upload shows the decline and leaves no file on disk | `tests/system/test_t7_sensitive_matters.py`, `frontend/e2e/flow1_messy_bundle.spec.ts` | PR-05 | `feat/ui-sensitive-decline`, D20 | 1.0 |

Total committed: 5.0 + 5.0 + 5.0 + 4.5 = **19.5**. Per task: PR-03 2.5, PR-04 2.0, PR-05 4.0, PR-13 4.5, PR-14 2.0, PR-38 2.0, PR-39 1.0, EV-12 1.5.

Scope valves, in the order to use them if you fall behind (PR-38 and PR-39 are never cut): PR-13 part 2 can split the cover note and annexure index into a follow-up PR on D19; PR-14 layout polish can follow after D13; PR-04 `budget` route can wait.

## 4. Stretch queue (not committed; rank order)

| Rank | ID | Task | Days |
|---|---|---|---|
| 1 | PR-49 | "What counsel must verify" checklist at Gate 2 | 1.0 |
| 2 | PR-36 | Error-code catalogue and plain messages (`frontend/lib/errors.ts`, `api/models.py`) | 2.5 |
| 3 | PR-09 | Library routes with server-enforced `before`, `sc_root`, `good_law` | 1.0 |
| 4 | PR-08 | Batch desk routes (zip or folder upload, triage board, overnight queue) | 2.5 |
| 5 | PR-57 | Batch desk workflow in the UI | 2.5 |
| 6 | PR-25 | Progress UX: estimate, cancel, safe to leave, completion notification | 2.5 |
| 7 | PR-42 | Privacy indicator in the nav and the per-case Sarvam consent screen | 2.5 |
| 8 | PR-54 | Empty, error, offline and busy states on every page | 2.5 |
| 9 | PR-32 | Settings, health and version API | 1.0 |
| 10 | PR-53 | Settings and health page | 2.5 |
| 11 | PR-52 | Importable sample case (case-0007 with precomputed outputs) | 1.0 |
| 12 | PR-41 | Pseudonymisation visible to counsel (alias map view; real names only in the DOCX cause title on confirmation) | 2.5 |
| 13 | PR-56 | Deadline notifications for default-bail clocks | 2.5 |
| 14 | PR-15 | PDF export and print layout | 2.5 |
| 15 | PR-74 | Playwright setup fixes (pin 1.59 or `npx playwright install`, e2e on `next start`, run the e2e container) | 1.0 |

## 5. Deferred or cut (with the reason)

| ID | Reason |
|---|---|
| PR-19 | P2, a note on court formats; the generic format ships and the banner says "check against your court's rules" |
| PR-59 | P2, in-case search; needs deep edits across workspace components |
| PR-60 | P2, tablet and mobile layout; no lawyer needs it before the first release |
| PR-76 | P1 but 5 days; replaced by the manual QA script (PR-77) and Harshita's browser check (PR-75); first on the cut list of the readiness plan |

## 6. What you need from others

| From | What | Needed by |
|---|---|---|
| Vishak | Contract PR merged (API shapes, `last_activity`, library fields, event payloads) | D1 |
| Vishak | EV-01 `Switches` fields (`repair_mode`, `abhiyojak_isolation`) for EV-12 | D2 |
| Vishak | Review of your PRs is by Shravani (rotation); you review Vishak's PRs | continuous |
| Shravani | Frozen graph interface (`orchestration/state.py`, entry points `start_run`, `resume`, `stream_events`) | D2 |
| Shravani | PR-01 nodes merged (the PR-05 runner calls `start_run`) | D4 |
| Shravani | PR-07 gate routes merged (PR-38 needs them) | D9 |
| Shravani | PR-06 chat and brief routes (PR-38 end-to-end, PR-13 against a real brief) | D13 |
| Shravani | Review of your PRs, one working day; hook-in review for the 30-line edit in `tools/drafting/application.py` | continuous |
| Harshita | PR-28 statute data (CrPC 437 to 439, NDPS 37, First Schedule bail rows) for the statutory position | D10 |
| Harshita | PR-37 UI label and terms component and PR-45 strict demo guard (hook-ins into your files; you review) | D13 |
| Harshita | PR-75 defect list from the browser check | D17 (your fix window is D18 to D19) |
| Harshita | `last_verified`, `source` and `version` per rule in `configs/rights_rules.yaml` (the pinned rights shape allows null until then) | D17 |
| Shravani | TM-02: shared hook (`make hooks`), PR template, `scripts/check_commits.sh` | D1 |
| Shravani | PR-16 export route, to test the DOCX and card download from the browser | D17 |
| Vishak | PR-20 tier statement and PR-23 (only if the settings API, PR-32, is promoted) | D17, D18 |

## 7. What others need from you

| To | What | Date |
|---|---|---|
| Shravani | PR-03 app wiring and response models | D3 |
| Shravani | PR-04 read routes (integration tests) | D5 |
| Shravani | PR-05 upload, dictation, job runner, SSE | D10 |
| Shravani | PR-14 hearing card | D13 |
| Shravani | PR-13 DOCX with banner (PR-16 export route needs it) | D17 |
| Shravani | Fixes in `api`, `export`, `truth_maintenance`, Vakeel and Abhiyojak when a system or integration test fails there (`co-fix` tickets, one working day) | D16 to D19 |
| Vishak | EV-12 arms (S8, S10) merged so the sparring jobs can run | D7 |
| Vishak | PR-13 and PR-14 for the F5 and F6 stretch jobs | D17 |
| Harshita | Live reads and uploads (PR-04 D5, PR-05 D10) so PR-75 can start; a way to run the stack in live mode on the offline stand-ins (`docker compose up`, strict demo guard) | D14 |
| Harshita | Review of her frontend hook-ins (PR-37, PR-45) within one working day | continuous |
| All | Stewardship of `frontend/lib/types.ts` and `frontend/lib/api.ts`: changes to the two files go through your review | continuous |

## 8. Status table (update this, nothing else, when a state changes)

States: todo, doing, review, merged, blocked, dropped.

| ID | State | PR link | Merged on (Day) | Notes |
|---|---|---|---|---|
| PR-03 | todo | | | |
| PR-04 | todo | | | |
| EV-12 | todo | | | |
| PR-05 | todo | | | |
| PR-14 | todo | | | |
| PR-13 | todo | | | |
| PR-38 | todo | | | |
| PR-39 | todo | | | |
| Stretch taken (list IDs) | | | | |

Task index for this file (every ID that is yours): committed PR-03, PR-04, PR-05, PR-13, PR-14, PR-38, PR-39, EV-12; stretch PR-08, PR-09, PR-15, PR-25, PR-32, PR-36, PR-41, PR-42, PR-49, PR-52, PR-53, PR-54, PR-56, PR-57, PR-74; deferred PR-19, PR-59, PR-60, PR-76.
