# Gemini free tier, the paid lock and the provider registry (handoff)

Date 2026-10-28. No key was available while this was built: everything is tested offline against `httpx.MockTransport`; **no request has been sent to Google**, and no number below is measured on Gemini.

## Why
1. A third model family for the gold labeler, independent of the OpenAI system under test (design review 2026-10-27, finding 3: the labeler `gpt-6-luna` is the same model as the system).
2. A hosted agent arm (and B0L) that costs nothing, now that the paid providers are locked.
3. Cross-family checks of the gold labels.

## Done
- **Paid lock** (`models/paid_lock.py`, owner decision 2026-10-28): OpenAI and Sarvam refuse every call unless `VS_ALLOW_PAID=openai,sarvam` names them. Checked in the gate, the spend-ledger entry points and the HTTP transports: a locked call sends nothing and writes no ledger row. The factory treats a locked provider like one that is off (local client answers); `driver`, `eval.studies`, the labeler, the teacher, `scripts/sweep_dev.py` and `scripts/sweep_{openai,sarvam}_block.sh` refuse at once with the message naming the unlock. Sweep arms with `status: locked|blocked|moved` are never launched. Tests: `tests/unit/models/test_paid_lock.py`.
- **Providers by configuration** (`models/registry.py`, `models/hosted/`): see `adding-an-llm-provider.md`. Protocols `gemini_native` and `openai_compat`.
- **Gemini block** in `configs/models.yaml` `providers.gemini`: `generateContent`, key in header `x-goog-api-key`, `data_class_allowed: public_only`, mode variable `VS_GEMINI`, thinking budget 0, structured output with `responseMimeType: application/json` + `responseSchema` (JSON Schema converted to Gemini's OpenAPI subset; when a schema cannot be expressed, JSON mode only; on a 400 JSON in the prompt), then the existing validation and repair loop.
- **Privacy**: the gate refuses CLIENT_TEXT and CLIENT_RAW for Gemini in every mode, consent included, with a message saying why; PUBLIC data and the evaluation driver's public-source cases (`public_source_scope`, T1 and constructed cases, still pseudonymised and boundary-checked) pass. Product cases on `VS_LLM_BACKEND=gemini` therefore always fall back to the local client.
- **Key pool**: `GEMINI_API_KEY`, or `GEMINI_API_KEYS=k1,k2`, or `GEMINI_API_KEY_1..N`. Keys appear only in the header; logs, ledger, reports and errors show a fingerprint `k-xxxxxxxx` (first 8 hex digits of the SHA-256). **Limits are per Google Cloud project, not per key**: list one key per project (each teammate's own free-tier project); two keys of one project do not add quota, and the ledger cannot tell.
- **Request ledger** (`models/hosted/quota.py`, `<data>/hosted/quota.sqlite`): per provider, key fingerprint and model; reserve before every call; rpm window plus 60/rpm spacing, tpm window, rpd per quota day; a full day raises `HostedQuotaExceeded` (alias `GeminiQuotaExceeded`), which the factory turns into the local fallback; 429 per minute lowers the key's rate (factor 0.5 for an hour) and keeps Retry-After / RetryInfo; 429 per day (QuotaFailure `...PerDay...`) blocks the key until the next midnight Pacific; 500/502/503/504 back off 2, 4, 8 ... s (max 60, 5 retries) with jitter; 401/403 drops the key for the process. Keys rotate on 429 and full days; the client waits only when every key must wait (at most `max_wait_s` 900 s, then `HostedRateLimited`). A request larger than the model's TPM is refused before sending (Gemma: 16K), and the answer limit is lowered to fit when only it overflows.
- **Quota day**: counted in `quota_day_tz` (default UTC, as asked). Google resets at midnight Pacific, so with UTC our day starts 7 or 8 hours before Google's; set `quota_day_tz: America/Los_Angeles` to follow Google exactly. A per-day 429 is honoured either way.
- **Per-model limits** as shown in Google AI Studio on 2026-10-28 for one free-tier project (RPM / TPM / RPD): Gemini 3.1 Flash Lite and 3.5 Flash Lite 15 / 250K / 500; Gemma 4 26B and 31B 30 / 16K / 14,400; Gemini 2.5 Flash Lite 10 / 250K / 20; Gemini 2.5 Flash, 3 Flash, 3.6 Flash, 3.8 Flash 5 / 250K / 20. Pro models, Gemini 2, 2 Flash Lite and Gemini 4 Argon show 0. **Re-check in AI Studio; they change.** Env `VS_GEMINI_RPM/RPD/TPM` overrides.
- **Model ids are guesses from the AI Studio display names** (`gemini-3.1-flash-lite`, `gemma-4-31b-it`, ...). `make gemini-models` lists the exact ids each key can use (GET `/v1beta/models`) and names the configured ids that are missing.
- **Modes**: Gemma on the Gemini API may refuse system instructions and JSON mode. Configured Gemma models start with the system text folded into the user turn and JSON in the prompt; for any model a 400 naming the feature switches the mode, which the ledger remembers per model and the manifest records (`hosted.gemini.modes`). `make gemini-models MODEL=<id>` sends ONE public smoke request (system instruction + JSON schema) and prints the mode that worked.
- **Failover and the planner** (`models/hosted/planner.py`, `scripts/gemini_quota_plan.py`, `make gemini-plan`): days per model by RPD and by tokens per day (TPM x 1440), the model that finishes soonest, a day-by-day failover split, and warnings when a paired comparison mixes models. Failover is opt-in (`VS_HOSTED_FAILOVER=1`) and must not be used for paired arms; the ledger records the model of every call and the manifest has `hosted.gemini.run_models` (settled calls per model of the run).
- **Wiring**: `VS_LLM_BACKEND=gemini` (agent roles), `VS_LABELER=gemini` (family `gemini`, so the family rule against an OpenAI system holds and against a Gemini system fails), `VS_TEACHER=gemini` (public orders), B0L on `roles.b0l` (`gemini-3-flash-preview`), `--labeler gemini` in the gold agreement runner, `hosted_backend()` for the baselines, the workflow-search ledger state (requests). Run manifests: `roles.*.provider/model/family/version`, `hosted.gemini` (protocol, limits, quota today per key, modes, run models), `paid_lock`.
- **Resumability**: the gold runner stops submitting after a `QuotaExceeded` error and prints how many orders remain; failed orders are redone on the next run. The driver checks the requests left before each case, stops when none are left, and never saves a case during which a call hit the daily quota (that case was partly answered by the local fallback); the next run resumes from it.
- `make gemini-usage` (today's requests, tokens, remaining per key and model), `make gemini-models [MODEL=<id>]`, `make gemini-plan ARGS=...`. `.env.example` lists `GEMINI_API_KEY`, `VS_GEMINI`, `VS_ALLOW_PAID`.

## How to run (once a key exists)
```
# .env (untracked): GEMINI_API_KEY=...   or GEMINI_API_KEYS=key_of_project_1,key_of_project_2
set -a; . ./.env; set +a
make gemini-models MODEL=gemma-4-31b-it            # exact ids per key; one public smoke call; prints the mode that worked
make gemini-plan ARGS="--n 250 --calls-per-item 6 --tokens-per-call 2500"     # gold labelling of 250 orders x 6 tasks
VS_MODELS=auto VS_GEMINI=public .venv/bin/python -m vakeel_sahayak.pipelines.gold.agreement run --labeler gemini --task g1 --n 20 --workers 2 --out data/interim/gold_candidate
VS_MODELS=auto VS_LLM_BACKEND=gemini VS_GEMINI=pseudonymised VS_GEMINI_MODEL=gemma-4-31b-it .venv/bin/python -m vakeel_sahayak.eval.runners.driver eval-smoke --n 1 --out /tmp/g1
make gemini-usage
```
The driver needs `VS_GEMINI=pseudonymised`: its agent calls carry pseudonymised public-source text (class CLIENT_TEXT with the public-source basis), which needs that mode rank; the gate still refuses any product case.

## Sweep plan on Gemini (configs/eval/sweep_dev.yaml, phase 5)
The OpenAI phase 2 and Sarvam phase 3 arms are `status: locked, moved_to: gemini`. Phase 5 runs them, with its own Full and baselines, on ONE model for every paired arm: `gemma-4-31b-it` (the model that finishes soonest; 16K TPM per request). B0L runs on `gemini-3-flash-preview` by design (unpaired). Requests are estimated from the gpt-6-luna Full pilot (47 calls and 74,228 tokens a Full case, pilot-4f; one call x 1.3 for the single-call baselines), at the configured limits, ONE project (`scripts/gemini_quota_plan.py --sweep --phase 5`):

| group | requests | tokens | gemma-4-31b-it, 1 project | 4 projects | gemini-3.1-flash-lite, 1 project | 4 projects |
|---|---|---|---|---|---|---|
| 50-case dev baselines (full, b0, b1, b2, b3, b4) | 6,360 | 11.2 M | 1 day (about 12 h of pacing) | 1 day | 13 days | 4 days |
| ex-phase-2 arms (A1, A2, A3, A6, A7, A8, A9, b2, b3) | 13,780 | 22.5 M | 1 day (about 23 h, TPD-bound) | 1 day | 28 days | 7 days |
| ex-phase-3 arms (S1, S3, S3b, S8, S9, S10, S11, S15, S15b) | 15,450 | 24.4 M | 2 days | 1 day | 31 days | 8 days |
| whole phase 5 (b2, b3 counted once) | 35,460 | 57 M | 3 days | 1 day | 71 days | 18 days |
| b0l on gemini-3-flash-preview | 65 | | 4 days (20 RPD) | 1 day | | |

These are planning figures, not measurements: Gemma's replies (JSON in the prompt, no system instruction) may need more repair calls, and a Full case of about 74K tokens takes at least 4.6 minutes at 16K TPM. The first real arm should be a 3-case smoke, then `make gemini-usage` for the real request count per case.

## Not done / open
- Nothing has been sent to Google. Model ids, the acceptance of `thinkingBudget: 0` by Gemini 3.x and Gemma, Gemma's JSON quality and the real limits are unverified.
- The generic client is sync only; no async bulk path.
- `gemini` and an OpenAI-compatible Gemini entry would be counted apart although Google counts them together (use one per project).
- The ledger cannot tell when two keys belong to one project.
- The quota day defaults to UTC as asked; consider `America/Los_Angeles`.

## The owner must supply
1. One `GEMINI_API_KEY` per teammate project (in each person's untracked `.env`, or all in `GEMINI_API_KEYS` on the machine that runs).
2. The exact model ids (`make gemini-models`) and confirmation of the chosen model (proposed: `gemma-4-31b-it` for the agent arms, `gemini-3.1-flash-lite` for the labeler, `gemini-3-flash-preview` for B0L).
3. The limits AI Studio shows for each project if they differ from 2026-10-28 (edit `providers.gemini.models` or set `VS_GEMINI_RPM/RPD/TPM`).
4. The go-ahead to run phase 5, and whether to set `quota_day_tz: America/Los_Angeles`.
