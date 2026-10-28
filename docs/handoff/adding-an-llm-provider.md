# Adding an LLM provider: a yaml block and an environment variable

Date 2026-10-28. Code: `src/vakeel_sahayak/models/registry.py` (the provider list), `src/vakeel_sahayak/models/hosted/` (client, key pool, request ledger, protocols, planner, probe). Tests: `tests/unit/models/test_hosted_gemini.py` (a made-up provider `acme` is added by an override file alone and run against a fake transport: `test_a_made_up_provider_runs_from_yaml_alone`).

## The rule
To add a provider you add a block under `providers:` in `configs/models.yaml` (or, for a personal or experimental one, in the untracked `configs/providers.local.yaml`, or a file named by `VS_PROVIDERS_FILE`), put its key in an environment variable, and select it:

- `VS_LLM_BACKEND=<name>` for the agent roles (evaluation cases only if the provider is `public_only`),
- `VS_LABELER=<name>` for the gold labeler, `VS_TEACHER=<name>` for the teacher (both public orders only),
- `python -m vakeel_sahayak.pipelines.gold.agreement run --labeler <name>`.

No code change. The privacy gate (`sarvam/policy.py authorize`), the paid lock (`models/paid_lock.py`), the factory fallback, the run manifest (`describe_run_models()["hosted"]`), the request ledger and `make gemini-usage PROVIDER=<name>` all read the block.

## The fields
| field | meaning |
|---|---|
| `protocol` | `openai_compat` (any `/chat/completions` service) or `gemini_native` (`generateContent`). `builtin` marks openai and sarvam, which keep their own adapters. |
| `base_url`, `chat_path`, `api_version` | where requests go. `openai_compat`: `<base_url><chat_path>` (default `/chat/completions`); `gemini_native`: `<base_url>/<api_version>/models/<model>:generateContent`. |
| `auth_header`, `auth_scheme` | the header that carries the key and its prefix (`Authorization` + `Bearer`; Gemini: `x-goog-api-key` + empty). The key is never put in a URL. |
| `key_env` | the env variable with the key; default `<NAME>_API_KEY` in capitals. A pool: `<key_env>S` (comma separated) or `<key_env>_1 .. _N`. One key per project: limits are per project. |
| `free`, `paid` | `paid: true` puts the provider behind the paid lock (`VS_ALLOW_PAID=<name>` unlocks; only with the owner's go-ahead). |
| `data_class_allowed` | `public_only` (free tiers: public data and the driver's public-source cases; client data refused in every mode, consent cannot unlock it), `pseudonymised` (never raw client data), `consented` (as OpenAI and Sarvam: mode plus counsel's consent decide). |
| `mode_env` | the provider's own mode variable (e.g. `VS_GEMINI`); else `VS_EXTERNAL` applies. Consent events are `<name>_consent`. |
| `structured` | `schema` (provider-side JSON schema), `json_mode` (JSON output, schema written into the prompt) or `prompt` (schema in the prompt only). A 400 naming the feature moves to the next weaker mode; the ledger remembers it per model. |
| `system_instruction` | `false`: the system text is folded into the first user turn (Gemma on the Gemini API). |
| `thinking` | `gemini_native`: `{budget: 0}` or `{level: low}` (thinkingConfig); `openai_compat`: extra body keys such as `{reasoning_effort: low}`. Dropped automatically when the model rejects it. |
| `max_tokens_field`, `max_tokens_cap` | `max_tokens` or `max_completion_tokens`; the answer-limit cap. |
| `default_model`, `roles`, `failover` | model ids; `roles: {agents, labeler, teacher, b0l}`; `failover` is used only with `VS_HOSTED_FAILOVER=1` (never inside a paired comparison). `VS_<NAME>_MODEL` pins the agents' model, `VS_<NAME>_LABELER_MODEL` the labeler's. |
| `limits`, `models.<id>` | `rpm`, `rpd`, `tpm` per MODEL (provider `limits` is the fallback; env `VS_<NAME>_RPM/RPD/TPM` overrides). A request larger than the model's TPM is refused before sending. Per model you may also set `family`, `system_instruction`, `structured`, `thinking`. |
| `family` | model family for the rule that labeler, teacher and judged system differ (default: from the model id). |
| `quota_day_tz` | time zone of the daily counter (default UTC; Google resets at midnight Pacific). |
| `timeout_s`, `retries`, `learn`, `max_wait_s` | transport timeout; 5xx backoff (`max`, `base_delay_s`, `max_delay_s`, `jitter_s`); how far and how long a 429 lowers the rate; the longest per-minute wait. |

## Worked example 1: Gemini through its OpenAI-compatible endpoint
Put this in `configs/providers.local.yaml` (it shares the Gemini key; note that its ledger rows are counted under `gemini_openai`, apart from `gemini`, although Google counts both against the same project quota, so use one name per project at a time):
```yaml
providers:
  gemini_openai:
    protocol: openai_compat
    base_url: https://generativelanguage.googleapis.com/v1beta/openai
    auth_header: Authorization
    auth_scheme: Bearer
    key_env: GEMINI_API_KEY
    mode_env: VS_GEMINI
    free: true
    paid: false
    data_class_allowed: public_only
    family: gemini
    structured: schema
    default_model: gemini-3.1-flash-lite
    models: {gemini-3.1-flash-lite: {rpm: 15, tpm: 250000, rpd: 500}}
```
Then `VS_MODELS=auto VS_GEMINI=public VS_LABELER=gemini_openai ...`.

## Worked example 2: a paid OpenAI-compatible service
```yaml
providers:
  acme:
    protocol: openai_compat
    base_url: https://api.acme.example/v1
    free: false
    paid: true                       # locked until VS_ALLOW_PAID=acme
    data_class_allowed: pseudonymised
    structured: json_mode
    default_model: acme-small
    models: {acme-small: {rpm: 60, rpd: 1000, tpm: 100000, family: acme}}
```
Key in `ACME_API_KEY` (the default `key_env`). A paid provider's cost is NOT capped in money by the generic ledger (it counts requests and tokens only); a provider that costs money should stay locked unless the owner agrees and sets limits low enough.

## Not done
- No money cap for generic paid providers (only the OpenAI and Sarvam adapters have spend ledgers). Mark such providers `paid: true` so they stay locked.
- Async calls: the generic client is sync only (the gold runner uses threads).
- Vision, speech and translation through generic providers: LLM chat only.
