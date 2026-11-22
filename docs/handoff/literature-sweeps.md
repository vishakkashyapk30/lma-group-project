# Literature sweeps 1 to 4: what each sweep built, measured and decided

The four sweeps (October to November 2026) added the S variants. Each section below is the note of one sweep, unchanged except for its heading level. Which paper each variant comes from, with its switch, module and test, is in `../literature-to-code-map.md`.

---

## Sweep 1: retrieval and orchestration variants (handoff)

Variant ids follow `docs/evaluation-plan.md` section 3.3 (S1-S5 are this sweep; the literature review uses its own ids S2/R1/R2,
see `docs/literature-to-code-map.md`). Priority order set by the lead: S3, S1, S2, S5 (S4 last, optional).

| Variant | Switch | Status |
|---|---|---|
| S3 sufficiency stopping | `stopping` (`rules`/`rules_llm`/`llm`; variants S3, S3b, alias A11b) | DONE |
| S1 retrieval critique | `retrieval_policy='self_critique'` | DONE (see below) |
| S2 adaptive depth | `retrieval_policy='adaptive'` | DONE (see below) |
| S5 graph expansion | `graph_expansion` | DONE (see below) |
| S4 score-skew weak signal | `weak_signal='skew'` | DONE (see below) |

Golden for default-off equivalence: `tests/unit/agents/sutradhar/golden_default_run.json` (captured before any change; digests of packs,
plans, events as a multiset, budget). Helper: `tests/unit/agents/sutradhar/_variants_helpers.py`.

### S3 (done)
Files: `src/vakeel_sahayak/orchestration/switches.py` (field, `ARCHITECTURE`, `VARIANT_ALIASES`, validator), `agents/sutradhar/sufficiency.py`
(new), `prompts.py` (`TASK_RATE`, `SufficiencyJudgment`), `offline.py` (`rate_offline`), `work.py` (`FactorWork.stopping`), `agent.py`
(`_apply_rater`, `_store_calls_spent`, `retrieval_signals`, `_finish`), `orchestration/state.py` (`retrieval_signals` field, empty by default).
Tests: `tests/unit/agents/sutradhar/test_variants_stopping.py` (20 pass); reconciled `tests/unit/orchestration/test_switches.py`,
`tests/unit/eval/test_registries.py` (`# RECONCILED`). Docs: `docs/literature-to-code-map.md`, `docs/architecture/skeleton.md`.

### S1 (done)
Files: `agents/sutradhar/critique.py` (new: `critique_assess`, `choose_action`, `critique_data` offline critic, `reorder`, `CritiqueTrace`, `signals`), `prompts.py`
(`TASK_CRITIQUE`, `PassageVerdict`, `SlotCritique`), `offline.py` (`critique_offline`), `work.py` (`SlotWork.verdicts/discarded/critic_action/critic_used`,
`FactorWork.critique`), `agent.py` (`assess`, `_next_move`, `_variant_signals`, which now serves S3 and S1), `switches.py` (S1 in `IMPLEMENTED_VARIANTS`).
Tests: `tests/unit/agents/sutradhar/test_variants_critique.py` (24 pass); reconciled `tests/unit/orchestration/test_switches.py` (`# RECONCILED`).
Signals: `retrieval_signals[factor]['critique']` and `critique`/`critic_action`/`retrieval_signals` events. A slot with nothing retrieved is MISSING with no critic call.

### S2 (done)
Files: `agents/sutradhar/depth.py` (new: `classify` rules none/single/multi, `features_of`, `signals`), `work.py` (`SlotWork.skipped`, `FactorWork.depth/round_cap`),
`agent.py` (`_new_work(adaptive=)`, `_apply_depth`, round cap in `replan`, stopped label `depth_cap`, `_reretrieve` uses full depth), `switches.py`.
Tests: `tests/unit/agents/sutradhar/test_variants_depth.py` (21 pass). Note: case-0007 is BNS-era, so every factor is multi there (loop unchanged);
single/none behaviour is tested by reading the case as IPC-era (monkeypatching `depth.BNS_CODES`) and by setting the Rights Radar undertrial_limit to ELIGIBLE.

### S5 (done)
Files: `pipelines/citation_graph/expansion.py` (new: PPR, `expand_documents`, `merge_ranked`, `ExpandedParagraph`), `stores/caselaw_citations.py` (`expand`, `graph`),
`stores/caselaw_reasoning.py` (`search_docs`), `stores/paragraph_store.py` (`_search_docs`), `stores/hybrid.py` (`key_prefixes` on `search`), `tools/caselaw/reasoning.py`
(`expand_graph=False` argument, `expand_search`), `agents/sutradhar/agent.py` (`_expands`, `_absorb` counters, `graph` signals), `work.py` (`FactorWork.graph`).
Signature change: `search_reasoning(..., k=10, expand_graph=False)`; reconciled `tests/unit/tools/test_registry.py` (`# RECONCILED`) and `test_switches.py`.
Tests: `test_expansion.py` (11), `test_graph_expansion.py` (10), `test_variants_graph.py` (12; its toolbox gives the fake `search_reasoning` the real `expand_search`).
Expanded paragraphs keep the normal slot rules (factor tag, family, date): a graph hit only counts toward a slot when it passes them. Constants are untuned assumptions.

### S4 (done)
Files: `agents/sutradhar/skew.py` (new: `gini`, `top_gap`, `skew_of`, `thresholds`), `agent.py` (`_apply_skew`, `with_scores` in `_tidy_step`, `_absorb` records, `skew` signals),
`work.py` (`SlotWork.skew_last`, `FactorWork.skew`), `stores/paragraph_store.py` (`_search_scored`; `_search` unchanged in behaviour), `stores/caselaw_reasoning.py` (`search_scored`),
`tools/caselaw/reasoning.py` (`with_scores=False`), `expansion.py` (`ScoredParagraph`). Tests: `test_variants_skew.py` (18), `tests/unit/tools_caselaw/test_scored_search.py` (5).
Thresholds (`GINI_FLAT`, `GAP_FLAT`) are untuned assumptions; RRF scores are flat by construction, so tune on dev. The M19 AUROC metric is not built (eval/ was off limits).

### Next steps
Sweep-1 retrieval variants (S1-S5) are all done. Open: tune the S4 and S5 constants on the dev split; run the real-store retrieval-only comparison for S5 (recall@10 G2, SC-root share) and S4 (AUROC) once the stores are rebuilt;
add the M19 AUROC helper in `eval/metrics`; `retrieval_policy` S1/S2 and `weak_signal`/`graph_expansion` are all combinable (tested pairwise in the variant files).

### Test results after S3
Targeted command: 817 passed, 30 failed; all 30 are pre-existing (stubs raising NotImplementedError in `test_graph.py` and
`test_fallback_state_machine.py`, which the regression command ignores, and 3 in `test_registries.py`: NotImplementedError and an extra
`b6` baseline module, none touched by this work). Regression command: 2146 passed, 16 skipped. `ruff check src`: clean.

---

## Sweep 2: verification and adversarial variants (handoff)

Variant ids follow `docs/evaluation-plan.md` section 3.3. Golden for default-off equivalence:
`tests/unit/agents/vakeel/golden_default_run.json` (digests of the offline case-0007 Vakeel + Abhiyojak run, captured from the HEAD versions of
the Vakeel files before any change; helper `tests/unit/agents/vakeel/_variants_helpers.py`; test `test_variants_golden.py`).

| Variant | Switch | Status |
|---|---|---|
| S8 / A2b self-critique repair | `repair_mode='self_critique'` | DONE |
| S10 / A8c no-isolation sparring | `abhiyojak_isolation=False` | DONE |
| S9 / A8b sampling-only critic | `critic_mode='sampling'` | DONE |
| S15 / A13 reasoning-first output | `output_format='reasoning_first'` | DONE (S15b free_then_parse not built) |
| S11 (a) three-role review | `critic_mode='three_role'` | DONE |
| S11b/c draft debate and vote | `draft_mode='debate'`, `'vote'` | DONE |

### S8 (done)
Files: `agents/vakeel/agent.py` (`_self_review`, `_run_check` branch, `_guard_problems` extracted from `_check_sentence` unchanged, `_offered_sources` extracted from
`_reword`, `repair_signals`, `_emit_repair_signals`, `SELF_CRITIQUE_NOTICE` open issue), `prompts.py` (`TASK_SELF_CRITIQUE`, `TASK_SELF_REVISE`, `SelfReview`),
`offline.py` (`self_critique_offline`), `work.py` (problem word), `orchestration/state.py` (`variant_signals`, empty by default), `switches.py` (`S8` in `IMPLEMENTED_VARIANTS`).
Tests: `tests/unit/agents/vakeel/test_variants_self_critique.py`, `test_variants_golden.py`; reconciled `tests/unit/orchestration/test_switches.py` (`# RECONCILED`).
Signals: `state.variant_signals['repair']`, events `self_critique` (per claim) and `repair_signals` (cumulative; the last one is final; replies made through Sutradhar's `_spar` update it).
Notes: the offline stand-in accepts everything except uncited or repeated sentences, so offline S8 never repairs by itself; use a scripted or hosted model for behaviour.

### S10 (done)
Files: `agents/abhiyojak/isolation.py` (`build_open_context`, `vakeel_view`, `NOTE_TOOLS`), `agent.py` (`isolated`, `system_prompt`, `_instructions`, `_context`, `_view_for`, `guard`,
`_log_llm` token tally, `critic_signals`, `_emit_critic_signals`, `run` adds `variant_signals['critic']`), `prompts.py` (`SYSTEM_PROMPT_OPEN`, `NO_ISOLATION_NOTE`), `switches.py`.
Tests: `tests/unit/agents/abhiyojak/test_variants_no_isolation.py` (11); reconciled `test_switches.py`.
Notes: default `guard` still raises `ContextIsolationError`; `build_open_context` raises unless the switch is off; `list_objections_one_call` stays isolated. Offline S10 yields the
same objections as the default (the rule-based stand-in ignores what it reads); the arm's effect needs a real model. `critic_signals()['tokens']` is the agent's own spend (used by S9 for the equal-token budget).

### S9 (done)
Files: `eval/ablations/a8b_sampling_critic.py` (new: `SamplingCritic(AbhiyojakAgent)` replaces only `raise_objections`; `reference_tokens`; `install`; offline handler), `eval/runners/driver.py`
(`wire_variants` puts the critic in Sutradhar's `_peers`; `collect_variant_signals` adds `variant_signals` to the result only when a variant ran), `switches.py` (S9 implemented; new validator:
`abhiyojak_isolation=False` cannot combine with `critic_mode` sampling / three_role). Signature changes: none to existing functions.
Tests: `tests/unit/agents/vakeel/test_variants_sampling_critic.py` (21); reconciled `test_switches.py` (S9 in the implemented set, dispatch test now uses S7).
Equal tokens: the arm stops before a sample that would pass the budget (estimate: mean of past samples, else prompt plus 300); pass the reference as `case['sparring_tokens']`
(`reference_tokens(events)` of the paired Full run, round 1 only). Open: the runs.yaml job for S9 is not added (configs/eval is outside this sweep).

### S15 (done)
Files: `agents/vakeel/prompts.py` (`DraftedGroundReasoned`, `ReasonedReply`, `REASONING_NOTE`), `agents/vakeel/agent.py` (`_schema_and_limit`, `_ins`, `_keep_reasoning`, `reasoning_of`, `output_signals`,
`_emit_output_signals`, `REASONING_ROOM`; draft, reply and reword calls), `offline.py` (`_with_reasoning`), `switches.py`. Tests: `tests/unit/agents/vakeel/test_variants_reasoning_first.py` (12).
Scope: Vakeel only (the plan also names Peshkar and Sutradhar prompts; those agents were not touched here). The reasoning text lives in `reasoning_first` events (first 1500 characters) and `VakeelAgent.reasoning_of`.
The BailBrief schema is unchanged (no reasoning in exports).

### S11 (a) (done)
Files: `eval/ablations/a8d_three_role.py` (new), `driver.wire_variants`, `switches.py`. Tests: `tests/unit/agents/vakeel/test_variants_three_role.py` (7); reconciled `test_switches.py`.

### S11b / S11c (done)
Files: `agents/vakeel/agent.py` (`_draft_many`, `_medoid`, `_similarity`, `draft_signals`, constants `DRAFT_SAMPLES`, `DRAFT_TEMPERATURE`, `CONVERGED`), `prompts.py` (`TASK_DEBATE`), `offline.py` (`debate_offline`).
Tests: `tests/unit/agents/vakeel/test_variants_draft_modes.py` (11). Ground drafting only; aggregation is a medoid; tokens reported, not equalised.

### Not done
S15b (`free_then_parse`); the `runs.yaml` jobs for S8-S11, S15 (configs/eval is outside this sweep); Peshkar and Sutradhar schemas for S15.
The validator refuses `abhiyojak_isolation=False` with `sampling` and `three_role`.

---

## Sweep 3: intake, safety and serving variants (handoff)

Variant ids follow `docs/evaluation-plan.md` section 3.3. Goldens for default-off equivalence: `tests/unit/agents/peshkar/golden_default_run.json` (offline Peshkar run over a
planted shelf: dossier, dates, events, every prompt), `tests/unit/agents/munshi/golden_default_run.json` (14-page bundle: report, events, tool calls); helpers
`_variants_helpers.py` in each folder.

| Variant | Switch | Status |
|---|---|---|
| S17 / S17b / S17c / S17d (A15) injection defences | `no_typed_handoff`, `no_spotlighting`, `no_guard` | DONE |
| S7 (A11a) hierarchy re-reading | `munshi_gap_policy='hierarchy'` | DONE |
| P7 image-only ingestion | `munshi_image_only=True` | DONE |
| S14 / S14b / S14c / S14d serving | `plan_cache`, `urgency_policy`, `prefix_layout` | DONE |

### S17 (done)
Files: `privacy/defences.py` (new), `agents/base.py` (`defences`, `untrusted` now an instance method, `flag_instructions`, `_handoff`, `injection_signals`, `_with_injection`; `ask` calls `_handoff`),
`agents/peshkar/agent.py` (`run` adds `variant_signals['injection']` only when an arm runs), `agents/munshi/agent.py` + `decisions.py` (`LlmAdvisor(spotlight=)`), `ingestion/pipeline.py`
(`page_read`, `guard`/`min_route` on `read_page`/`read_file`, `PageRead.missed_lines`), `eval/ablations/susceptible_llm.py` (new, `SusceptibleLLM`), `switches.py`.
Tests: `tests/unit/privacy/test_defences.py`, `tests/unit/agents/peshkar/test_variants_golden.py` + `test_variants_injection.py`, `tests/unit/agents/munshi/test_variants_golden.py` + `test_variants_injection.py`;
reconciled `tests/unit/orchestration/test_switches.py` (`# RECONCILED`).
Signature change: `BaseAgent.untrusted` is no longer a staticmethod (it reads the agent's switches); every caller already used `self.untrusted`.
Notes: the guard arm changes Munshi's extraction view (instruction-like lines are dropped when on); the susceptible-model stand-in follows an instruction by channel, so the guard arm shows no success change there. The OCR-vs-text-layer cross-check is not built.

### S7 (done)
Files: `ingestion/hierarchy.py` (new), `ingestion/gaps.py` (`resolve_gap(policy=, signals=)`, one record per item), `agents/munshi/agent.py` (`check_gaps` passes policy and skips an item an earlier re-read filed, under hierarchy only;
`gap_signals`; `_Run.gap_records`; `run` adds `variant_signals['munshi']['gaps']` and `check_gaps` logs a `gap_policy` event only under hierarchy), `switches.py`.
Tests: `tests/unit/ingestion/test_hierarchy.py` (19), `tests/unit/agents/munshi/test_variants_gap_policy.py` (7); reconciled `test_switches.py` (S12 is now the unbuilt id the dispatch test uses).
Notes: weights and `MIN_SCORE` are untuned (TODO on dev bundles). `oracle_regret` is a lower bound. The file to compare is built in the test (four weak scanned pages, arrest and remand on the last).

### P7 (done)
Files: `agents/munshi/agent.py` (`_floor`, `_read_page`, `survey` event, `image_only_signals`, `run` signals), `ingestion/pipeline.py` (`read_file(min_route=)`), `switches.py`.
Tests: `tests/unit/agents/munshi/test_variants_image_only.py` (7); reconciled `test_switches.py`. The ladder is unchanged: `min_route=VISION` already meant [vision, ask counsel].

### S14 family (done)
Files: `batch/cache.py` (`RetrievalCache.peek`, `PlanCache`, `plans_of`), `agents/sutradhar/agent.py` (the single plan-cache hook: `_ask_plan` now checks the cache, the old body is `_ask_plan_model`; `_plan_cache`),
`batch/urgency.py` (`order_cards`, `has_deadline`, `POLICIES`), `batch/scheduler.py` (`Scheduler(policy=, sizes=)`, `_order`, `signals`, `completed`; default path unchanged), `agents/pairokar/agent.py` (`policy` passed, `batch_signals`, `_serving_variant`),
`models/prefix.py` (new), `models/prompting.py` (`prefix_friendly`), `agents/base.py` (`build_prompt`, `ask` meter, `prefix_signals`), `eval/runners/driver.py` (`collect_sweep3_signals`), `switches.py`
(new field `prefix_layout` and variant id `S14d`; `urgency_policy` accepts `'shortest_first'`).
Tests: `tests/unit/batch/test_plan_cache.py`, `tests/unit/agents/sutradhar/test_variants_plan_cache.py`, `tests/unit/agents/pairokar/test_variants_golden.py` + `test_variants_scheduling.py` (+ `_variants_helpers.py`, `golden_default_run.json`),
`tests/unit/models/test_prefix.py`; reconciled `test_switches.py`, `test_registries.py` (`# RECONCILED`: new field `prefix_layout`, implemented set).
Measured on case-0007, offline: the second case with the same signature skips all 8 planning calls, tokens 30,633 -> 12,836, evidence packs byte-identical to the no-cache run.
Notes: `prefix_layout` and `S14d` are not in the plan (it names prefix caching as a server flag); `store_version` has no producer yet: a batch must set it (`plans_of(cache, store_version=...)`) when a store is rebuilt.
Attained service for `urgency_least_work` is planned hours times attempts. Untested against the real models: G1 recall with the cache on.

### Test results
Targeted runs per variant: all green. Final regression command: 3,351 passed, 16 skipped (after reconciling `tests/unit/models/test_interfaces.py`, which lists `models.prefix` as a helper, the one failure of the first run). `ruff check src`: clean.
Not done: the OCR-versus-text-layer cross-check of plan S17(c); datamarking and encoding forms of spotlighting; S15b, runs.yaml jobs for the new variants (configs/eval is outside this sweep).

---

## Sweep 4: routing, topology, chunking, workflow search (handoff)

Variant ids follow `docs/evaluation-plan.md` section 3.3. Golden default-run digests: `tests/unit/agents/sutradhar/golden_default_run.json`.

| Variant | Switch | Status |
|---|---|---|
| S6 (A12) / B5 (S6b) learned store prior | `store_prior='order'` / `'only'` | DONE |
| S12 / S12b topology | `topology='sequential'` / `'single_agent'` | DONE |
| S16 / S16b chunking | `chunking=` | DONE |
| S13 workflow search | grid over switches | DONE (harness and offline smoke) |

### S6 / B5 (done)
Files: `agents/sutradhar/store_prior.py` (new: `StorePrior`, `Outcome`, `outcomes_from_orders`, `train_from_file`, `run_prior_only`, `order_signals`, CLI `python -m vakeel_sahayak.agents.sutradhar.store_prior train --orders F [--out F]`),
`agents/sutradhar/agent.py` (`store_prior_model`, `set_store_prior`, `_apply_prior`, `run` dispatch for `only`, `_variant_signals`), `agents/sutradhar/work.py` (`FactorWork.prior_trace`), `switches.py` (ids in `IMPLEMENTED_VARIANTS`; validator: `only` excludes the contract-loop variants, `free_planner` stays legal).
Artefact: `<data dir>/eval/store_prior.json` (or `VS_STORE_PRIOR`); missing artefact gives the neutral prior (contract order, `trained: False` in signals).
Tests: `tests/unit/agents/sutradhar/test_variants_store_prior.py` (17); reconciled `tests/unit/orchestration/test_switches.py`.
Notes: `order` mode defers (never removes) stores below `prune_below`; the artefact is not trained on real data yet (needs a TRAIN-orders file with G1/G2/G3 gold); court is not in the planner's signals, so the court level is unused at run time; calls saved and regret are estimates against the contract order.

### S12 / S12b (done)
Files: `agents/sutradhar/agent.py` (`_drive_sequential`, `_left_limits`, `_digest`, `_ask_plan` inline plan for `single_agent`, `_new_work` pooled limits, `history` in the plan prompt for `sequential`, `topology` signals), `switches.py` (ids; validator: `sequential` excludes A6/A7).
Tests: `tests/unit/agents/sutradhar/test_variants_topology.py` (11); reconciled `test_switches.py`.
Notes: single_agent still drafts through Vakeel's unchanged `delegate` (no per-factor drafting API without editing Vakeel); the merged-agent claim is about planning, budgets and threading. Paper author lists for this row were not re-checked on the official pages.

### S16 / S16b (done)
Files: `stores/chunk_strategies.py` (new: `STRATEGIES`, `chunk_order_with`, `propositions`, `LateChunkEmbedder`, `strategy_for`), `eval/baselines/chunking_variants.py` (`evaluate_strategy`, `compare_strategies`), `b3_naive_chunking.VARIANTS['proposition']`, `switches.py` (`chunking` accepts fixed, recursive, semantic, page too; ids added).
Tests: `tests/unit/stores/test_chunk_strategies.py`; reconciled `test_switches.py`. Synthetic in-memory indexes only; no store rebuilt; `chunk_order` untouched (default byte-identical).
Not done: BGE-M3 token vectors for true late chunking (models/ outside this change); a model-based Propositionizer; running the comparison on real T1 data (needs the stores).

### S13 (done: harness only)
Files: `eval/runners/workflow_search.py` (new), `switches.py` (S13 in `IMPLEMENTED_VARIANTS`).
Tests: `tests/unit/eval/test_workflow_search.py` (7); reconciled `test_switches.py` (the "fails loudly" test now removes the id from the implemented set; `system_runner('S13')` raises ValueError because a grid point needs fields).
Not done: a real search (needs a hosted or local model, about 36 hours in the plan); testing the winner on the test split.

### Other ids
`Switches.implemented_variants()` now covers every id defined in the table (S1-S17 arms, A1-A10, B5, P5-P7). Not built, by design: no further must/should ids remain; S12's `orchestrated` arm is the default.
