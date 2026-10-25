# Literature sweep 4: routing, topology, chunking, workflow search (handoff)

Variant ids follow `docs/evaluation-plan.md` section 3.3. Golden default-run digests: `tests/unit/agents/sutradhar/golden_default_run.json`.

| Variant | Switch | Status |
|---|---|---|
| S6 (A12) / B5 (S6b) learned store prior | `store_prior='order'` / `'only'` | DONE |
| S12 / S12b topology | `topology='sequential'` / `'single_agent'` | DONE |
| S16 / S16b chunking | `chunking=` | DONE |
| S13 workflow search | grid over switches | DONE (harness and offline smoke) |

## S6 / B5 (done)
Files: `agents/sutradhar/store_prior.py` (new: `StorePrior`, `Outcome`, `outcomes_from_orders`, `train_from_file`, `run_prior_only`, `order_signals`, CLI `python -m vakeel_sahayak.agents.sutradhar.store_prior train --orders F [--out F]`),
`agents/sutradhar/agent.py` (`store_prior_model`, `set_store_prior`, `_apply_prior`, `run` dispatch for `only`, `_variant_signals`), `agents/sutradhar/work.py` (`FactorWork.prior_trace`), `switches.py` (ids in `IMPLEMENTED_VARIANTS`; validator: `only` excludes the contract-loop variants, `free_planner` stays legal).
Artefact: `<data dir>/eval/store_prior.json` (or `VS_STORE_PRIOR`); missing artefact gives the neutral prior (contract order, `trained: False` in signals).
Tests: `tests/unit/agents/sutradhar/test_variants_store_prior.py` (17); reconciled `tests/unit/orchestration/test_switches.py`.
Notes: `order` mode defers (never removes) stores below `prune_below`; the artefact is not trained on real data yet (needs a TRAIN-orders file with G1/G2/G3 gold); court is not in the planner's signals, so the court level is unused at run time; calls saved and regret are estimates against the contract order.

## S12 / S12b (done)
Files: `agents/sutradhar/agent.py` (`_drive_sequential`, `_left_limits`, `_digest`, `_ask_plan` inline plan for `single_agent`, `_new_work` pooled limits, `history` in the plan prompt for `sequential`, `topology` signals), `switches.py` (ids; validator: `sequential` excludes A6/A7).
Tests: `tests/unit/agents/sutradhar/test_variants_topology.py` (11); reconciled `test_switches.py`.
Notes: single_agent still drafts through Vakeel's unchanged `delegate` (no per-factor drafting API without editing Vakeel); the merged-agent claim is about planning, budgets and threading. Paper author lists for this row were not re-checked on the official pages.

## S16 / S16b (done)
Files: `stores/chunk_strategies.py` (new: `STRATEGIES`, `chunk_order_with`, `propositions`, `LateChunkEmbedder`, `strategy_for`), `eval/baselines/chunking_variants.py` (`evaluate_strategy`, `compare_strategies`), `b3_naive_chunking.VARIANTS['proposition']`, `switches.py` (`chunking` accepts fixed, recursive, semantic, page too; ids added).
Tests: `tests/unit/stores/test_chunk_strategies.py`; reconciled `test_switches.py`. Synthetic in-memory indexes only; no store rebuilt; `chunk_order` untouched (default byte-identical).
Not done: BGE-M3 token vectors for true late chunking (models/ outside this change); a model-based Propositionizer; running the comparison on real T1 data (needs the stores).

## S13 (done: harness only)
Files: `eval/runners/workflow_search.py` (new), `switches.py` (S13 in `IMPLEMENTED_VARIANTS`).
Tests: `tests/unit/eval/test_workflow_search.py` (7); reconciled `test_switches.py` (the "fails loudly" test now removes the id from the implemented set; `system_runner('S13')` raises ValueError because a grid point needs fields).
Not done: a real search (needs a hosted or local model, about 36 hours in the plan); testing the winner on the test split.

## Other ids
`Switches.implemented_variants()` now covers every id defined in the table (S1-S17 arms, A1-A10, B5, P5-P7). Not built, by design: no further must/should ids remain; S12's `orchestrated` arm is the default.
