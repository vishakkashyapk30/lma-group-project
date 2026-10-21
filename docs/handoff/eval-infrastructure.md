# Evaluation infrastructure: handoff (EV-03, EV-05, EV-06a, EV-07, PR-12)

Updated after each finished task. Status values: done / partly / not started.

| Task | Status | Notes |
|---|---|---|
| EV-07 + PR-12 driver, runners, smoke | done | `make smoke` exits 0; `tests/unit/eval/test_runners.py` 42/42 |
| EV-06a ablations A2, A8, A9 | done | all ten wrappers (A1-A10) done with the shared `ablations/common.py`; `test_ablation_runs.py` 30/30, `test_registries.py` 46/46 |
| EV-05 baselines | done | B0, B0L, B0S, B1, B2, B3, B4, B6, Full; `test_baselines.py` 26/26, `test_chunking_variants.py` 6/6, new `test_b6_and_b0_variants.py` 16/16 |
| EV-03 T1 builder | done (real run done) | `tests/unit/testsets/test_t1_court_grounded.py`, `test_t1_blind.py` |

## EV-07 / PR-12: driver (done)
Files: `src/vakeel_sahayak/eval/runners/{driver,jobs,systems,shard_runner,run_rq1,run_ablations,run_rq2,run_features,run_tool_calling,run_safety}.py`,
`eval/baselines/full_system.py`, `Makefile` (`smoke`, `eval-smoke`).
- `driver.run_agents(case, ctx, counsel)`: Munshi (if a bundle) -> Peshkar -> Gate 1 -> Sutradhar.run -> Sutradhar.delegate (Vakeel drafting,
  check-and-repair, Abhiyojak sparring) -> Gate 2 -> export attempt. No LangGraph. `ScriptedCounsel` approves only through `GateGuard.approve`
  and only when the scenario says so; the export goes through `call_tool("export")` so `GateGuard` still blocks it (`export.blocked`).
- `driver.run_cases(...)`: resumable shard loop, one `<case_id>.json` per case, `_events/<case_id>.jsonl`, `MANIFEST.json` (code version, config hash,
  model/version/date stamp, seed, switches, budgets, case-file hash).
- Output layout (README C6): `<out_dir>/runs/<job>/outputs/<system>/<case_id>.json`, repeat k > 1 in `<system>__run<k>`. (`docs/evaluation-plan.md` 6.0 proposed another layout; C6 wins.)
- `make smoke`: `VS_MODELS=offline VS_LLM_BACKEND=offline .venv/bin/python -m vakeel_sahayak.eval.runners.driver smoke` (case-0007 fixture via
  `tests/fakes`, so it must run from the repo root). `make eval-smoke` needs `data/testsets/t1/dev.jsonl` (EV-03).
- Commands: `.venv/bin/pytest -q -p no:cacheprovider tests/unit/eval/test_runners.py tests/unit/eval/test_ablation_runs.py`
- Not done: the blind-slice lock (`testsets/blind.py`, with the T1 builder), jobs other than rq1/ablations raise NotImplementedError in `jobs.py` (T6/T7, features, RQ2).

## EV-05 baselines (done)
Files: `eval/baselines/{common,offline_rules,b0_single_pass,b1_single_rag,b2_whole_doc,b3_naive_chunking,b4_all_stores,b6_expert_rule,chunking_variants,full_system}.py`, `eval/runners/systems.py` (name -> runner), `tests/unit/eval/test_b6_and_b0_variants.py`.
- B0/B0L/B0S: `b0_single_pass.run_case` and `run_case_with_model(case, ctx, role)` (roles `None`, `teacher`, `munshi_4b`); offline stand-in handler registered for the task.
- B4: Sutradhar in mode B4 via a subclass in `b4_all_stores.py` (facts text plus factor name in every query, all 12 factors queried). Needed because `agents/sutradhar/baselines.run_b4` queries with the dossier summary and skips picker-NOT_APPLICABLE factors; the subclass is a workaround for code another agent is editing.
- B3: retrieved paragraphs are re-cut with the chosen chunker (default `recursive`); the real dev choice needs the retrieval-only analysis (`select_best_variant`).
- B1/B2/B3 use `search_reasoning` / `similar_orders` as the stand-in for the merged index (SKELETON-GAP in the tests).
- B6: own section regex, no model, tools `get_statute`, `map_section`, `rights_check`; a subprocess test proves it loads neither `pipelines.factor_tagger`, `pipelines.order_facts` nor `pipelines.gold`.
- Test edited: `test_registries.py::test_baselines_b0_to_b4_and_full_system` expects b6 too (marked `# RECONCILED`).
- Not done: `run_job` has no arms for B5, the S-variants, T6/T7, features, RQ2. Still failing in `tests/unit/eval` (other owners): metrics, stats, features, ingestion pipelines.

## Jobs (partly done)
`eval/runners/jobs.py`: done: `rq1_full`, `rq1_b2_b3`, `rq1_b0l_b0s_b6` (new job in `configs/eval/runs.yaml`, test list edited with `# RECONCILED`), `ablations`, `a5_extractors`, `a10_knockouts`,
`t7_safety` and `t6_tool_calling` (the scripted `tests/system` scenarios, per-file result JSON per run; they run on fakes and will report today's failures of the unbuilt graph and API).
Waiting (NotImplementedError naming the dependency, see `NEEDS` in `jobs.py`): RQ2 (P1-P6, T2), F2 (T3), F1/F5/F6 (export), F3 (T4), F4 (T5). Not in `runs.yaml` yet: S1, S2, S5, S8-S10, B5 (need new `Switches` fields from EV-01 and Sutradhar variants).
Tests: `tests/unit/eval/test_driver.py` (13), `test_runners.py` (42).
Known gap: no route resolves a Gate 2 checklist item; the scripted counsel marks NEEDS_REVIEW grounds SUPPORTED by a counsel-authored brief write and cannot resolve an UNANSWERED objection (Gate 2 then stays closed).

## EV-03 T1 builder (done)
Files: `testsets/{t1_court_grounded,blind,common}.py`; fix in `pipelines/gold/g2_cited_precedents.py` (`paths.interim` -> `interim_dir`); tests `test_t1_court_grounded.py` (one leaky-id set edited, `# RECONCILED`), `test_t1_blind.py`, `test_common.py` (faker tests skip: faker is not installed).
Run: `.venv/bin/python -m vakeel_sahayak.testsets.t1_court_grounded --update-splits` (about 15 min; writes `data/interim/t1_work/` candidates and gold, `data/testsets/t1/`, and rewrites `data/interim/splits.json` with a `.pre-t1` backup). `--open-blind` opens the sealed ids once (needs git tag `eval-freeze-v1`, writes `data/eval/blind.lock`).
Real result: 200 test (80 BNS-era, 137 dated after 2025-04), dev 50, open 120, blind 80 (40 BNS-era, all post-release; ids hashed). Pool: 9,892 High Court candidates, 6,736 test and 1,126 dev orders dropped by the 8-word facts overlap rule. Gold is rule-only (provisional) because no non-Qwen labeler ran; G2 citation coverage 0 of 80 extracted (no `oil_metadata.jsonl`), G7 almost empty.
Next steps: run the non-Qwen labeler for agreed gold; supply `oil_metadata.jsonl`; commit the blind set hash into `docs/preregistration.md`; `make eval-smoke` works on `dev.jsonl`.
