# Eval-side code completed (handoff)

Date 2026-10-27. Nothing committed. No model call of any kind was made (offline stand-ins only, stores and data read-only). Scope: `src/vakeel_sahayak/eval/**`, the S15b hook in
`orchestration/structured_output.py` and the registry in `orchestration/switches.py`, `scripts/ada/*.sh`, `scripts/sweep_dev.py`, `configs/eval/**`, tests under `tests/unit/{eval,scripts}`.

## What was built, by task

### 1. M5 label-source sensitivity (`eval/label_sensitivity.py`, wired into `scoring score` and `report`)
- `compute(runs, cases, cfg, second_labeler_dir)`: the same saved outputs scored against four label sources, no model call: keyword rules only (`rule_labels`), one labeler only
  (`llm_labels`, today gpt-6-luna, span-grounded), agreed only (`labels`, the primary), and an optional second labeler read from `raw_<slug>_g1.jsonl` (Sarvam: 80 orders, G1 only).
  Per system and source: M1, M2 strict and lenient, M3, M4 (G5 recall) with bootstrap interval and n; the system ranking by M1 per source and whether it equals the agreed order; Cohen kappa per
  factor (rule vs labeler for G1, G4, G5; labeler vs labeler2 for G1) with a bootstrap interval, and pooled.
- `scoring score --second-labeler data/interim/gold_candidate` (flag; default none so tests never read `data/`). The block is written into `score_agreed.json` (`label_sensitivity`; None on the rule-only pass).
- `report` writes `table_label_sensitivity` and `table_label_kappa` (md, tex, csv). `label_sensitivity.run(out_dir)` flattens the block (the old stub signature).
- Real data (dev, 6 systems of `data/eval/dev_runs`): G1 pooled kappa rule vs labeler 0.62, G4 0.46, G5 0.60; the system order under rules-only and labeler-only differs from agreed in the middle (b4/b0l), top (b6) and bottom (full) are the same.
- Tests: `tests/unit/eval/test_label_sensitivity.py` (6).

### 2. Scoring metrics (`eval/metrics/citations.py`, `eval/scoring/citation_scores.py`, columns in `engine.METRICS`, tables `table_citations` and `table_abstention`)
Definitions are in the module docstring. Nothing is an LLM judge.
| Metric | Where | Notes |
|---|---|---|
| M9 fabricated-citation rate | `fabricated_citations` | a citation is `[A:doc#para]` (inline, with an optional quotation before it) or an `authorities` entry; fabricated = (doc, para) not in the index, or the quotation not found (whitespace removed, ellipsis splits fragments). Index = the paragraph stores read-only (`SqliteParagraphIndex`) |
| M13 authority quality | `authority_quality` | share court reasoning, share Supreme Court, share dated before the order, over distinct cited paragraphs found in the index |
| M15 good-law violation + known-treatment share | `good_law` | overruled per the citation graph (`GraphTreatmentIndex`, read-only, `as_of` = the order date) and cited without warning wording; known treatment = at least one incoming edge with a treatment label other than UNKNOWN. Real dev run: 0 violations, known share 0 (the cited High Court paragraphs carry no treatment labels) |
| M16 citation precision and recall (ALCE style) | `citation_precision_recall` | support checker = MiniCheck if installed, else DeBERTa NLI, else the lexical stand-in; the table says `offline stand-in` and names the checker (`meta.checker`) |
| M17 citation faithfulness by removal | computation `removal_change`; arm `eval/runners/m17_removal.py` | the arm runs Full, then for up to 3 cited grounds rebuilds the factor's evidence pack without the first cited paragraph and redrafts with a fresh Vakeel; record gains `removal`. Smoked offline on 1 dev case (about 80 s/case on the stand-in drafter). Lower bound only |
| M18 stopping quality | `stopping_quality` | event-based: over-search share (calls in rounds after the first round with no MISSING or WEAK slot) and share of factors that stopped with a slot unfilled. The plan's "replay to the 16-call budget" (stopped-too-early) needs a re-run and is NOT computed |
| M33 coverage-risk curve and AURC | `coverage_risk_curve`, `engine._curve` | claims = factual sentences with their support scores (`unsupported_fact.sentence_support`); emitted at tau = passed the gate and score >= tau; risk = share below the M6 cut; AURC trapezoid with a case-bootstrap interval; a system with no gate (baselines) is "one point". Because risk uses the same score, risk is 0 at tau = cut by construction (stated in the table note) |
| M35 confident-wrong + the four cells | `confident_wrong` | emitted claims unsupported by the facts AND by the rest of the order (parts other than facts, `data/interim/t1_work/parts.jsonl`) |
- Pending policy: a metric whose resource is absent (stores, citation graph, the parts file) is None and named in `meta.pending` with the reason, but only when the case has something to measure; `--strict` raises. On a machine with `data/stores` nothing is pending.
- Tests: `test_citation_metrics.py` (11, hand-computed), `test_scoring_citations.py` (4), `test_m17_removal.py` (3), `test_workflow_search.py`.
- A real scoring pass of the six dev systems takes about 40 s (loads the order parts once).

### 3. Studies (`eval/studies/`, offline, zero cost; `python -m vakeel_sahayak.eval.studies <s14|s16|s4s5|m17> --out DIR [--n N]`)
- `s14` (S14b, S14c): scheduling simulation on the 300 T5 cases, policies fifo / urgency / urgency + least work / shortest first; one worker, 5 working hours a day, stages per case constructed from a hash of the case id (stated). Real result: fifo misses 66 of 100 planted deadlines, urgency and urgency+least-work 0; pairwise ranking accuracy 0.52 vs 1.00; planted order accuracy 0.977; cases per node-hour identical (4.02) by construction. Test: `test_studies_s14.py` (6).
- `s16` (S16, S16b): chunk strategies over a re-chunked sample (300 orders from the splitter's parts file; 292 queries per kind). G2 is not resolvable here (the 19 cited judgments are Supreme Court judgments whose text is not in the corpus file), so the result reports n = 0 for G2 and uses two self-supervised targets, labelled "NOT G2" in every output: first sentence of a reasoning paragraph, and the same with every third content word dropped. 85 s for n = 300. Test: `test_studies_s16.py` (3).
- `s4s5` (S4, S5): on the real stores. S4: AUROC of Gini and top gap of the top-10 scores (new `metrics/retrieval.auroc`, the M19 helper) for "top-10 contains a gold document"; S5: recall@10 with and without PPR expansion plus McNemar. Two query sets: `g2` (T1 dev/open facts with a resolved G2; thin, n printed, an AUROC is "undefined" with no negatives) and `proxy` (self-supervised: reasoning paragraphs that cite a judgment in the store, citation strings masked; the proxy favours S5 because its gold is the same cited-by relation S5 walks, stated in the output). About 2 s per query; 30-query trial: proxy recall@10 0.07 plain vs 0.50 expanded, AUROC (Gini) 0.89 on 2 positives (not a result). Test: `test_studies_s4s5.py` (4).
- `sweep_dev.yaml`: arms with `kind: study` (S14b, S14c, S16, S16b, S4-retrieval, S5-retrieval, M17-removal) run once per study through `scripts/sweep_dev.py run --phase 1`; the driver arms S4 and S5 (full pipeline with the switch) remain. The old SPECIAL set is gone.

### 4. S15b and S13
- S15b (`output_format='free_then_parse'`): built in `orchestration/structured_output.py` (that is where the plan puts S15's structured-output layer): inside `output_format('free_then_parse')` a structured call sends NO `json_schema` to the backend, appends a note that allows free text ending in one JSON object, and goes through the same parser and repair loop (so a reply that does not parse costs an extra attempt). Default path byte-identical (flag None; prompt and `json_schema` unchanged, tested). `eval/runners/systems.py` opens the scope for any run whose switches say `free_then_parse` and writes counters (`variant_signals.output_format`: calls, attempts, repairs) into the saved record and an event. S15b is now in `IMPLEMENTED_VARIANTS`, a job (`s15_output_format` systems S15 and S15b), an arm in `sweep_dev.yaml` (phase 3, could) and has an effect test in `tests/unit/eval/test_variant_effects.py`. Offline stand-in: the offline model still answers JSON from the schema in the prompt, so an offline S15b run shows the plumbing; the real effect needs a model. Test: `test_s15b_free_then_parse.py` (5).
- S13 workflow search: `workflow_search.py` already had the deterministic grid/random search; added `recall_evaluator` (dev reward = factor recall M1 against agreed G1, the same as scoring), `assert_offline` (refuses a hosted or local backend: the model-backed arm stays planned) and a CLI `python -m vakeel_sahayak.eval.runners.workflow_search --cases data/testsets/t1/dev.jsonl --n 3 --max-configs 4 --out report.json [--grid small]`. The `s13_workflow_search` job now runs the offline smoke (3 cases, 4 grid points) instead of raising; the hosted arm raises `NotImplementedError` naming the reason. Tests in `test_workflow_search.py` (10).

### 5. `scripts/ada/*.sh`
No script was deleted; every `TODO` stub is now a thin wrapper over `scripts/ada/_common.sh` (checks `SHARD N_SHARDS`, puts `src` on PYTHONPATH, sets `VS_MODELS=auto VS_LLM_BACKEND=local VS_EXTERNAL=off` unless overridden, `OUT`, `HOURS`, `PY`/`VS_VENV`): `run_rq1`, `run_ablations`, `run_a5_extractors`, `run_features`, `run_rq2_full`, `run_rq2_vision`, `run_t6_t7` call the Python runners; `run_shard.sh` takes `JOB=<job of runs.yaml>`; new `run_sweep_ada.sh SHARD N` runs `scripts/sweep_dev.py run --phase 4 --backend ada --shards N --shard-index SHARD` (new `--shard-index` flag of the sweep runner); `stage_to_scratch.sh` copies model folders and, with `STAGE_DATA=1`, public data to node scratch (refuses `data/cases`, `data/raw`); `tunnel_demo.sh` opens the SSH tunnel of `serve_qwen32b.sh`. `shard_runner.py` gained a `main()` (`--job`). Untouched: `serve_qwen32b.sh`, `sbatch_qlora.sbatch`, `run_teacher_dossiers.sh`, `fetch_qwen32b.sh`. Tests: `tests/unit/scripts/test_ada_scripts.py` (bash only, nothing heavy runs).

### 6. Registry
`IMPLEMENTED_VARIANTS` now equals the variant table (S15b added); the stale comments (module docstring, "EV-01 added every other S-id", "Ids whose behaviour exists today (S3 and the A1-A10 ...)", `implemented_variants()` docstring) are rewritten. Tests: `test_variant_registry_docs.py` (5; the map's sweep tables, the plan, the registry and the comments agree) and `tests/unit/scripts/test_sweep_dev.py` (7: every arm of `sweep_dev.yaml` is dispatchable or a declared study).

## Reconciled tests (`# RECONCILED`)
`tests/unit/eval/test_eval_jobs.py` (two tests that used S15b as the unbuilt example now take the id out of the registry with monkeypatch), `tests/unit/orchestration/test_switches.py` (S15b in the implemented set and the accepted list), and ONE assertion in `tests/unit/agents/vakeel/test_variants_reasoning_first.py` (it said S15b is not implemented). `tests/unit/eval/test_variant_effects.py` (another agent's untracked file) got an S15b effect test and its id in `COVERED`.

## For the lead
- Stale text in `docs/literature-to-code-map.md` (not edited, outside my list): line 29 says "S15b not built"; the whole "EV-01 switch table" (lines 62-87) still says "switch defined, behaviour not implemented" for ids that are built; `docs/preregistration.md` line 96 names S15b as unbuilt; `docs/handoff/eval-jobs.md` and `eval-scoring.md` still list M9, M15, M16, M17, M33, M35 as not built; `docs/evaluation-plan.md` 8.2/8.3 say `label_sensitivity.py` is a stub. `AGENTS.md` is fine.
- The Makefile `eval-score` target can pass `SCORE_ARGS="--second-labeler data/interim/gold_candidate"`.
- Run order for the offline phase 1 (zero cost): `scripts/sweep_dev.py run --phase 1 --arms s14,s16,s4s5` (minutes), then `--arms m17` (20 cases about 30 min with 4 shards), then the driver arms.

## Still needs a model (or is not computed)
- M16 and M6/M33/M35 numbers are only meaningful with MiniCheck or the DeBERTa NLI (`pip install minicheck` / `.[nli]` and `VS_NLI=auto`); offline they carry the lexical stand-in label.
- M17 on a hosted or local drafter (the arm is built and smoked offline) and S15b on a real model.
- S13's model-backed evaluation arm (the harness and recall evaluator are built; offline smoke only).
- M18 stopped-too-early (needs a replay to the 16-call budget), and true late chunking (token vectors from BGE-M3) in S16b.

## How to check
```bash
.venv/bin/pytest tests/unit/eval tests/unit/scripts tests/unit/orchestration -q -p no:cacheprovider
.venv/bin/python -m vakeel_sahayak.eval.scoring score --runs data/eval/dev_runs --out <dir> --gold-source both --allow-mixed-code --second-labeler data/interim/gold_candidate
.venv/bin/python -m vakeel_sahayak.eval.scoring report --scores <dir>
```
