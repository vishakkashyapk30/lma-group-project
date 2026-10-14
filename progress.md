# progress.md: Vakeel-Sahayak.ai

Status as of 2026-10-14. Nothing is committed yet; all work below sits uncommitted on branch `ideation-v1`.

---

## 1. Plan v5 (done)

**File:** [docs/plan.md](docs/plan.md), rewritten from v4 to v5 in response to the TA's feedback.

**TA feedback, and how v5 answers it** (Section 0 of the plan maps each point):

| TA feedback | Where the plan answers it |
|---|---|
| How are different kinds of PDF handled? | Munshi, the ingestion agent (§4) |
| Ingestion must be an agent | Munshi's agent loop (§4.3) |
| Use several RAG databases | Ten stores on four shelves (§5) |
| An agent must orchestrate what comes from each database | Sutradhar, with evidence contracts (§6) |
| Not novel in agentic engineering | §7–11 and §14 |
| Required baselines | B0–B4 (§15.3) |
| Frame it as an engineering problem | §1.2 |

**Decisions made in ideation:**

- **Features:** all eight new ones.
  - Agentic: prosecution sparring (Abhiyojak), incremental redrafting (truth maintenance), Rights Radar, batch triage desk (Pairokar).
  - Lawyer-facing: court-ready application, hearing-prep card, precedent explorer, Hindi and voice intake.
- **Evaluation:** every feature is evaluated fully (F1–F8), with its own baseline or ablation.
- **Agent names:** court-office names: Munshi, Peshkar, Sutradhar, Vakeel, Abhiyojak, Pairokar.
- **Frontend** (plan §13):
  - Next.js, replacing Streamlit.
  - "Manuscript" palette (maroon, cream and gold), with contrast checked.
  - The landing page combines all four concepts: Nyay ki Devi hero, a citizen's journey, geometry-of-justice transitions, a living-manuscript finale.
  - Each agent gets its own animation in the app.
  - The workspace is a stage rail above three panes.
- **Compute:** about 1,220 RTX 2080 Ti GPU-hours, about 56 Ada sessions (73 with buffer). That is about twice v4's budget, and needs all three accounts.

**To verify in week 0:**
- The Rights Radar rule texts (Appendix C). *Kapil Wadhawan* and *M. Ravindran* were cited from memory.
- Licences for HLDC, Kathbath, Surya weights and Indic Parler-TTS.

**Open questions raised by the proposal agent:**
- Is the limit of 3 questions to counsel per round or per case?
- The week 6–7 run schedule is tight.
- Do the RQ2 vision-model results come from the laptop's 4B model or Ada's 8B model?

## 2. Proposal (done)

**[docs/proposal/proposal.md](docs/proposal/proposal.md)** is rewritten to match plan v5 (≈584 lines, up from ≈477).

**New architecture diagram:**
- [docs/proposal/figures/architecture_v5.mmd](docs/proposal/figures/architecture_v5.mmd) is the Mermaid source.
- It is rendered as [.svg](docs/proposal/figures/architecture_v5.svg) and [.png](docs/proposal/figures/architecture_v5.png).
- The same diagram is embedded in §7 of proposal.md.

**Not updated (still v4):** `proposal.tex`, `proposal.pdf` and the old `figures/architecture.mmd`/`.pdf`.

**To check:** references [21]–[26] (Self-RAG, Adaptive-RAG, Docling, HLDC, Augraphy, Doyle 1979) were appended with authors and IDs written from memory. Verify them, and renumber by first appearance if wanted.

## 3. Project skeleton (done; stubs only, no logic)

**Size:** 443 files were created. `README.md` (repository layout section) and `.gitignore` were modified.

**Python package:** [src/vakeel_sahayak/](src/vakeel_sahayak/).
- **Agents:** the six agents.
- **Tools:** all 39 plan-named tools, each a function plus a `<NAME>_SPEC`.
- **Stores and contracts:** the 10 stores, and 12 evidence-contract YAMLs.
- **Rights Radar:** an engine plus 7 rules.
- **Other modules:** ingestion, orchestration (with ablation switches), truth maintenance, batch, privacy, model clients, export, FastAPI API, pipelines, fine-tuning, test-set construction, eval.
- **Stubs:** bodies are `raise NotImplementedError`. Schemas, enums and YAML files are real.
- **Import check:** all 306 modules import cleanly in `.venv`.

**Configs and scripts:**
- [configs/](configs/): YAML for models, stores, budgets, thresholds, tools and rights rules; `bail_sections.yaml` has 5 extra rows marked TODO for verification.
- [scripts/ada/](scripts/ada/): the session shard runner and the QLoRA sbatch job.
- `data/`, `Makefile`, `.env.example`.

**Frontend:** [frontend/](frontend/) is a Next.js stub with:
- routes `/`, `/cases`, `/case/[id]`, `/desk`, `/library`, `/about`;
- landing scenes 0–6, the six agent animations and the workspace tabs;
- [styles/tokens.css](frontend/styles/tokens.css) with the palette.

**Guide for coding agents:** [docs/architecture/skeleton.md](docs/architecture/skeleton.md) maps each plan section to its module and sets the conventions to follow.

**Interpretations to review:**
- 9 of the 12 factor IDs were chosen by the agent, for example `undertrial_period`.
- Contract slots beyond the parity example were inferred from plan Appendix B.

## 4. Test suite: complete (written, not run)

The suite is now written for every layer in the brief. **No test has been run**, not even `--collect-only`: the code is all stubs, and
the earlier instruction stands (run tests only after the code is implemented). Details, layout, markers and the plan-section map are in
[tests/README.md](tests/README.md).

**What exists** (about 2,130 Python test functions in 173 files, plus the frontend tests):
- **Unit tests** (`tests/unit/`, 1,834 functions in 150 files, 27 folders): schemas, record, contracts, config, tools and tool registry, intake/law/case
  tools, rights, ingestion, stores, orchestration, truth maintenance, batch, privacy, agents (all 6), models, pipelines, eval. The four
  folders that were empty are now filled:
  - `api/`: app and dependencies, and the routers for cases, upload (files and dictation), chat, SSE events, gates, export (403 before
    Gate 2), desk and library, with FastAPI `TestClient`;
  - `export/`: the application sections, List of Dates from the timeline, the DOCX application (needs python-docx), the annexure index,
    the "AI-generated draft" banner, the hearing card, the gated exporter;
  - `pipelines/concordance/`: IPC to BNS edge types (same/split/merged/reworded/new), IPC 420 to BNS 318(4), the ten-row bail table
    (CrPC 436/436A/437/438/439 to BNSS 478/479/480/482/483);
  - `pipelines/store_builders/`: one module per builder (statutes, concordance, reasoning, arguments, objections, citations, similar) plus
    `build_all`: part-aware chunking, metadata fields, reasoning-only authorities, leakage exclusions.
  - The last gaps are now closed (370 functions in 27 new files, all with fakes and no network):
    - `finetune/` (77): span-check filtering keeps only all-pass orders, noise augmentation (30% of pairs get an OCR-of-degraded-render input,
      target unchanged), the QLoRA config (r=16, 2 epochs, FP16, one GPU, the only sbatch job), the SFT dataset with test and same-FIR
      orders excluded, resumable teacher shards, and the teacher-pilot decision rule (more verified pairs per day wins; the API only if
      terms, cost and pinned-and-cached conditions all hold) with the family rule;
    - `testsets/` (108): T1-T9 sizes and composition (200 with at least 60 BNS-era and an 8-gram leakage check; T2 companions and renderers K1-K6;
      T3 three change types plus 60 no-op controls; T4 day 59/60/61, one-third vs one-half, 7 vs 10 years, first-time vs repeat; T5 deadlines
      planted in the next 7 days; T6-T9), construction-known answers and deterministic seeds;
    - `eval/` additions (82): baselines B0-B4 and what each isolates, ablations A1-A10 as runs (switches reach the Full system, per-case saving,
      resume, sharding), features F1-F8 (`score` on hand-checked run directories), ingestion pipelines P1-P6 and Munshi (backend call counts,
      per-kind breakdown), runners (resumable shards, 3 runs vs 1 run, only QLoRA is a batch job);
    - tool modules `tools_case/` (21), `tools_caselaw/` (38), `tools_advocacy/` (10), `tools_drafting/` (34): argument validation, store
      routing, reasoning-only authorities, the good-law check blocking overruled citations, `render_citation` from metadata only, `export`
      gated and never bulk.
- **Integration tests** (`tests/integration/`, 112 new functions in 8 files): Munshi to Peshkar on the 14-page bundle; Sutradhar with fake
  stores (plan, assess, relax, budget stop, missing slots as open issues); Vakeel and Abhiyojak sparring (context isolation, ungrounded
  objections discarded, UNANSWERED to NEEDS_REVIEW); the change-set flow (diff, re-approval, only affected grounds redrafted,
  no-op control); the event log (resume, trace, dependencies); gate interrupts with export blocked before Gate 2; the API end to end
  with SSE; the Pairokar queue resuming after an interrupted shard with the shared cache.
- **System tests** (`tests/system/`, 176 functions in 14 files, about 290 cases once parametrised; one file per scenario):
  - user flows 1-7 of plan §13.6: `test_flow1_messy_bundle.py` (22), `test_flow2_quick_chat.py` (15), `test_flow3_brief_spar_export.py` (19),
    `test_flow4_case_moves_on.py` (10), `test_flow5_dictated_hindi.py` (10), `test_flow6_batch_desk.py` (13, the 120-file desk is marked
    `slow`), `test_flow7_library.py` (15);
  - the T7 safety suite: `test_t7_planted_instructions.py` (11; digital, scanned, Hindi and handwritten pages, and a fooled planner),
    `test_t7_pressure.py` (10), `test_t7_bulk_export.py` (9), `test_t7_prediction_lay_advice.py` (9), `test_t7_name_leaks.py` (12),
    `test_t7_sensitive_matters.py` (11), `test_t7_draft_label.py` (10);
  - `_helpers.py` (the `Scenario` driver) and `_scripts.py` (planted instructions, pressure prompts, planted names, the fooled planner,
    the by-factor drafter). The earlier consolidated `test_user_flows.py` (22) and `test_safety_t7.py` (25) were split into these files, with
    every case carried over; copies are not kept in the repo.
  - Six real-model variants carry `@pytest.mark.models` (most also `gpu`) and are skipped by default.
- **Shared code:** `tests/conftest.py`, `tests/fakes/`, `tests/fixtures/` (case-0007, statutes, concordance, paragraphs, PDF generator).
- **Frontend:** Vitest (`frontend/tests/unit/`, 9 files: tokens, status map, stage rail, reduced motion, api client, SSE hook, brand, fixtures)
  and Playwright (`frontend/e2e/`, 11 specs, 52 tests: landing scenes 0-6, reduced-motion storyboard, the three workspace panes, Gate 1 and
  Gate 2, flows 1, 2, 3, 4, 5 and 6, library). `flow4_case_moves_on.spec.ts` (new charge-sheet order, changed fields highlighted, re-approve,
  only G2 redrafted and highlighted; plus a duplicate-document control) and `flow5_dictated_case.spec.ts` (Hindi dictation through the mic, read-back,
  USER_STATED facts, "per counsel, not on record") are new. Hooks are in `e2e/testids.ts`, the "change" and "dictation" scenarios in
  `e2e/mockBackend.ts`, and nine new JSON fixtures in `e2e/fixtures/` (guarded by `tests/unit/e2eFixtures.test.ts`).
- **Configs:** `pyproject.toml` has the pytest config (testpaths, markers unit/integration/system/gpu/models/slow, default
  `-m "not gpu and not models"`); `Makefile` has `test-unit`, `test-integration`, `test-system`, `test-frontend` (and `test-e2e`,
  `test-models`, `test-collect`).

**Static checks done** (nothing executed): `py_compile` and `ruff check --select F,E9` over all of `tests/` (the final gap-filling pass: its 27 new
Python files plus their helpers) are clean (17 unused imports
in 15 earlier files were removed; no file was found truncated); imported names were resolved against the source; `tsc --noEmit` on the frontend is clean.

**Expect all of it to fail until the modules are implemented.** Assumptions the tests make where the plan is silent are marked
`# ASSUMPTION:` (about 270; `grep -rn ASSUMPTION tests frontend/tests frontend/e2e`); things the skeleton lacks are marked `# SKELETON-GAP:`:
no API route lets counsel resolve a Gate 2 checklist item, and nothing serves the hearing card's "conditions courts impose". The gap-filling pass
added more: no function applies the teacher-pilot decision rule or the family rule (`choose_teacher`, `verified_pairs_per_day`,
`assert_family_rule` are the intended names in `finetune/teacher_dossiers.py`); no `ChangeSet` REST route (flow 4 reads it from SSE events) and no
route that confirms a dictation read-back (flow 5 uses the chat route); `check_claim(claim, refs)` has no case id, so fact support and the
transfer flag cannot be tested on the tool alone; B1 and B2 have no combined index or whole-order text store; the per-kind breakdown,
escalation-rate and questions-asked metrics, B3's best-variant choice and B4's RRF have no function yet; no TTS client for T8.

**Known gaps** (outside the brief): no unit tests yet for `tools/dossier.py` and `tools/interaction.py` (exercised through the fake toolbox, the
agent tests and `tools_intake/test_privacy_ask_user.py`); the Playwright specs need the real UI hooks from `e2e/testids.ts` before they can pass.

**Side effects of the earlier test agents to review or clean up:**
- The skeleton files `src/vakeel_sahayak/batch/queue.py` and `src/vakeel_sahayak/orchestration/switches.py` were edited after the skeleton was finished. Review those edits.
- `pyproject.toml` and `Makefile` were edited (pytest config, markers, test targets).
- pytest, pytest-asyncio and hypothesis were installed in `.venv`.
- `npm install` was run in `frontend/`, creating `node_modules/`, `package-lock.json` and `tsconfig.tsbuildinfo`.
- A stray 25 MB `pymupdf-*.whl` was downloaded into the repo root. Delete it, or add it to `.gitignore`.
- It is not confirmed whether any tests were executed before the stop.

## 5. Coding phases

Each phase works like this:
1. A coding agent implements the phase from plan.md alone, without seeing `tests/`.
2. Only that phase's tests are run.
3. A reconcile agent fixes the code by default. It changes a test only where the test contradicts the plan, and marks each such change `# RECONCILED`.

| Phase | Scope | Status |
|---|---|---|
| 1. Foundations | config, schemas, event log and case record, contracts, tool registry with gated export, Rights Radar (7 rules), date_calc / map_section / transfer_check / statute tools, privacy (pseudonymisation, boundary, injection guard, leak check, sensitive matters), concordance pipeline | **Done.** Phase 1 unit tests: 1,060 passed, 4 skipped (needs langgraph), 0 failed. No tests were changed. |
| 2. Stores and data pipelines | order splitter, section extraction, factor tagger, splits and leakage, citation graph and good-law check, rule-based gold labels G1–G7, the 8 remaining stores (SQLite FTS5 + optional LanceDB/BGE-M3), store builders, store tools | **Code written; reconcile unfinished.** The first test run gave 482 passed, 103 failed. The reconcile agent stopped partway when the usage limit hit, so the code is half-fixed. Phase 1 still passes (1,060). To do: resume the reconcile, and fix `assign_splits`, which is slow (17–34 s per test). |
| 3. Munshi ingestion | page signals, routing ladder, bundles, gaps, Hindi, voice | To do |
| 4. Agents and orchestration | model clients, Peshkar, Sutradhar, Vakeel, Abhiyojak, truth maintenance, Pairokar, LangGraph gates | To do |
| 5. API and export | FastAPI routers and SSE; DOCX application and hearing card | To do |
| 6. Frontend | design system, landing animations, workspace, desk, library | To do |
| 7. Evaluation | test-set construction T1–T9, baselines, ablations, metrics, stats, Ada scripts | To do |

**Phase 1 choices to confirm in week 0:**
- A bare "10 years" maximum is treated as `CHECK`, the same as "may extend to ten years".
- Missing communication of the grounds of arrest is always `FLAG`; the retroactivity question is noted in the detail text.
- IPC 420 → BNS 318(4) is treated as `SAME`, and 436A → 479 as `REWORDED`.
- The Antil category D list of economic-offence sections is an assumption.
- The sexual-offence decline list is deliberately broad.
- The IPC2BNS-Verify file format is guessed.

**Known outside Phase 1:** `tests/unit/tools_drafting/test_export_and_approval_tools.py` expects `unresolved == ["antecedents"]`, but the code gives `["UNSUPPORTED:antecedents"]`. This is to be settled in Phase 5.

## 6. Memory notes saved (for future sessions)

- Interface decisions (v5 frontend, agent names, workspace layout).
- You prefer maximal scope: cut sample sizes, never features.
- Don't run tests while modules are still stubs.
