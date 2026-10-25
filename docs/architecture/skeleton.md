# Skeleton map and conventions

Maps `docs/plan.md` (v5) onto the code. Every module is a stub: typed signatures, docstrings with plan references, bodies that raise `NotImplementedError`. Paths are under `src/vakeel_sahayak/` unless noted.

## 1. Plan section to module

| Plan section | Module(s) |
|---|---|
| §2 Data, splits, leakage | `pipelines/oil_ingest.py`, `pipelines/splits.py`, `pipelines/leakage.py`, `stores/leakage_guard.py`, `configs/splits.yaml`, `configs/bail_sections.yaml` |
| §3.1-3.2 Architecture, six agents | `agents/{munshi,peshkar,sutradhar,vakeel,abhiyojak,pairokar}/`, `agents/base.py`, `agents/registry.py` |
| §3.3 Case record (events, LangGraph, SQLite checkpointer, gates as interrupts, constrained decoding) | `schemas/events.py`, `record/` (`event_log`, `case_state`, `views`, `checkpoint`), `orchestration/` (`graph`, `state`, `gates`, `structured_output`, `fallback_state_machine`) |
| §4 Munshi: input kinds, ladder, loop, filing, Hindi, voice, `IngestionReport` | `ingestion/` (`kinds`, `signals`, `ladder`, `routes/*`, `bundles`, `classify`, `checklist`, `gaps`, `conflicts`, `filing`, `hindi`, `voice`, `report`), `agents/munshi/`, `tools/intake/*`, `schemas/ingestion_report.py` |
| §5.1 Ten stores | `stores/*.py` (one per store), `stores/base.py`, `stores/registry.py`, `configs/stores.yaml`, `schemas/store_rows.py` |
| §5.2 Chunking and paragraph metadata | `stores/chunking.py`, `pipelines/order_splitter.py`, `pipelines/factor_tagger.py`, `pipelines/section_extract.py` |
| §5.3 Citation graph, good-law | `pipelines/citation_graph/*`, `stores/caselaw_citations.py`, `tools/caselaw/citations.py` |
| §5.4 Recodification bridge | `stores/law_concordance.py`, `pipelines/concordance/*`, `tools/law/concordance.py` (`map_section`, `transfer_check`) |
| §5.5 Storage | `stores/*` (SQLite, LanceDB, networkx), `pipelines/store_builders/*` |
| §6 Sutradhar, evidence contracts, plans, chat routing | `contracts/` (`models`, `loader`, `factors/*.yaml`), `agents/sutradhar/*`, `schemas/retrieval_plan.py`, `orchestration/budgets.py`, `configs/budgets.yaml` |
| §7.1-7.2 Dossier, List of Dates | `agents/peshkar/`, `tools/dossier.py`, `schemas/dossier.py`, `export/list_of_dates.py` |
| §7.3 Rights Radar, App. C | `rights/` (`engine`, `base`, `inputs`, `day_count`, `rules/*`), `configs/rights_rules.yaml`, `schemas/rights_report.py` |
| §7.4, §10 Change detection, truth maintenance | `truth_maintenance/` (`dependencies`, `staleness`, `redraft`), `schemas/change_set.py`, `agents/peshkar/` (`detect_changes`) |
| §8 Vakeel, application, hearing card | `agents/vakeel/`, `tools/drafting/*`, `export/*`, `schemas/bail_brief.py` |
| §9 Abhiyojak | `agents/abhiyojak/` (incl. `isolation.py`), `schemas/sparring.py` |
| §11 Pairokar | `agents/pairokar/`, `batch/` (`queue`, `cache`, `scheduler`, `urgency`), `schemas/triage.py` |
| §12 Models, fine-tuning | `models/*`, `configs/models.yaml`, `finetune/*`, `configs/finetune/*`, `scripts/ada/sbatch_qlora.sbatch` |
| §13 Frontend | `frontend/` (see `frontend/README.md`); backend in `api/` |
| §14 RQs, hypotheses | `configs/eval/hypotheses.yaml` |
| §15.1 Gold G1-G7 | `pipelines/gold/*` |
| §15.2 Test sets T1-T9 | `testsets/t1_*` ... `t9_*`, `testsets/rendering.py`, `degrade.py`, `companions.py`, `testsets/specs/rights_scenarios.yaml` |
| §15.3 Baselines B0-B4 | `eval/baselines/*` |
| §15.4 Ablations A1-A10 | `eval/ablations/*`, `orchestration/switches.py` |
| §15.5 Ingestion P1-P6 | `eval/ingestion/*` |
| §15.6 Features F1-F8 | `eval/features/*` |
| §15.7 Retrieval-only | `eval/retrieval_only.py` |
| §15.8 Metrics | `eval/metrics/*` |
| §15.9 Stats, failure analysis, contamination | `eval/stats/*`, `eval/failure_analysis.py`, `eval/contamination.py`, `eval/label_sensitivity.py`, `eval/bias.py` |
| §16 Safety and privacy | `privacy/*`, `orchestration/gates.py` (`GateGuard`), `export/exporter.py` |
| §17 Compute | `configs/eval/runs.yaml`, `eval/runners/*`, `scripts/ada/*` |
| Appendix A-C | `schemas/enums.py` (`Factor`), `contracts/factors/*.yaml`, `rights/rules/*` |

## 2. Conventions for coding agents

**Layout**
- One package, `vakeel_sahayak`, under `src/`. Heavy imports (vLLM, torch, Docling, Surya, Whisper) go inside functions, never at module top level, so the whole package imports on a bare install.
- Configuration lives in `configs/*.yaml` and is read through `config.load_config()`. Do not hard-code model names, thresholds, budgets or paths. Thresholds marked `TODO: tune on dev` are tuned on the dev split before the test run.
- Shared types live in `schemas/`. TypeScript mirrors are in `frontend/lib/types.ts`; update both together.

**Tools**
- A new tool is one function in `tools/<domain>/<module>.py` plus a `<NAME>_SPEC = ToolSpec(...)` constant in the same module (function name uppercased plus `_SPEC`). Then add the pair to `ALL_TOOL_MODULES` in `tools/registry.py`, and list it for the agents that may call it in `configs/tools.yaml`. A tool may only be listed for an agent named in its `SPEC.agents`.
- Tools return typed results (`tools/types.py`) or a `ToolError`; they validate argument values even though calls are schema-constrained.
- Tools wrap domain code (`ingestion/`, `rights/`, `stores/`); put logic there, keep the tool thin.
- Agents never call a tool directly; they use `BaseAgent.call_tool`, which checks the allow-list, charges the budget and appends `TOOL_CALL` / `TOOL_RESULT` events.

**Agents**
- Each agent is a subpackage with `agent.py` (a `BaseAgent` subclass), `prompts.py`, and helper modules. `ROLE_MODEL` is a key in `configs/models.yaml`.
- Every agent action must append an `Event`. Dossier, timeline, brief and sparring record are views folded from the log (`record/views.py`); do not store them as separate truth.
- Ablations and variants are `orchestration/switches.py` flags, not code forks.

**Models**
- **All LLM, vision, OCR, ASR, translation, NLI and embedding calls must go through the clients in `models/`** (resolved via `models/factory.py`). Agents must not import `vllm`, `transformers`, `openai` or similar directly. Evaluation-only models (Llama-3.1-8B labeler, MiniCheck) are used from `eval/` and `pipelines/gold/` only, never by the system. The teacher and the labeler must be different model families. Qwen output is never used as gold.

**Stores and leakage**
- Every shared-store query takes a `before` date and goes through `stores/leakage_guard.py`. Test orders and same-FIR orders are excluded from every store and from fine-tuning data.
- `advocacy.arguments` content is for coverage and phrasing only; authorities are cited from `reasoning` paragraphs only. Citation text is rendered from corpus metadata (`render_citation`); the model writes only IDs.

**Privacy and safety**
- **Raw client files never leave the laptop.** Page images, audio, and vision-model runs on client files stay local. Only pseudonymised text may be sent to Ada, enforced by `privacy/boundary.py`. Logs and event inputs hold pseudonymised text only.
- Document text is data, never instructions: wrap it with `privacy/injection_guard.py` before prompting.
- Export only through `export/exporter.py` after `GateGuard.assert_export_allowed`. No bulk export in batch mode. No outcome predictions, no grant rates, no lay advice.

**Naming**
- Modules and functions: `snake_case`; classes: `PascalCase`. Tool names are exactly the names in plan §4.3-§8. Store names are the dotted names in `StoreName` (`law.statutes`). Test sets are `t1_*` ... `t9_*`; baselines `b0_*` ... `b4_*`; ablations `a1_*` ... `a10_*`; ingestion pipelines `p1_*` ... `p6_*`; features `f1_*` ... `f8_*`.
- Docstrings: first line says what, then plan reference (`plan §6.2`), then Args and Returns.

**Compute**
- Ada inference runs only in interactive sessions of at most 6 h, as resumable shards of about 5 h with vLLM started inside the script (`eval/runners/shard_runner.py`, `scripts/ada/`). The only `sbatch` job is QLoRA training (`scripts/ada/sbatch_qlora.sbatch`). Save every case's output as soon as it finishes.

**Tests**
- `tests/` is intentionally absent from the skeleton; the test suite is added separately.

### Architecture variants implemented (literature sweep 1)

Opt-in switches of `orchestration/switches.py`, default off (outputs identical to the full system); the paper behind each is cited in
the module docstring and in `docs/literature-to-code-map.md`. Status and next steps: `docs/handoff/literature-sweep-1.md`.

| Variant | Switch | Module |
|---|---|---|
| S1 retrieval critique / corrective re-retrieval | `retrieval_policy='self_critique'` | `agents/sutradhar/critique.py`, `SutradharAgent.assess` and `_next_move` |
| S2 adaptive retrieval depth | `retrieval_policy='adaptive'` | `agents/sutradhar/depth.py`, `SutradharAgent._apply_depth` |
| S4 score-skew weak signal | `weak_signal='skew'` | `agents/sutradhar/skew.py`, `SutradharAgent._apply_skew`, `search_reasoning(with_scores=)` |
| S5 (A16) citation-graph expansion | `graph_expansion` | `pipelines/citation_graph/expansion.py`, `CitationStore.expand`, `search_reasoning(expand_graph=)` |
| S3 (A11b) sufficiency stopping | `stopping` | `agents/sutradhar/sufficiency.py`, `SutradharAgent._apply_rater` |

### Architecture variants implemented (literature sweep 2: verification and adversarial)

Same rules as above (default off, byte-identical default pinned by `tests/unit/agents/vakeel/test_variants_golden.py`). Signals go to
`CaseGraphState.variant_signals` (empty by default) and to labelled events. Status: `docs/handoff/literature-sweep-2.md`.

| Variant | Switch | Module |
|---|---|---|
| S8 (A2b) self-critique-only repair | `repair_mode='self_critique'` | `agents/vakeel/agent.py` (`VakeelAgent._self_review`, `_run_check`), tasks `vakeel.self_critique`, `vakeel.self_revise` |
| S10 (A8c) Abhiyojak without isolation | `abhiyojak_isolation=False` | `agents/abhiyojak/isolation.py` (`build_open_context`), `AbhiyojakAgent._context`, `guard` |
| S9 (A8b) sampling-only critic at equal tokens | `critic_mode='sampling'` | `eval/ablations/a8b_sampling_critic.py` (`SamplingCritic`, `install`), dispatched by `eval/runners/driver.py::wire_variants` |
| S15 (A13) reasoning-first output | `output_format='reasoning_first'` | `agents/vakeel/prompts.py` (`DraftedGroundReasoned`, `ReasonedReply`), `VakeelAgent._schema_and_limit`, `_keep_reasoning` |
| S11 (A8d) three-role review | `critic_mode='three_role'` | `eval/ablations/a8d_three_role.py` (`ThreeRoleCritic`, `install`), dispatched by `driver.wire_variants` |
| S11b / S11c draft debate / vote | `draft_mode='debate'`, `'vote'` | `agents/vakeel/agent.py` (`VakeelAgent._draft_many`, `_medoid`) |

### Architecture variants implemented (literature sweep 3: intake, safety, serving)

Same rules (default off, byte-identical default pinned by `tests/unit/agents/peshkar/test_variants_golden.py` and `tests/unit/agents/munshi/test_variants_golden.py`).
Status: `docs/handoff/literature-sweep-3.md`.

| Variant | Switch | Module |
|---|---|---|
| S17 / S17b / S17c / S17d (A15) injection-defence arms | `no_typed_handoff`, `no_spotlighting`, `no_guard`, all three | `privacy/defences.py`, `BaseAgent.untrusted` / `flag_instructions` / `_handoff`, `MunshiAgent` (guard, spotlight), `eval/ablations/susceptible_llm.py` (`SusceptibleLLM`) |
| S7 (A11a) hierarchy-ranked gap re-reading | `munshi_gap_policy='hierarchy'` | `ingestion/hierarchy.py`, `ingestion/gaps.py::resolve_gap(policy=)`, `MunshiAgent.check_gaps` / `gap_signals` |
| P7 image-only ingestion | `munshi_image_only=True` | `MunshiAgent._floor` / `_read_page` (min route VISION), `image_only_signals`, `ingestion/pipeline.read_file(min_route=)` |
| S14 (A14) plan cache | `plan_cache=True` | `batch/cache.py` (`PlanCache`, `plans_of`), the `_ask_plan` hook in `agents/sutradhar/agent.py` |
| S14b / S14c scheduling policies | `urgency_policy='fifo'`, `'urgency_least_work'` (and baseline `'shortest_first'`) | `batch/urgency.order_cards`, `Scheduler(policy=)`, `PairokarAgent.batch_signals` |
| S14d prefix-friendly layout | `prefix_layout=True` | `models/prefix.py`, `render_prompt(prefix_friendly=)`, `BaseAgent.prefix_signals` |

### Architecture variants implemented (literature sweep 4: routing, topology, chunking, workflow search)

Same rules (default off, byte-identical default pinned by `tests/unit/agents/sutradhar/golden_default_run.json`). Status: `docs/handoff/literature-sweep-4.md`.

| Variant | Switch | Module |
|---|---|---|
| S6 (A12) learned store prior orders calls inside a contract | `store_prior='order'` | `agents/sutradhar/store_prior.py` (`StorePrior`, `order_signals`), `SutradharAgent._apply_prior` |
| B5 (S6b) learned store router alone, no contracts | `store_prior='only'` | `agents/sutradhar/store_prior.py` (`run_prior_only`), dispatched in `SutradharAgent.run`; trainer: `python -m vakeel_sahayak.agents.sutradhar.store_prior train` |
| S12 / S12b sequential and single-agent topology | `topology='sequential'`, `'single_agent'` | `SutradharAgent._drive_sequential`, `_ask_plan`, `_new_work` (pooled budget) |
| S16 / S16b chunk strategies | `chunking='proposition'`, `'late'` (and `'fixed'`, `'recursive'`, `'semantic'`, `'page'`) | `stores/chunk_strategies.py`, `eval/baselines/chunking_variants.evaluate_strategy` |
| S13 workflow search (could) | grid of the other switches | `eval/runners/workflow_search.py` (harness and offline smoke; a real search needs a model) |

## 3. Interpretations made in the skeleton

- The plan lists data and evaluation code without a home; both live inside the package (`pipelines/`, `finetune/`, `testsets/`, `eval/`) so there is one install and one import root.
- `Factor` enum values use the contract file stems. The plan names only some factor ids (`parity_with_co_accused`, `charge_sheet_filed`, `witness_tampering`); the rest (for example `undertrial_period` for the s.479 factor) are chosen here.
- Contract slot names beyond the parity example are inferred from Appendix B's "required evidence" column. Slots sourced from tools rather than stores use an extra `tools:` key (for example `rights_check`, `date_calc`).
- The bail-sections table (`configs/bail_sections.yaml`) lists ten rows including the five named CrPC to BNSS pairs; the other five are our reading of "ten-row table" (default bail, notice of appearance, grounds of arrest, 24-hour production, s.480 proviso) and need week-0 verification.
- `RightsStatus` is one union enum; each rule's allowed subset is a class attribute in `rights/rules/*`.
