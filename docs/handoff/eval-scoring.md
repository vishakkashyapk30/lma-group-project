# Eval scoring: driver outputs to tables (handoff)

Date 2026-10-26. Nothing committed. Update 2026-10-27 (`eval-complete.md`, `sweep-dev.md`): M5 and the citation and abstention metrics are now built (rows marked below); run manifests carry `git_sha`, `git_dirty` and `code_tree_hash` and the loader refuses to score runs from different commits (`--allow-mixed-code` overrides; tests `test_scoring_pipeline.py`, `test_manifest_code_stamp.py`); the agreed gold now has G2 merged (14 test cases changed, 0 dev; dev has 0 resolved citations, so M10 stays `n/a (n=0)` on dev). Code: `src/vakeel_sahayak/eval/scoring/` (`loader`, `case_metrics`, `engine`, `pipeline`, `render`, `stats_extra`, `cli`),
tests `tests/unit/eval/test_scoring_{math,pipeline,render}.py` (+ `scoring_fixtures.py`), Makefile targets `eval-score` and `eval-report`.

## Commands
```bash
# 1. outputs from the driver (offline example; any driver layout works: every directory with a MANIFEST.json is one run of manifest["system"], `<system>__run<k>` is repeat k)
VS_MODELS=offline VS_LLM_BACKEND=offline .venv/bin/python -m vakeel_sahayak.eval.runners.driver run --system full --n 3 --out <runs>/outputs/full
# 2. score (dev slice needs no lock); --gold-source both = the gold_source_sweep job (same outputs, both golds, delta, robustness)
.venv/bin/python -m vakeel_sahayak.eval.scoring score --runs <runs> --slice dev --gold-source agreed|rule|both --out <out>      # or: make eval-score RUNS=<runs> OUT=<out> GOLD=both
# 3. tables and figures
.venv/bin/python -m vakeel_sahayak.eval.scoring report --scores <out>                                                          # or: make eval-report OUT=<out>
```
Other flags: `--reference full` (system the others are compared with), `--testsets DIR` (default the configured `data/testsets`; note `VS_DATA_DIR` rebases it, so pass
`--testsets` when you set `VS_DATA_DIR` to a scratch dir), `--pass-bar 0.5`, `--stances favourable,adverse`, `--strict` (a stub scorer raises `NotImplementedError` naming the function instead of a `pending` column).
Outputs: `score_<gold>.json`, `per_case_<gold>.csv` (+ `.parquet` when pyarrow is installed), `sweep.json` (both golds), `tables/*.{md,tex,csv}` (secondary gold in `tables/rule/`), `figures/` (CSV always; PDF and PNG when matplotlib is installed, it is not today).
T4 Rights Radar records (`{rule, predicted, designed}` written by `eval/features/f3_rights_radar.py`) anywhere under `--runs` are picked up as arms (Wilson interval, false-ELIGIBLE with the rule-of-three bound, McNemar of radar against the LLM arms).

## Rules it enforces
- **Slices**: `dev` (dev.jsonl, 50 orders, no lock), `open` (the 120 of `manifest_open.json`), `blind`. Blind goes through `testsets.blind.open_blind`: needs `--open-blind`, the git tag `eval-freeze-v1`, no `data/eval/blind.lock`; it writes the lock when it opens (one opening). The check happens after the runs are loaded, so an empty or wrong `--runs` does not burn the opening. Saved outputs of blind ids are dropped from a dev or open scoring (counted in `meta.excluded_records`).
- **Gold**: `--gold-source agreed` (primary) or `rule` (pre-declared secondary) read through `testsets.gold_source.load_t1`; the same saved outputs score against either. Run manifests record their own `gold_source`; it does not matter for scoring because systems never see the gold.
- **Statistics (plan 5.1 to 5.4)**: runs averaged within a case; paired bootstrap interval (`eval/stats/bootstrap`), Wilcoxon (`eval/stats/wilcoxon`; if scipy is missing the p comes from a bootstrap and `p_source` says so), d_z; binary outcomes (per-case pass^k, per-item gold-factor hits) get exact McNemar and a cluster bootstrap (`scoring/stats_extra.py`, written here because `eval/stats` has neither).
- **Holm (plan 5.3)** only inside the registered primary families of `engine.FAMILIES` (recall, hallucination, guard, ablate-recall, sparring, retrieval), with the registered family size m (a test not run counts as p = 1, so a partial run is not under-corrected), on the gold it is called for. Everything else is `exploratory (uncorrected)`. The sweep adds no test: it reports sign and Holm decision of each family test on both golds and `robust` when both agree. Families for the other plan families (F-ingestion, F-features, F-safety) are not here: they do not come from per-case T1 outputs.

## Metrics and where they come from
| Column | Source | State |
|---|---|---|
| Factor recall, precision strict and lenient, F1, G5 recall (M1 to M4) | `eval/metrics/factor_scores.factor_recall_precision` on answerable factors (case row `answerable`, else `pipelines.gold.common.answerable_factors(facts_text)`) | works; None (n/a) where the denominator is empty, n printed |
| Unsupported-fact rate (M6) | `eval/metrics/unsupported_fact.unsupported_fact_rate` | called; it was implemented by the metrics agent during this task (NLI facade or MiniCheck). If it raises `NotImplementedError` the column prints `pending` and `meta.pending` names it |
| Recall@10 of court-cited precedents (G2), coverage | `eval/metrics/retrieval.recall_at_k` on the ranked documents: record `retrieved`, else Sutradhar's tool results in `_events/`, else the brief's cited authorities (under-estimate; the column `G2 retrieved from` says which) | works; on T1 today **0 orders have a resolved citation** (manifest: 0 of 80 resolved), so the cell is `n/a (n=0)` |
| Objection recall, precision (G4) | sparring objections in the record against agreed G4 | works; n = orders with an agreed objection |
| Rights Radar | T4 records (above); G7 on T1 has 1 labelled order and the run record carries no rights report | T4 works; G7 agreement is not computed |
| pass^k, flip share, run SD | `eval/metrics/agentic.pass_hat_k`; pass = factor recall >= `--pass-bar` (0.5) and no error | works; the bar is provisional (the preregistration leaves it `<definition>`) |
| Coverage (M33, x-axis) | share of grounds emitted without NEEDS_REVIEW and not the "no supported argument" placeholder; a baseline (no gate fields) cannot decline: 1.0 | works |
| Coverage-risk curve, risk side and AURC (M33), M35, citation precision and recall (M16), M9, M13, M15, M18 | `eval/metrics/citations.py` + `eval/scoring/citation_scores.py`; tables `table_citations`, `table_abstention` | **built 2026-10-27** (superseded: was "not built"). Caveats: M16, M33, M35 carry the "offline stand-in" NLI label unless MiniCheck or the DeBERTa NLI is installed (the table names the checker); M33 risk is 0 at tau = the M6 cut by construction; M15 on the dev run is 0 violations with known-treatment share 0 (cited paragraphs carry no treatment labels); M18 is event-based and the stopped-too-early replay to the 16-call budget is NOT computed; a metric whose resource is absent is `pending` (`--strict` raises) |
| Label-source sensitivity (M5) | `eval/label_sensitivity.py`, flag `--second-labeler data/interim/gold_candidate`; tables `table_label_sensitivity`, `table_label_kappa` | **built 2026-10-27**: four sources (rules only, one labeler, agreed, optional second labeler: Sarvam, 80 orders, G1 only), system ranking per source, Cohen kappa per factor with a bootstrap interval |
| Citation faithfulness by removal (M17) | computation `removal_change`; arm `eval/runners/m17_removal.py` | built; smoked offline on one dev case; lower bound only; needs a real drafter for a result |
| Tokens, store calls, seconds, USD per case, USD per passed case | record `meta`; USD is 0 offline, priced on OpenAI from `configs/eval/runs.yaml` `estimate`, None on Ada/Sarvam | works |

Definitions fixed in code and to be frozen in the preregistration: argued factor (non-placeholder ground, stance not `not_applicable`), answerable rule, pass bar, coverage. Captions say `Preliminary dev result` for the dev slice, name offline stand-in models, and print the label source; a system scored on fewer than 20 orders gets a "too few for a claim" note (plan 5.5).

## How to add a metric
1. Add the per-case value to the dict returned by `case_metrics.score_case` (None when undefined; call the `eval/metrics` function, and for a stub catch `NotImplementedError`, set `pending[<name>] = <dotted function>` and honour `cfg.strict`).
2. Register it in `engine.METRICS` (label, higher is better); it then gets a summary with interval and n, and `PAIRED_METRICS` decides whether it enters the paired table. A gold-dependent metric also goes into `pipeline.GOLD_DEPENDENT` (the sweep).
3. Put it in a registered family in `engine.FAMILIES` only if the preregistration lists it; otherwise it is exploratory.
4. Add a column in `render.table_main` (or a new `Table`), and a hand-computed test in `test_scoring_math.py`.

## Done on a real offline run (scratch under /tmp/claude-1000/sc, will not survive)
`driver run` of full (2 runs), b0, b1 on 3 dev cases (the first 3, none has an agreed answerable factor: every M1 cell is n/a) and on 6 dev cases chosen because G1 meets the answerable set (`t1dev-003, 009, 011, 025, 033, 039`), scored with `--gold-source both`, plus 40 T4 scenarios (`f3_rights_radar`). The numbers describe the offline template model only.

## Not done / next
- (Done 2026-10-27, see the table: per-claim support scores for M33 and M35, and M9, M13, M15, M16, M17, M18.) Still open: M16, M33 and M35 on a real NLI (MiniCheck or DeBERTa) rather than the stand-in; M18 stopped-too-early replay; M17 on a real drafter.
- The driver does not save the evidence packs (only a pack count), so recall@10 reads Sutradhar's tool results from `_events/`; saving `retrieved` in the record would make it exact.
- Table 2 (retrieval-only), 3, 4 layout per variant, 5 to 8 (ingestion, features, safety, slices) and figures 1, 3, 4 to 10 are not rendered; figures 2 (cost-quality) and the per-factor bars are, as CSV and, with matplotlib, PDF and PNG (the matplotlib branch is only tested against a stub here).
- Contamination (pre and post Qwen3) and per-court slices are not cut; `case_means` rows carry no court field yet (add it from the gold row).
- `matplotlib` is not in any extra of `pyproject.toml`; add it to `eval` if figures are wanted.
