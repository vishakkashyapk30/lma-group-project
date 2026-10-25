# EV-01: Switches fields and variant table (handoff)

## Done
- `Switches` fields of evaluation plan 3.4 with the plan's names and values; defaults are the current behaviour (`variant()` is `full`).
  New: `retrieval_policy`, `weak_signal`, `graph_expansion`, `store_prior`, `munshi_gap_policy` (default `sequential`), `repair_mode`,
  `critic_mode`, `abhiyojak_isolation`, `draft_mode`, `topology`, `plan_cache`, `urgency_policy` (default `urgency`), `output_format`
  (default `answer_only`), `no_typed_handoff`, `no_spotlighting`, `no_guard`, `munshi_image_only` (P7), `chunking` (S16; not named in plan 3.4).
- `for_variant()` / `variant()` know: full, A1-A10, S1-S17 (arms `S3b`, `S11b/c`, `S12b`, `S14b/c`, `S15b`, `S16b`, `S17b/c/d`), B5, P5-P7,
  aliases A11a, A11b, A12-A16, A2b, A8b-d, S6b. S13 needs a grid point (`for_variant('S13', **fields)`).
- Validators: planner-modifying switches cannot combine with `fixed_router` / `free_planner`; `single_agent` excludes planner switches;
  `hierarchy` excludes P5; `repair_mode='none'` sets `no_check_repair` (A2), `critic_mode='none'` sets `no_sparring` (A8); `self_critique`
  / `sampling` / `three_role` / `abhiyojak_isolation=False` reject the matching legacy "off" flag.
- `Switches.implemented_variants()`, `assert_variant_implemented(name)`, `canonical_variant(name)`. Implemented: full, A1-A10, S3, S3b, P5, P6.
- Runner dispatch: `eval/runners/systems.py` (A/S ids and b5) and `jobs._run_ablations` call `assert_variant_implemented`.
- Docs: "EV-01 switch table" appended to `docs/literature-to-code-map.md`.

## Not done
- No behaviour for any new switch (agents, stores, batch, ingestion untouched). `configs/eval/runs.yaml` jobs for new arms not added.

## Tests
`tests/unit/orchestration/test_switches.py` (field set reconciled, new tests for defaults, round-trips, aliases, validators,
`implemented_variants`, dispatch) and `tests/unit/eval/test_registries.py` (field documentation test reconciled).
`tests/unit/eval/test_stats.py` fails on `NotImplementedError` stubs (EV-03 not built): unrelated to EV-01.

## Next steps
Each variant task flips its id into `IMPLEMENTED_VARIANTS` in `switches.py` (and updates the `test_implemented_variants...` test).
