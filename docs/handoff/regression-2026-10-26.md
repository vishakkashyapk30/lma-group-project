# Regression, 26 October 2026 (Vishak)

## Sutradhar bug behind the 2 failing `tests/unit/api` chat tests (fixed)
Two causes, both found through `tests/unit/api/test_chat_router.py`:
1. **Poisoned argument-model cache (`tools/registry.py`, co-fix; the file is not listed in the ownership table).** `_args_model(name)` is `@cache`d and built from `get_tool(name)`. The system harness (`tests/system/_helpers.Scenario._patch_wiring`) replaces `get_tool` with the fake toolbox, whose wrappers are `call(*args, **kwargs)`; the model built from them had no fields and `extra="forbid"`, so every real call to `date_calc` or `map_section` failed with "start: Extra inputs are not permitted" (this also cached the empty model for later tests in the same process). Fix: build the model from the discovered real function (`_discover()[1]`), not from `get_tool`. Default behaviour is unchanged.
2. **Custody days counted to today (`agents/sutradhar/factor_pick.py`).** The dossier folded from the event log has `as_of=None`, so `plan_context` fell back to today's date (797 days instead of 167). `signals_from_dossier` now uses `rights.as_of` when the dossier has none (the Rights Radar was counted to a date). A dossier with its own `as_of` is unchanged.
Regression tests: `tests/unit/agents/sutradhar/test_args_model_not_poisoned.py` (2). `tests/unit/api`: 119/119 pass, `tests/unit/agents` all green, ruff clean on the touched files.

## Test-set manifests (task 2)
Rebuilt with `SETS="t3 t6"` and `SETS="t2 t8" scripts/build_testsets.sh`: `t2`, `t3`, `t6`, `t8` `manifest.json` now record `source_cases_sha256 = 40366c9e...b958a1` (the agreed-gold `t1/cases.jsonl`; before: `ab5ce389...` = rule-only). No other non-PDF file changed (T2 `truth.jsonl`, `driver_cases.jsonl`, T3/T6/T8 data files byte-identical). All 600 T2 PDFs differ in bytes only because the PDF trailer `/ID` is random per build (no creation date; text and truth unchanged). T7 and `driver_cases` do not record the T1 hash (not rebuilt). T4, T5, T9 do not read T1.
T1 selection and gold: `build_t1_with` uses the gold only through `_clean`, which drops an order whose `doc_id` is missing from any of g1..g7; label values and status are never read for selection, so the selected ids, ordering and blind slice are identical under the agreed and the rule-only gold (as long as both cover the same doc ids, which `test_gold_source.py` checks).

## Broad regression (task 3)
Run per test file in the background (`setsid nohup`, 10-minute timeout per file; the full-tree run hung on an SSE test) on the tree before Shravani's `de93b64`, so the metrics/stats rows below are stale (Harshita's tests now pass except 3 Wilcoxon tests in `test_stats.py` and 3 helper tests in `test_ingestion_pipelines.py`, per the lead).
Total: 4,288 passed, 315 failed, 9 errors, 38 skipped, 2 files timed out.

| Area | Owner | Result | Cause |
|---|---|---|---|
| tests/unit minus the rows below (agents, batch, config, contracts, ingestion, models, orchestration, pipelines, privacy, record, rights, schemas, stores, testsets, tools*, truth_maintenance, api) | Vishak/Shravani | all pass | |
| tests/unit/eval `test_metrics`, `test_stats` | Harshita | 36 + 16 failed (before `de93b64`; now only 3 Wilcoxon) | stubs |
| tests/unit/eval `test_ingestion_pipelines` | Harshita | 3 failed | `by_kind`, `escalation_rate`, `questions_asked` missing in `eval/metrics/ingestion.py` |
| tests/unit/export | Satvik | 26 failed, 9 errors (27 skipped) | export stubs |
| frontend tests | Satvik | not run (old design) | |
| tests/unit/finetune | Vishak | 82 failed | the QLoRA pipeline is still stubs (`NotImplementedError`, `finetune.teacher_dossiers.{choose_teacher,assert_family_rule,verified_pairs_per_day}` missing); 2 of them assert the `scripts/ada` sbatch list and now see the new untracked `serve_qwen32b.sbatch`. Not a regression; building it is a separate task |
| tests/integration | Shravani | 43 failed, 74 passed; `test_api_routes.py` timed out in the SSE test | see below |
| tests/system | Shravani | 109 failed, 157 passed; `test_flow6_batch_desk.py` timed out | see below |

Integration/system root cause (diagnosed on `test_api_routes::test_every_tab...`; not fixed, harness-side): after `through_gate1` and `through_draft` the case is still at stage INTAKE with 24 Peshkar `extract_field` errors ("no JSON value found in the reply"), because `Scenario`'s laptop client is `ScriptedLLM(default="")` and the real Peshkar reads each field through the model task `peshkar.extract_field`, not through the fake `extract_dossier` tool the harness expects; the empty dossier then gives Sutradhar 8 `reword_query` failures and no brief ("no brief yet" 404). Fix belongs in `tests/system/_helpers.py` (Shravani): give the laptop client the offline handler for `peshkar.extract_field` (or script the replies). Almost all of the 152 failures probably share this cause; the SSE hang is in `api/sse` follow mode (Shravani).
