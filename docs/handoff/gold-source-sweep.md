# Gold-source sweep: agreed gold primary, rule-only secondary (handoff)

Date 2026-10-26. Nothing committed. Owner decision: the agreed gold (rules and non-Qwen labeler, span-grounded) is the PRIMARY T1 gold; the rule-only gold is a pre-declared SECONDARY gold; both are reported as one rescoring sweep (no model call, cost 0).

## What moved (all under gitignored `data/`)
- `data/testsets/t1` was MOVED (not copied) to `data/testsets/t1_rule_only` (rule-only gold, its `manifest.json` refreshed). `data/testsets/t1` was rebuilt from `t1_gold_candidate/{cases,dev}.jsonl` plus the unchanged id files (`manifest_dev.json`, `manifest_open.json`, `manifest_blind.json`, `blind_sealed.json`), its `manifest.json` refreshed with the builder's `_stats` (coverage numbers now describe the agreed gold) and `details.gold = {source, cases_sha256, dev_sha256, gold_sha256}`. `t1_gold_candidate` is kept (it is the agreed source and what `gold_source=agreed` falls back to if `t1/` is ever swapped back to rule).
- `data/interim/t1_work/gold/g{1,3,4,5,6,7}.jsonl`: originals MOVED to `data/interim/t1_work/gold/rule_only/`; the files in `gold/` are now the agreed records merged over the rule-only rows by `doc_id` (the 250 labelled orders carry agreed records, the other 19,057 orders keep their rule rows, so rebuilding T1 still finds every order). g2 untouched.

## Hashes
| item | before | after |
|---|---|---|
| blind-set hash (`scripts/prereg_hash.py`) | 9185e1cce6f981a70df4cf4aaaa5a35bc0648dfa216dff6900010512be8ebe32 | same (unchanged) |
| `manifest_blind.json`, `blind_sealed.json`, `manifest_dev.json`, `manifest_open.json` (md5) | 65410ace..., ee95d3c6..., b973b19e..., d27f50614... | byte-identical in `t1` and `t1_rule_only`: no id and no id hash changes |
| rule-only `cases.jsonl` sha256 | ab5ce38994be895812d21a62756e9520ec6bc37e7d96e1cd7c0dd693a6f89378 | same file in `t1_rule_only` |
| rule-only `dev.jsonl` sha256 | 7853c3cb38ed3fa60a82ca94cbaf7e5890cc41cfcbc8a0c9342c5b448ec47270 | same |
| rule-only gold hash | 8c081a09c992c1039d833a845c0010b6e6b738da088a2e6a363c3829c8a5bac6 | same |
| agreed `cases.jsonl` sha256 | | 40366c9eeedc960040b11c22ca14700a5ebba2116c7b9c6ec78427bcaeb958a1 |
| agreed `dev.jsonl` sha256 | | 9a22f359b9f4c5ba8337384aed1fc9ed86bee16ce1f05582960df5d73384618c |
| agreed gold hash (`gold_sha256` = sha256 of the two file hashes) | | ce7feced13f8643f060a29a96546570d6b2ec698f742c54700f6714e1f42a55f |
| `t1/manifest.json` md5 | 4210e017ef2e95e0856260ab98b68a62 | d0ade064d0d13b57277660ebffce2b7a (coverage stats and `details.gold` changed; `blind_set_hash` same) |
Note for `docs/preregistration.md` section 0: the "Dev ids" file hash and the T1 manifest hash must be taken after this swap. T2, T3, T6 and T8 manifests record `source_cases_sha256` of the OLD `t1/cases.jsonl`; the lead's data-bundle rebuild should rerun those builders (or accept that they point at the rule-only file, which is now `t1_rule_only/cases.jsonl`). Test-split coverage (share of the 200 cases with a label, agreed against rule-only): G1 0.665 / 0.74, G4 0.34 / 0.46, G5 0.635 / 0.72, G6 0.545 / 0.55, G3 1.0, G7 0.005.

## Commands
- Swap (idempotent; scriptable): `scripts/swap_gold.sh --primary agreed` (done) or `--primary rule`. It refuses to overwrite a `t1/` whose gold is stored nowhere else unless `--backup DIR` (must not exist) is given; both the agreed (`t1_gold_candidate`) and rule-only (`t1_rule_only`) golds are always kept, so switching back and forth needs no backup. Interim gold files follow unless `--no-interim`. Code: `src/vakeel_sahayak/testsets/gold_source.py` (`swap_t1`, `swap_interim_gold`, `refresh_manifest`, which reuses the builder's `_stats`; the blind slice is found through its salted hashes, the sealed ids are never read). Check the layout: `python -m vakeel_sahayak.testsets.gold_source info`.
- Reading: `load_t1("test"|"dev", gold_source=None)` and `t1_dir(gold_source)` in `testsets/gold_source.py`; `gold_source` is `agreed` (default) or `rule`; `VS_GOLD_SOURCE` overrides the default. `eval/runners/jobs.t1_cases_path(gold_source)`, `testset_cases_path("T1")`, `driver run --gold-source agreed|rule` (default cases), and the F1, F4, F7 feature loaders (`feature_common.t1_dir`) follow it. `MANIFEST.json` of every driver run now has `gold_source` and `gold_sha256` (None for T2 to T9 case files).
- Job: `gold_source_sweep` in `configs/eval/runs.yaml` (`rescoring: true`, `model_calls: 0`, listed in `priority` and `run_variants.JOBS`). `driver plan --job gold_source_sweep` prints cost 0 (0.00 USD, INR 0.00); `plan --all` lists it last. Running it raises `NotImplementedError` naming `vakeel_sahayak/eval/metrics` while those modules are stubs (Harshita), and after they exist raises until the rescoring loop is written (read every `<out>/runs/*/outputs/<system>`, score against `load_t1("test", source)` for each source in `gold_sources`, write `scores_<source>.json`). The loop and the metrics are NOT done.
- Docs: `docs/evaluation-plan.md` 5.9 new subsection "Gold-source sensitivity" (primary, secondary, one sweep, not a new Holm family, coverage G1 169/250, G3 249, G4 88, G5 155, G6 133 of 152, G7 1 so C30 rests on T4, claims by gold, second labeler note), one sentence added to 5.3; `docs/preregistration.md` section 0 (label sources, gold hashes placeholders `<hash agreed>`, `<hash rule>`, sensitivity row) and section 6 (Holm on the primary gold, sweep uncorrected). No results are stated.
- Tests: `tests/unit/testsets/test_gold_source.py` (5): both sources load, case ids identical and in the same order, hashes differ, manifests record the source, blind manifest byte-identical, swap idempotent and reversible, refusal without a backup, run manifest records the gold. No existing test was changed.

## Test results
`tests/unit/testsets tests/unit/pipelines/gold`: 265 passed, 6 skipped (before the last runner edit; they do not touch it). `tests/unit/eval` without `test_metrics.py` and `test_stats.py`: 275 passed, 4 failed; the 3 `test_ingestion_pipelines` metric failures are the known stubs, the 4th (`test_runners` job coverage) was caused by my new job not being in a runner and is fixed (added to `run_variants.JOBS`; `test_runners.py` and `test_eval_jobs.py` rerun: 74 passed with the new test file). `make data-check`: required missing 0.

## Not done or blocked
- Rescoring itself (metrics are stubs; see above). Rebuilding the data bundle and the derived T2/T3/T6/T8 manifests is the lead's. Re-running the T1 builder from the merged interim gold was not done (the selection could change if `_clean` depends on gold status; not checked).
- G6 note: the agreed g6 candidate has 152 rows (grants only); the other 98 orders kept their rule-only `not_applicable` rows in the merge.
