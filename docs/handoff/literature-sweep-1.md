# Literature sweep 1: retrieval and orchestration variants (handoff)

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

## S3 (done)
Files: `src/vakeel_sahayak/orchestration/switches.py` (field, `ARCHITECTURE`, `VARIANT_ALIASES`, validator), `agents/sutradhar/sufficiency.py`
(new), `prompts.py` (`TASK_RATE`, `SufficiencyJudgment`), `offline.py` (`rate_offline`), `work.py` (`FactorWork.stopping`), `agent.py`
(`_apply_rater`, `_store_calls_spent`, `retrieval_signals`, `_finish`), `orchestration/state.py` (`retrieval_signals` field, empty by default).
Tests: `tests/unit/agents/sutradhar/test_variants_stopping.py` (20 pass); reconciled `tests/unit/orchestration/test_switches.py`,
`tests/unit/eval/test_registries.py` (`# RECONCILED`). Docs: `docs/literature-to-code-map.md`, `docs/architecture/skeleton.md`.

## S1 (done)
Files: `agents/sutradhar/critique.py` (new: `critique_assess`, `choose_action`, `critique_data` offline critic, `reorder`, `CritiqueTrace`, `signals`), `prompts.py`
(`TASK_CRITIQUE`, `PassageVerdict`, `SlotCritique`), `offline.py` (`critique_offline`), `work.py` (`SlotWork.verdicts/discarded/critic_action/critic_used`,
`FactorWork.critique`), `agent.py` (`assess`, `_next_move`, `_variant_signals`, which now serves S3 and S1), `switches.py` (S1 in `IMPLEMENTED_VARIANTS`).
Tests: `tests/unit/agents/sutradhar/test_variants_critique.py` (24 pass); reconciled `tests/unit/orchestration/test_switches.py` (`# RECONCILED`).
Signals: `retrieval_signals[factor]['critique']` and `critique`/`critic_action`/`retrieval_signals` events. A slot with nothing retrieved is MISSING with no critic call.

## S2 (done)
Files: `agents/sutradhar/depth.py` (new: `classify` rules none/single/multi, `features_of`, `signals`), `work.py` (`SlotWork.skipped`, `FactorWork.depth/round_cap`),
`agent.py` (`_new_work(adaptive=)`, `_apply_depth`, round cap in `replan`, stopped label `depth_cap`, `_reretrieve` uses full depth), `switches.py`.
Tests: `tests/unit/agents/sutradhar/test_variants_depth.py` (21 pass). Note: case-0007 is BNS-era, so every factor is multi there (loop unchanged);
single/none behaviour is tested by reading the case as IPC-era (monkeypatching `depth.BNS_CODES`) and by setting the Rights Radar undertrial_limit to ELIGIBLE.

## S5 (done)
Files: `pipelines/citation_graph/expansion.py` (new: PPR, `expand_documents`, `merge_ranked`, `ExpandedParagraph`), `stores/caselaw_citations.py` (`expand`, `graph`),
`stores/caselaw_reasoning.py` (`search_docs`), `stores/paragraph_store.py` (`_search_docs`), `stores/hybrid.py` (`key_prefixes` on `search`), `tools/caselaw/reasoning.py`
(`expand_graph=False` argument, `expand_search`), `agents/sutradhar/agent.py` (`_expands`, `_absorb` counters, `graph` signals), `work.py` (`FactorWork.graph`).
Signature change: `search_reasoning(..., k=10, expand_graph=False)`; reconciled `tests/unit/tools/test_registry.py` (`# RECONCILED`) and `test_switches.py`.
Tests: `test_expansion.py` (11), `test_graph_expansion.py` (10), `test_variants_graph.py` (12; its toolbox gives the fake `search_reasoning` the real `expand_search`).
Expanded paragraphs keep the normal slot rules (factor tag, family, date): a graph hit only counts toward a slot when it passes them. Constants are untuned assumptions.

## S4 (done)
Files: `agents/sutradhar/skew.py` (new: `gini`, `top_gap`, `skew_of`, `thresholds`), `agent.py` (`_apply_skew`, `with_scores` in `_tidy_step`, `_absorb` records, `skew` signals),
`work.py` (`SlotWork.skew_last`, `FactorWork.skew`), `stores/paragraph_store.py` (`_search_scored`; `_search` unchanged in behaviour), `stores/caselaw_reasoning.py` (`search_scored`),
`tools/caselaw/reasoning.py` (`with_scores=False`), `expansion.py` (`ScoredParagraph`). Tests: `test_variants_skew.py` (18), `tests/unit/tools_caselaw/test_scored_search.py` (5).
Thresholds (`GINI_FLAT`, `GAP_FLAT`) are untuned assumptions; RRF scores are flat by construction, so tune on dev. The M19 AUROC metric is not built (eval/ was off limits).

## Next steps
Sweep-1 retrieval variants (S1-S5) are all done. Open: tune the S4 and S5 constants on the dev split; run the real-store retrieval-only comparison for S5 (recall@10 G2, SC-root share) and S4 (AUROC) once the stores are rebuilt;
add the M19 AUROC helper in `eval/metrics`; `retrieval_policy` S1/S2 and `weak_signal`/`graph_expansion` are all combinable (tested pairwise in the variant files).

## Test results after S3
Targeted command: 817 passed, 30 failed; all 30 are pre-existing (stubs raising NotImplementedError in `test_graph.py` and
`test_fallback_state_machine.py`, which the regression command ignores, and 3 in `test_registries.py`: NotImplementedError and an extra
`b6` baseline module, none touched by this work). Regression command: 2146 passed, 16 skipped. `ruff check src`: clean.
