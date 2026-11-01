# Rights Radar table for the report (2026-11-01)

## Done
- Ran F3 (`eval/features/f3_rights_radar.py`) offline on T4 (627 scenarios, `sweep-v3/data/testsets/t4`, spec hash in `docs/results/rights/t4_manifest.json`), all three arms. Radar arm: the rules engine called directly on the scenario inputs (not through the Peshkar agent). The two "LLM" arms are the offline naive stand-in reader (`naive_reader`), not a model.
- Inputs kept in `docs/results/rights/`: `per_scenario.csv` (1,881 rows: id, rule, arm, designed, predicted), `t4_manifest.json`.
- `docs/report/tools/make_table_rights.py` (stdlib) writes `docs/report/generated/table_rights.tex` (Wilson 95%, bold best, underline second best in accuracy and false-ELIGIBLE columns; CHECK rate plain).
- Table included with `\gentable{table_rights}` in `sections/appendix.tex`; one results paragraph in `sections/results.tex` (after "Offline studies"). `./build.sh` builds (37 pages), no undefined references.

## Result
Radar 627/627 (1.000, [0.994, 1.000]), 0 false ELIGIBLE, CHECK rate 0.134. Stand-in reader 0.488, 17 false ELIGIBLE; with date_calc identical.

## Limits (stated in the paragraph)
- Radar = 1.000 is a consistency check against a spec writer that shares the same reading of the rule text; not legal validation.
- Six of seven rules have T4 scenarios; `grounds_of_arrest` has none and is not claimed.
- No real model was run on T4; the stand-in says nothing about one.

## Discrepancy to resolve
The brief says "6 of 7 rules verified". `configs/rights_rules.yaml` at this commit has three dated rules (`notice_of_appearance`, `production_24h`, `grounds_of_arrest`) and four with `last_verified: null` (`default_bail`, `undertrial_limit`, `antil_category`, `statutory_bar`, corrected in HA-03, awaiting re-check). `sections/limitations.tex` and `challenges.tex` say "six of seven unverified". The new paragraph therefore makes no verification-count claim; it only says the rule texts are still being checked. Reconcile those sentences once the verification state is settled.

## Not done
- Radar not run through the Peshkar agent on dossiers (T4 are rule inputs); no hosted-model arm; no McNemar test (stand-in arms are not informative); F3 job size in `configs/eval/runs.yaml` untouched.

## Rerun
```bash
VS_DATA_DIR=<data> VS_LLM_BACKEND=offline VS_MODELS=offline PYTHONPATH=src .venv/bin/python -m vakeel_sahayak.eval.features.f3_rights_radar run --out <dir>
python3 docs/report/tools/make_table_rights.py collect <dir> docs/results/rights/per_scenario.csv
python3 docs/report/tools/make_table_rights.py table docs/results/rights/per_scenario.csv docs/results/rights/t4_manifest.json docs/report/generated/table_rights.tex
cd docs/report && ./build.sh
```
