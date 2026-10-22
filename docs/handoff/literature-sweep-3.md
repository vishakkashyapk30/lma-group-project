# Literature sweep 3: intake, safety and serving variants (handoff)

Variant ids follow `docs/evaluation-plan.md` section 3.3. Goldens for default-off equivalence: `tests/unit/agents/peshkar/golden_default_run.json` (offline Peshkar run over a
planted shelf: dossier, dates, events, every prompt), `tests/unit/agents/munshi/golden_default_run.json` (14-page bundle: report, events, tool calls); helpers
`_variants_helpers.py` in each folder.

| Variant | Switch | Status |
|---|---|---|
| S17 / S17b / S17c / S17d (A15) injection defences | `no_typed_handoff`, `no_spotlighting`, `no_guard` | DONE |
| S7 (A11a) hierarchy re-reading | `munshi_gap_policy='hierarchy'` | DONE |
| P7 image-only ingestion | `munshi_image_only=True` | DONE |
| S14 / S14b / S14c / S14d serving | `plan_cache`, `urgency_policy`, `prefix_layout` | DONE |

## S17 (done)
Files: `privacy/defences.py` (new), `agents/base.py` (`defences`, `untrusted` now an instance method, `flag_instructions`, `_handoff`, `injection_signals`, `_with_injection`; `ask` calls `_handoff`),
`agents/peshkar/agent.py` (`run` adds `variant_signals['injection']` only when an arm runs), `agents/munshi/agent.py` + `decisions.py` (`LlmAdvisor(spotlight=)`), `ingestion/pipeline.py`
(`page_read`, `guard`/`min_route` on `read_page`/`read_file`, `PageRead.missed_lines`), `eval/ablations/susceptible_llm.py` (new, `SusceptibleLLM`), `switches.py`.
Tests: `tests/unit/privacy/test_defences.py`, `tests/unit/agents/peshkar/test_variants_golden.py` + `test_variants_injection.py`, `tests/unit/agents/munshi/test_variants_golden.py` + `test_variants_injection.py`;
reconciled `tests/unit/orchestration/test_switches.py` (`# RECONCILED`).
Signature change: `BaseAgent.untrusted` is no longer a staticmethod (it reads the agent's switches); every caller already used `self.untrusted`.
Notes: the guard arm changes Munshi's extraction view (instruction-like lines are dropped when on); the susceptible-model stand-in follows an instruction by channel, so the guard arm shows no success change there. The OCR-vs-text-layer cross-check is not built.

## S7 (done)
Files: `ingestion/hierarchy.py` (new), `ingestion/gaps.py` (`resolve_gap(policy=, signals=)`, one record per item), `agents/munshi/agent.py` (`check_gaps` passes policy and skips an item an earlier re-read filed, under hierarchy only;
`gap_signals`; `_Run.gap_records`; `run` adds `variant_signals['munshi']['gaps']` and `check_gaps` logs a `gap_policy` event only under hierarchy), `switches.py`.
Tests: `tests/unit/ingestion/test_hierarchy.py` (19), `tests/unit/agents/munshi/test_variants_gap_policy.py` (7); reconciled `test_switches.py` (S12 is now the unbuilt id the dispatch test uses).
Notes: weights and `MIN_SCORE` are untuned (TODO on dev bundles). `oracle_regret` is a lower bound. The file to compare is built in the test (four weak scanned pages, arrest and remand on the last).

## P7 (done)
Files: `agents/munshi/agent.py` (`_floor`, `_read_page`, `survey` event, `image_only_signals`, `run` signals), `ingestion/pipeline.py` (`read_file(min_route=)`), `switches.py`.
Tests: `tests/unit/agents/munshi/test_variants_image_only.py` (7); reconciled `test_switches.py`. The ladder is unchanged: `min_route=VISION` already meant [vision, ask counsel].

## S14 family (done)
Files: `batch/cache.py` (`RetrievalCache.peek`, `PlanCache`, `plans_of`), `agents/sutradhar/agent.py` (the single plan-cache hook: `_ask_plan` now checks the cache, the old body is `_ask_plan_model`; `_plan_cache`),
`batch/urgency.py` (`order_cards`, `has_deadline`, `POLICIES`), `batch/scheduler.py` (`Scheduler(policy=, sizes=)`, `_order`, `signals`, `completed`; default path unchanged), `agents/pairokar/agent.py` (`policy` passed, `batch_signals`, `_serving_variant`),
`models/prefix.py` (new), `models/prompting.py` (`prefix_friendly`), `agents/base.py` (`build_prompt`, `ask` meter, `prefix_signals`), `eval/runners/driver.py` (`collect_sweep3_signals`), `switches.py`
(new field `prefix_layout` and variant id `S14d`; `urgency_policy` accepts `'shortest_first'`).
Tests: `tests/unit/batch/test_plan_cache.py`, `tests/unit/agents/sutradhar/test_variants_plan_cache.py`, `tests/unit/agents/pairokar/test_variants_golden.py` + `test_variants_scheduling.py` (+ `_variants_helpers.py`, `golden_default_run.json`),
`tests/unit/models/test_prefix.py`; reconciled `test_switches.py`, `test_registries.py` (`# RECONCILED`: new field `prefix_layout`, implemented set).
Measured on case-0007, offline: the second case with the same signature skips all 8 planning calls, tokens 30,633 -> 12,836, evidence packs byte-identical to the no-cache run.
Notes: `prefix_layout` and `S14d` are not in the plan (it names prefix caching as a server flag); `store_version` has no producer yet: a batch must set it (`plans_of(cache, store_version=...)`) when a store is rebuilt.
Attained service for `urgency_least_work` is planned hours times attempts. Untested against the real models: G1 recall with the cache on.

## Test results
Targeted runs per variant: all green. Final regression command: 3,351 passed, 16 skipped (after reconciling `tests/unit/models/test_interfaces.py`, which lists `models.prefix` as a helper, the one failure of the first run). `ruff check src`: clean.
Not done: the OCR-versus-text-layer cross-check of plan S17(c); datamarking and encoding forms of spotlighting; S15b, runs.yaml jobs for the new variants (configs/eval is outside this sweep).
