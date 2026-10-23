# Shravani: critical path owner (graph, gates, chat, brief, export route, integration and system tests)

Part of the team plan in `docs/team/README.md` (read sections 2 to 8 first). This file is the only place you update your own status. Do not edit `progress.md`.

Calendar: Day 1 (D1) is the Monday after the history sync; weeks are D1 to D5, D6 to D10, D11 to D15, D16 to D20. Effort is in person-days (estimates).

## 1. Role summary

You own the one chain that cannot be shortened: LangGraph flow (PR-01), then gate routes (PR-07), then chat, draft, brief, spar and hearing routes (PR-06), then the gated export route (PR-16), then integration tests (PR-72) and system tests (PR-73). You are the only person on this chain, so nothing else is allowed to block you: Satvik delivers the app wiring on D3, and the graph interface is frozen by you on D2 so that others can build against it. You also own the shared repo hygiene (TM-02: commit hook, PR template, check script).

Committed: **20.5 person-days** (W1 5.0, W2 5.0, W3 5.0, W4 5.5). Capacity: 17.5 days at 3.5 weeks, 20 at 4 weeks. You have zero slack. If you fall more than one day behind on PR-01, move EV-14 to the stretch queue without asking (README section 11).

## 2. Owned paths

Under `src/vakeel_sahayak/` unless stated.

| Path | Notes |
|---|---|
| `orchestration/` (except `orchestration/switches.py`, which Vishak owns) | graph, state, gates, budgets, structured output, fallback |
| `record/` | event log, case state, views, checkpoint |
| `contracts/` | the twelve evidence contracts |
| `privacy/` | pseudonymisation, boundary, injection guard, sensitive matters |
| `tools/` (everything except `tools/intake/`) | registry, drafting, case, caselaw, law, advocacy |
| `agents/base.py`, `agents/registry.py` | agent base class and registry |
| `api/routers/chat.py`, `api/routers/gates.py`, `api/routers/export.py`, `api/routers/brief.py` (new file created in the contract PR) | the critical-path routes; Satvik owns the other API files |
| `schemas/` | steward of the shared add-only rule (README section 2) |
| `configs/budgets.yaml`, `configs/tools.yaml` | per-file owner rule |
| `scripts/git-hooks/`, `scripts/check_commits.sh`, `scripts/run_api.sh`, `.github/` (PR template, optional CI), `Makefile` | steward of `Makefile` for new targets (`hooks`, `check-commits`) |
| `tests/integration/` (except `test_munshi_to_peshkar.py`, `test_sutradhar_with_fakes.py`, `test_batch_queue_resume.py`, which follow Vishak's packages), `tests/system/` | |
| `tests/unit/{orchestration, record, contracts, privacy, schemas, config, tools, tools_drafting, tools_law_case, tools_case, tools_caselaw, tools_advocacy}`, `tests/unit/agents/base` | |
| `tests/conftest.py`, `tests/fakes/`, `tests/fixtures/`, `tests/README.md` | steward of the shared test rules |

## 3. Week-by-week tasks (committed)

Test names are the tests that must go green for the task. PR branch names are suggestions; the target day is the day of the squash merge.

### Week 1 (D1 to D5): 5.0 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| TM-02 | Versioned `scripts/git-hooks/commit-msg` that strips AI-attribution trailers and lines, `make hooks` (sets `core.hooksPath`), `scripts/check_commits.sh <range>` (fails on attribution lines and on `# RECONCILED` without a reason), `.github/pull_request_template.md` from README section 4 | After `make hooks`, a test commit containing an attribution trailer is cleaned; the check script exits non-zero on a planted one | none (shell); `make test-collect` stays clean | none | `feat/repo-hygiene`, D1 | 0.5 |
| PR-01 (interface, part of PR-01) | Freeze `orchestration/state.py`: node names, event kinds, entry points `start_run(case_id, kind)`, `resume(case_id, decision)`, `stream_events(case_id, after_id)` | Frozen shapes merged and announced to Satvik and Vishak | `tests/unit/orchestration/test_state.py` | contract PR (Vishak, D1) | `feat/graph-interface`, D2 | (inside PR-01) |
| PR-01 (part 1) | LangGraph flow: Munshi, Peshkar, Gate 1 interrupt, Sutradhar/Vakeel/Abhiyojak loop, Gate 2 interrupt, export node; gate router; SQLite checkpointer keyed by case id | All nine node functions and `build_graph` implemented; export is unreachable before Gate 2 | `tests/unit/orchestration/test_graph.py` (nodes, router, gates), `tests/unit/orchestration/test_gates.py`, `tests/integration/test_gates_interrupts.py` | none | `feat/graph-nodes-gates`, D4 | 4.5 (of 5.0) |

### Week 2 (D6 to D10): 5.0 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| PR-01 (part 2) | Resume after a kill from the checkpoint; the change-set path (new document, Peshkar diff, Gate 1 again, truth maintenance, partial redraft) | A killed process resumes at the last node; the change-set run redrafts only affected grounds | `tests/unit/orchestration/test_graph.py` (all), `tests/integration/test_event_log_resume_trace.py`, `tests/integration/test_change_set_flow.py` | PR-01 part 1; `truth_maintenance/` (Satvik, done) | `feat/graph-resume-changeset`, D7 | 0.5 |
| PR-07 | Gate 1 and Gate 2 routes: resolve checklist items, counsel answers to Munshi's questions, dictation read-back confirm, ChangeSet route (paths per the contract PR) | Approval is refused while an UNSUPPORTED, NEEDS_REVIEW or UNANSWERED item is open; no route lets counsel resolve a Gate 2 item (only the lawyer path in the contract) | `tests/unit/api/test_gates_router.py`, `tests/integration/test_gates_interrupts.py` | PR-03 (Satvik, D3), PR-01 | `feat/api-gates`, D9 | 2.5 |
| PR-06 (part 1) | Chat route through the Sutradhar chat router; draft start route; SSE events for plan and progress | A question gets a cited one-line answer with store and tool chips; a draft run starts and streams events | `tests/unit/api/test_chat_router.py` | PR-03, PR-01 | `feat/api-chat-draft`, D10 | 2.0 (of 5.0) |

### Week 3 (D11 to D15): 5.0 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| PR-06 (part 2) | Brief, spar and hearing-prep routes in `api/routers/brief.py`; budget stop visible; before-date set to the case's own date | Flows 2 and 3 run through HTTP up to Gate 2; every answer carries chips | `tests/integration/test_api_routes.py` (chat, brief, spar parts), `tests/system/test_flow2_quick_chat.py`, `tests/system/test_flow3_brief_spar_export.py` (up to export) | PR-01, PR-07 | `feat/api-brief-spar`, D13 | 3.0 |
| PR-40 | Refusals and abstention through the chat route: predictions, grant rates, lay advice, bulk export, pressure ("just export it"); an unanswerable factor is stated as a gap; scoped to wiring because the agents already refuse | The T7 refusal suites pass and the message cites NALSA 15100 where required | `tests/system/test_t7_prediction_lay_advice.py`, `test_t7_pressure.py`, `test_t7_bulk_export.py` | PR-06 | `feat/chat-refusals`, D15 | 1.0 |
| PR-72 (part 1) | Integration tests: fix each file as its route lands (`test_api_routes.py`, `test_gates_interrupts.py`, `test_event_log_resume_trace.py`, `test_change_set_flow.py`) | Those four files pass; other owners fix mismatches in their own packages (README section 4, "co-fix rule") | the four files named | PR-01, PR-06, PR-07 | `fix/integration-api-graph`, D14 | 1.0 (of 1.5) |

### Week 4 (D16 to D20): 5.5 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| PR-72 (part 2) | Remaining integration files with Satvik's PR-05 (upload and SSE) and Vishak's files | `tests/integration` passes with default markers | `tests/integration/` (all) | PR-05 (Satvik, D10) | `fix/integration-rest`, D16 | 0.5 |
| PR-16 | Export route: gated download, 403 before Gate 2, file names, stamp with brief version, banner present | 403 before Gate 2 in a test; the DOCX and the card download after Gate 2 | `tests/unit/api/test_export_router.py`, `tests/unit/export/test_exporter.py`, `tests/system/test_t7_pressure.py`, `tests/system/test_t7_draft_label.py` | PR-03, PR-07, PR-13 (Satvik, D17), PR-14 (Satvik, D13) | `feat/api-export-gated`, D17 | 1.0 |
| PR-73 | System tests: flows 1 to 7 and the T7 suites; the slow 120-file desk test and the `models` and `gpu` variants are excluded from the committed scope | `tests/system` passes with default markers (slow tests included only if time allows); each failure is fixed by the owner of the package that causes it (co-fix rule) | `tests/system/` (all 14 files) | PR-72, PR-16, PR-40; PR-05 (Satvik) for flows 1, 5 and 6 | `fix/system-flows-1-7`, `fix/system-t7`, D16 to D19 | 2.5 |
| EV-14 (T) | S15 output formats: `output_format` of `reasoning_first`, `answer_only`, `free_then_parse` implemented only in `orchestration/structured_output.py` (no prompt edits in other owners' files) | The three formats parse to the same schema; the reasoning field is never read as an answer; default behaviour unchanged | `tests/unit/orchestration/test_structured_output.py`, `tests/unit/orchestration/test_switches.py` | EV-01 (Vishak, D2) | `feat/structured-output-formats`, D19 | 1.5 |

Total committed: 5.0 + 5.0 + 5.0 + 5.5 = **20.5**. Per task: TM-02 0.5, PR-01 5.0, PR-07 2.5, PR-06 5.0, PR-40 1.0, PR-72 1.5, PR-16 1.0, PR-73 2.5, EV-14 1.5.

Critical path sequence (do not reorder): interface freeze D2, PR-01 D4 and D7, PR-07 D9, PR-06 D10 and D13, PR-72 D14 to D16, PR-16 D17, PR-73 D16 to D19.

## 4. Stretch queue (not committed; rank order)

| Rank | ID | Task | Days |
|---|---|---|---|
| 1 | PR-02 | Plain-Python fallback state machine with the same gate rules (`tests/unit/orchestration/test_fallback_state_machine.py`) | 1.0 |
| 2 | PR-10 | Settle reconcile items (approval `unresolved` wording, duplicate documents on re-ingest, Munshi double read); hook-in edits to `ingestion/filing.py` and `agents/munshi/toolkit.py` need Vishak's review | 1.0 |
| 3 | EV-17 | S17 injection defences (typed hand-off, spotlighting, text-layer versus OCR cross-check); hook-ins into `agents/peshkar/` and `ingestion/signals.py` need Vishak's review | 3.0 |
| 4 | PR-11 | Long-job control: single-GPU queue, cancel, idempotent re-ingest, two tabs | 2.5 |
| 5 | PR-17 | Editable brief backend: edit events, re-check, version history | 2.5 |
| 6 | PR-44 | Case deletion, retention, bundle export and import | 2.5 |
| 7 | PR-43 | Audit trail export | 2.5 |
| 8 | PR-66 | Logs with pseudonymised text only, rotation, diagnostics bundle | 1.0 |
| 9 | PR-65 | Backup, restore and data-schema migration | 2.5 |
| 10 | PR-70 | Security review and threat model for local use | 2.5 |

## 5. Deferred or cut (with the reason)

| ID | Reason |
|---|---|
| PR-71 | P2, optional passphrase lock; local single-user use does not need it for the first release |

## 6. What you need from others

| From | What | Needed by |
|---|---|---|
| Vishak | Contract PR merged (shapes for the graph interface, gate routes, `Switches` fields) | D1 |
| Vishak | EV-01 `Switches` fields (`output_format`) for EV-14 | D2 |
| Vishak | Reviews of your PRs (rotation: Vishak reviews Shravani); turnaround one working day | continuous |
| Satvik | PR-03: `create_app()`, dependencies, response models in `api/models.py` | D3 |
| Satvik | PR-04 read routes (needed only by integration tests) | D5 |
| Satvik | PR-05 upload, dictation, job runner and SSE (needed by PR-72 and PR-73 flows 1, 5, 6) | D10 |
| Satvik | PR-14 hearing card builder | D13 |
| Satvik | PR-13 DOCX builder with the "AI-generated draft. Not legal advice." banner | D17 (for PR-16) |
| Satvik, Vishak, Harshita | Fixes in their own packages for failing system and integration tests, within one working day of your ticket (labelled `co-fix`) | D16 to D19 |
| Harshita | PR-37 and PR-45 merged (UI label, strict demo guard) so the system and browser checks are consistent | D13 |
| Harshita | PR-75 defect list | D17 (fixes D18 to D19) |

## 7. What others need from you

| To | What | Date |
|---|---|---|
| All | TM-02: hook, `make hooks`, PR template, `scripts/check_commits.sh` | D1 |
| Satvik, Vishak | The frozen graph interface (`orchestration/state.py`) and entry points | D2 |
| Satvik | PR-01 merged (his PR-05 job runner calls `start_run`) | D4 (nodes) and D7 (resume) |
| Satvik | PR-07 gate routes, needed by his PR-38 Gate UI | D9 |
| Harshita | PR-06 chat, brief and spar routes live, for her first browser pass (PR-75) | D13 |
| Satvik | PR-16 export route for the UI export button | D17 |
| Vishak | EV-14 S15 output formats | D19 |
| Vishak | `GateGuard` semantics unchanged (the evaluation driver relies on them) | continuous; tell Vishak before any change |
| All | `tests/conftest.py` and `tests/fakes/` changes only through you or with your review | continuous |
| Harshita | Review of her PR-75, PR-77 and PR-81 PRs, and the README follow-through on a clean clone | D18 |
| All | Reviews: you review Satvik's PRs (rotation), second reviewer on gate-related PRs of anyone | one working day |

## 8. Status table (update this, nothing else, when a state changes)

States: todo, doing, review, merged, blocked, dropped.

| ID | State | PR link | Merged on (Day) | Notes |
|---|---|---|---|---|
| TM-02 | todo | | | |
| PR-01 (interface) | todo | | | |
| PR-01 (part 1) | todo | | | |
| PR-01 (part 2) | todo | | | |
| PR-07 | todo | | | |
| PR-06 (part 1) | todo | | | |
| PR-06 (part 2) | todo | | | |
| PR-40 | todo | | | |
| PR-72 | todo | | | |
| PR-16 | todo | | | |
| PR-73 | todo | | | |
| EV-14 | todo | | | |
| Stretch taken (list IDs) | | | | |

Task index for this file (every ID that is yours): committed TM-02, PR-01, PR-06, PR-07, PR-16, PR-40, PR-72, PR-73, EV-14; stretch PR-02, PR-10, PR-11, PR-17, PR-43, PR-44, PR-65, PR-66, PR-70, EV-17; deferred PR-71.
