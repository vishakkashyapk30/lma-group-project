# Status — Shravani

My assigned tasks (owner's day-1 message §7): **the LangGraph flow, the API routes with Swagger docs, and the integration + system tests.**

## Task list & implementation plan

### Task 1 — Orchestration / LangGraph flow  ← DONE (unit tests green; invoke-path exercised by Task 3)
Files: `src/vakeel_sahayak/orchestration/graph.py`, `fallback_state_machine.py`.
Spec encoded in: `tests/unit/orchestration/test_graph.py` (route + build_graph), `test_fallback_state_machine.py`.

Reference flow (already works offline, no LangGraph): `eval/runners/driver.run_agents` + `eval/baselines/full_system.run_case`. Nodes mirror it, one agent step each.

- [x] `route_after_gate(state)` — conditional edge after a gate. Rules: Gate 1 pending → never plan/draft/spar/export; Gate 2 pending → never export; stage BRIEF + nothing pending → `plan`; stage FILE + nothing pending → `export`; otherwise END.
- [x] 11 node bodies, each `CaseGraphState -> CaseGraphState`, building an `AgentContext` from the state and driving one agent:
  - `intake_node` (Munshi, skip if no files) · `dossier_node` (Peshkar → stage DOSSIER) · `gate1_node` (`await_gate` GATE_1, stage BRIEF on approval) · `plan_node` (Sutradhar retrieval → evidence packs) · `draft_node` (Vakeel draft + failed-claim handling) · `spar_node` (Abhiyojak sparring → stage SPAR) · `hearing_prep_node` (Vakeel hearing card → stage HEARING_PREP) · `gate2_node` (`await_gate` GATE_2, stage FILE on approval) · `export_node` (gated export, done) · `change_detection_node` (Peshkar diff) · `redraft_node` (incremental redraft of stale claims).
- [x] `build_graph(config)` — LangGraph `StateGraph(CaseGraphState)` + SqliteSaver checkpointer + interrupt gates. Edges: START conditional→{intake, change_detection}; intake→dossier→gate1; gate1 conditional→{plan, END}; plan→draft→spar→hearing_prep→gate2; gate2 conditional→{export, END}; export→END; change-set path: change_detection→redraft→gate1. **Invariants held:** export reachable ONLY from gate2; plan reachable only from gate1.
- [x] `PlainStateMachine(log).run(state)` — same gates via `await_gate(interrupt=False)`, advances to the next unapproved gate or the end, writes to the shared log. Stops at Gate 1 on a fresh case.
- [x] Green: `tests/unit/orchestration/` — **260 passed**, ruff clean, `make smoke` still OK.

**Open / to refine in Task 3:** (a) `build_graph` uses an in-memory checkpointer — the API layer must pass a persistent SqliteSaver + `thread_id=case_id` for cross-request resume; (b) each node builds a fresh `AgentContext`, so the budget does not yet carry across nodes (use `state.budget_tracker`); (c) node bodies drive one agent each (draft=Vakeel.run, spar=Abhiyojak.run) — the reference `delegate` also does Sutradhar-side failed-claim re-retrieval, add if integration tests need it; (d) change-set path redrafts then re-approves (plan prose is re-approve then redraft) — revisit if a test pins the order.

### Task 2 — API routes with Swagger docs  ← DONE (117/119 unit; 2 failures are a pre-existing Sutradhar bug)
Files: `src/vakeel_sahayak/api/*`. All 8 routers built on the folded views (`record/case_state.py`) and the shared record.

- [x] `api/deps.py` — `get_config`, `get_event_log` (one SQLite record per `VS_DATA_DIR`, overridable), `get_gate_guard`.
- [x] `api/app.py` — `create_app()` mounts all routers + CORS. **Note:** this FastAPI (0.162) includes routers lazily, so `create_app` adds each router's routes directly to `app.routes` to materialise them eagerly (the route-list test iterates `app.routes`).
- [x] `api/service.py` — shared helpers: case lookup/404, cause-list summary, Rights Radar chips (urgent first), stage derivation, `agent_context` (tools from the registry).
- [x] Routers: **cases** (cause list, all tabs, field edit, draft, page images), **gates** (checklist + approve, 409/403/404/422), **export** (gated DOCX/PDF, writers in `vakeel_sahayak.export`), **desk** (zip/PDF upload, triage board, open), **library** (reasoning search, citation graph, IPC↔BNS bridge), **chat** (Sutradhar `answer_chat` + history), **upload** (files + dictation), **events**/**sse** (SSE replay + follow).
- [x] `record/event_log.py`: added `case_ids()` (read-only, for the cause list).
- [x] `record/gates.py`: `gate_status` now subtracts counsel's `resolve` USER_ACTION items (the documented Scenario contract) — required for Gate 2 approval.
- [x] Adapted `tests/system/_helpers.Scenario` wiring (its docstring sanctions this): `self.log = deps.get_event_log(...)`, `GateGuard(self.log)` — so the API and the agents share one record. RECONCILED `make_events` off-by-one in `tests/unit/api/_helpers.py` (ev0001 is now TOOL_CALL, matching `test_frame_carries`).
- [x] `ruff check src/vakeel_sahayak/api` clean (Depends/Header via `Annotated`).

**Known 2 failures (NOT this router's bug):** `test_custody_question...` and `test_section_equivalent...` in `test_chat_router.py` fail because Sutradhar's `_chat_custody`/`_chat_section` mis-call their tools (tool-arg validation error). The identical path fails in `tests/system/test_flow2_quick_chat.py` (7 failures), so it's a pre-existing Sutradhar/chat-handler issue for its owner (Vishak), surfaced now that the API exists. The chat router itself is correct (delegates to `answer_chat`, persists Q/A).

**Deferred:** `CaseSummary.last_activity` not added (no test needs it; add when the frontend does).

### Task 3 — Integration & system tests
Files: `tests/integration`, `tests/system` (plan §13.6 user flows 1–7 + the T7 safety suite). Pass once the graph (Task 1) and API (Task 2) exist.

## Log
- 2026-10-26: env built (`.venv`, `.[data,dev]`); `make smoke` passes offline; synced to `origin/main` c0d51dd (clean, no reset needed); `backup/shravani` created. HF data download blocked — account `shravaniiith` not yet granted access to the private dataset.
- 2026-10-26: **Task 1 done** — orchestration graph + fallback machine; `tests/unit/orchestration` 260 passed (was 26 failed/14 passed).
- 2026-10-26: **Task 2 done** — all 8 API routers + deps/app/service/sse; `tests/unit/api` 117/119 (2 failures are a pre-existing Sutradhar chat-handler bug, also failing in system flow2). Added `EventLog.case_ids()`, `gate_status` resolve-handling. `make smoke` + `tests/unit/{record,orchestration}` (317) still green; ruff clean. Nothing committed yet.
- **Next: Task 3** (integration + system tests). These run full fake-model agent flows (slow) and will surface shared-agent bugs owned by others (e.g. the Sutradhar chat-handler tool-arg bug above).
