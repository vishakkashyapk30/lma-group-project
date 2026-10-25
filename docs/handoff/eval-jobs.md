# VI-03: evaluation jobs, one entry for every variant (handoff)

Date 2026-10-26. Nothing committed. Files: `src/vakeel_sahayak/eval/runners/{systems,driver,plan,jobs}.py`, `configs/eval/runs.yaml`, `docs/preregistration.md`, `scripts/prereg_hash.py`,
`tests/unit/eval/test_eval_jobs.py`, one fix in `agents/peshkar/agent.py`.

## Done
- **One entry**: `driver run --system <id>` (`systems.system_runner`). Ids: `full`, `b0 b0l b0s b1 b2 b3 b4 b6`, every id of `Switches.implemented_variants()` (A1-A10, S1-S18, B5, P5-P8 and the plan aliases), with
  `A5:base_4b|prompted_32b`, `A10:<store>` and `S13:<field>=<value>` taking an argument. A declared but unbuilt id (only `S15b`) exits 2 / raises `NotImplementedError` naming the variant; an unknown id lists the valid ones.
- **Manifest** (`MANIFEST.json`) now also records `describe` (`Switches.describe()`), `prompt_hash` (SHA-256 over `models/prompting.py` and every `agents/**/prompts.py`), and `scope` (what the variant changes in a per-case run).
  Read it before reading a null result: `S14b`, `S14c`, `S16`, `S16b` are inert in a per-case run (scheduler, chunking study); `S7`, `P5`-`P8` act only on cases with a bundle.
- **S14 and S14d** now get one shared in-memory `RetrievalCache` for the whole run (`driver.shared_cache_for`; `build_context(cache=)`), because both need a batch. The default run is unchanged (no cache).
- **`driver plan --job a[,b] | --all | --sarvam-full`**: cases, systems, runs, tokens, USD on gpt-6-luna, INR on Sarvam-105B (dashboard prices), hours; runs nothing. Sums spend per hosted backend and warns above a cap.
  The Sarvam cap is `VS_SARVAM_CAP_INR` or `budgets.sarvam_cap_inr` (25); `--sarvam-full` prices everything on Sarvam and gives the credits needed (about INR 7,350 for all jobs, tier A about 5,200; B1, B4, S-arms use ratio 1.0 where not measured).
- **`driver smoke-all`**: every dispatchable id offline on the first T1 dev case with a pass/fail table (see below).
- **`configs/eval/runs.yaml`**: a job for every implemented variant (plan 7.2 rows 15-33 plus carve-outs), `estimate:` (measured numbers of `data/eval/token_measure.json`), `token_ratio`, `priority`, `job_meta`
  (tier, backend, status, covers, note), `exclusions` (S15b) and `budgets:` (caps and the Sarvam price table). Existing entries are unchanged.
- **Validator tests** (`tests/unit/eval/test_eval_jobs.py`, 22): every implemented id has a job or an exclusion, every declared-but-unbuilt id is excluded, every job system dispatches, hosted blocks fit their caps, plan and manifest content.
- **Bug fixed** in `agents/peshkar/agent.py` (lines 829, 861): `self.error(..., kind=res.kind)` collided with `error(kind, ...)` and raised `TypeError` whenever `rights_check` or `diff_case_state` returned a tool error (A3 refuses `rights_check`, so the whole Peshkar stage of A3 failed). The detail is now `tool_error=`.
- `docs/preregistration.md` is the template (freeze record, claims C1-C42 with defaults, tests, families, blind slice, what may change). `scripts/prereg_hash.py` prints the blind-set hash and writes nothing.

## Backends and caps (owner decisions of 2026-10-26)
- OpenAI gpt-6-luna, 4.50 USD default cap (5.00 hard): one coherent block, `openai_sparring_block` = Full, A2, A8, A9, S8, S9 on the first 100 cases, about 4.0 USD at 0.0078 USD per Full case.
- Sarvam-105B, INR 25 by default (more credits may come; set `VS_SARVAM_CAP_INR`): INR 15 / 5 / 60 per 1M tokens (input / cached / output), so a Full case is about INR 1.15. `rq1_secondary_sarvam` (Full, B1, B4 on 6 cases, about INR 21) is a path and cost check, not a result.
  RQ1 main x3 (about INR 2,100) and the ablations on 100 cases (about INR 760) do not fit INR 25: they stay on Ada or on reduced floor sizes unless the Sarvam cap is raised.
- Everything else generative is `ada` (Qwen), `deferred` for tiers B, C and X. Fine-tuned 4B (A5), QLoRA and any local scoring stay on Ada. An arm is only comparable with Full on the same backend: each hosted block carries its own Full run.
- **A Sarvam spend ledger with a hard cap is required before any Sarvam run** (`models/sarvam`; OpenAI has `models/openai/ledger.py`, Sarvam has nothing). It must read the cap from the environment (`VS_SARVAM_CAP_INR`), refuse the call that would pass it, and record tokens per call so `measure_sarvam_cost` can replace the assumption that Sarvam uses the same token counts as gpt-6-luna. No Sarvam run is to be started until it exists.
- Disclosure: before that instruction arrived one 1-case `driver run --system full` was started with `VS_LLM_BACKEND=sarvam`. It made no Sarvam call and spent nothing: `.env` sets `VS_SARVAM=off`, which beats `VS_EXTERNAL`, so every call fell back to the local runtimes (40 `model_unavailable` events, 0 tokens). The output is only in the scratchpad.

## Hosted commands (for when the ledger exists)
Load keys from the untracked `.env` only. `.env` sets `VS_SARVAM=off`, `VS_EXTERNAL=off`, `VS_DATA_DIR` and `VS_LLM_BACKEND`: export the values below AFTER loading it.
```
bash -c 'set -a; . ./.env; set +a; export VS_MODELS=auto VS_LLM_BACKEND=sarvam VS_SARVAM=pseudonymised VS_EXTERNAL=pseudonymised VS_SARVAM_CAP_INR=25 VS_NLI=offline; exec .venv/bin/python -m vakeel_sahayak.eval.runners.driver run --system full --cases data/testsets/t1/dev.jsonl --n 1 --out <dir>'
```
OpenAI: the command of `docs/handoff/pilot-hosted-model.md` with `VS_LLM_BACKEND=openai`; then `driver run --system <id> --cases data/testsets/t1/cases.jsonl --n 100 --out data/eval/runs/<job>/outputs/<id>` per system of the job, or `python -m vakeel_sahayak.eval.runners.run_rq1 ...` for the existing jobs.
The driver pseudonymises each case's facts like the production intake (`file_facts`); `VS_EXTERNAL=pseudonymised`, not `public`.
Plan first: `.venv/bin/python -m vakeel_sahayak.eval.runners.driver plan --job openai_sparring_block,rq1_secondary_sarvam`.

## smoke-all (what `make eval-smoke` should run)
`.venv/bin/python -m vakeel_sahayak.eval.runners.driver smoke-all` (offline forced, scratch data dir with `data/stores` linked read-only, about 40 s per id, 60 ids, about 40 minutes; `--ids a,b` for a subset, `--stores empty` for speed, `--json F`).
Exit code 0 only when every id passes (S15b passes by being refused). Result table of the final run: see the report; the log of the run is not kept in the repo.

## Not done
- Case rows for T2, T5 and T7 (`<testsets>/t2|t5|t7/driver_cases.jsonl`): `jobs.testset_cases_path` raises `NotImplementedError` naming the path, so `s7_gap_reread`, `s17_defences`, `p_munshi_variants` and `s14_scheduling` cannot start until the builders (or an adapter) write them.
- S16/S16b have no per-case effect (chunking study only: `compare_strategies` needs docs and G2 queries; `oil_metadata.jsonl` is missing). S14b/S14c are measured on T5 through the batch desk. S13 has no model-backed evaluator (`runner: workflow_search` raises).
- S15b is not built (`agents/vakeel/agent.py`), listed under `exclusions`.
- Token ratios of B1, B4, A10 and the unlisted systems are 1.0, not measured; Sarvam token counts are assumed equal to gpt-6-luna's.
- Metrics and statistics (`eval/metrics`, `eval/stats`, Harshita's stubs): the driver only runs cases. Scoring needs `factor_scores`/`unsupported_fact` (C1, C2), `retrieval` (C5, C14), `agentic`, and `stats.{bootstrap,wilcoxon,holm}` plus McNemar and a cluster bootstrap that do not exist yet.

## Next steps
1. Lead: wire `make eval-smoke` to `smoke-all` (and keep `make smoke`); the Makefile is not mine to edit here.
2. Build the Sarvam ledger, then run `plan --job ...` and the hosted blocks; `measure_sarvam_cost` on 3 dev cases first.
3. Freeze: fill `docs/preregistration.md` section 0, run `scripts/prereg_hash.py`, tag.
