# VI-04: non-Qwen gold labeler (G1, G3) and the Sarvam spend ledger (handoff)

Date 2026-10-26. Nothing committed. Task A (Sarvam ledger) was the prerequisite; Task B is VI-04.

## Task A: Sarvam spend ledger (hard cap, INR)
Files: `models/sarvam/spend.py` (new), `models/sarvam/{api,config,errors,adapters,__init__}.py`, `configs/models.yaml` (`sarvam.ledger`, `prices_inr_per_1m`, `prices_inr_per_10k_chars`), `tests/unit/models/test_sarvam_spend.py` (15 tests), one reconciled line in `tests/unit/models/test_sarvam.py`.
- **Design (mirrors `models/openai/ledger.py`)**: SQLite `<data>/sarvam/ledger.sqlite`, integer micro-INR. `SarvamLedger.reserve` takes `BEGIN IMMEDIATE`, sums spent plus reserved over all processes and threads, and raises `SarvamBudgetExceeded` (alias `BudgetExhausted`; a `SarvamError`, so `FALLBACK_ERRORS` and `FallbackLLM` answer locally) before any HTTP request when `spent + worst case > cap`. Worst case = UTF-8 bytes of the request x input price + `max_tokens` x output price. Settled from `usage`; an HTTP error response releases the reservation; a transport failure keeps it as `unknown`. A ledger file that cannot be opened refuses the call.
- **Cap**: `VS_SARVAM_CAP_INR`, else `configs/eval/runs.yaml budgets.sarvam_cap_inr` (25), else `sarvam.ledger.default_cap_inr`. No hard maximum in code (credits may be added). Per-run cap `VS_SARVAM_RUN_CAP_INR` (run id `VS_SARVAM_RUN_ID`, else per process).
- **Prices** (`configs/models.yaml`, dashboard 2026-10-26, per 1M tokens input/cached/output): Sarvam-105B 15/5/60, MiMo V2.6 Flash 12.5/0.25/25, MiMo V2.6 Pro 40/0.3/80, DeepSeek V4.1 Flash 25/0.5/105, GLM 5.3 Flash 13.5/2.5/45, Gemma 4 35/10/90. A model with no price is refused. Character-priced endpoints (translate, transliterate, language id, TTS) are metered in the same ledger at INR per 10,000 characters: 20, 20, 3.5, 30. **These four numbers are my rounded-up guess, not from the dashboard; please correct them.** Speech-to-text and Vision digitise are not metered (priced per audio hour and per page).
- **Cache**: temperature-0 chat answers are cached (`<data>/sarvam/cache.sqlite`, reuses the OpenAI `ResponseCache`); a hit sends nothing, costs 0 and is recorded as a `cache` row. `VS_SARVAM_NO_CACHE=1` turns it off for measurements. `SarvamApi.chat` and `AsyncSarvamApi.chat` accept `purpose=` and `case_id=` (ledger labels; `SarvamLLMClient` now passes the scope's purpose).
- **Report**: `python -m vakeel_sahayak.models.sarvam.spend [--json]`. **Makefile line for the lead** (I did not edit the Makefile):
  `sarvam-spend:    ## Sarvam spend ledger: total spent (INR), remaining, per model, kind and purpose` then a tab and `$(PY) -m vakeel_sahayak.models.sarvam.spend` (add `sarvam-spend` to `.PHONY`).
- **Reconciled test**: `test_agent_role_configured_sarvam_is_wrapped_ada_side_and_pseudonymised_only` configured the agent role with a Qwen model name on the Sarvam client; the ledger refuses an unpriced model, so the role now names `sarvam-105b` (marked `# RECONCILED`).
- Real behaviour seen: a 400 from the API (wrong model id) was released and cost INR 0; run cap refusal worked live (below).

## Task B: labelers, agreement, candidates
Files: `pipelines/gold/span_labeler.py` (prompts, JSON schemas, span validation), `pipelines/gold/agreement.py` (agreement, kappa with bootstrap, coverage, rule-only comparison, runner, CLI), `models/labeler.py` (`EvalLabeler(backend='openai'|'sarvam')`, `client()` now also refuses system callers), `tests/unit/pipelines/gold/test_agreement.py` (20 tests, fake client, offline).
- **Labelers**: (i) the existing rules (`tag_factors` on the defense part for G1; `dossier_fields` plus `extract_dates` on the whole order for G3), (ii) OpenAI `gpt-6-luna`, public text only (`public_scope`, `VS_EXTERNAL=public`), temperature 0, structured JSON, OpenAI cache on. The model is NOT shown the rule candidates (the old design offered the rule labels for confirmation, which measures acquiescence); it labels independently.
- **Span grounding**: every label carries a verbatim span (8 to 600 characters). A span is rejected when empty, too short or long, or not found in the order (whitespace and case ignored); a section label needs its number in the span, a date label needs a written date in the span that normalises to the claimed date. Rejected labels are stored with a reason and never enter gold. G3 sections apply the same `charged_sections` filter as the rules.
- **Labels**: G1 = the 12 factors the defense argued. G3 = `sections=`, `arrest_date=`, `charge_sheet_filed=`, `previous_bail=`, `co_accused_bail=`, `trial_stage=`, `event=` (the rule label strings). `custody_days` is arithmetic on stated dates, not labelled by the model: it is kept as `rule_derived` on 30 of 250 G3 records and is not part of the agreed labels (so the candidate G3 omits it; the old G3 `fields` still carry it).
- **Per record**: `rule_labels`, `llm_labels`, `labels` (agreed = intersection, the plan's rule), `rule_only_labels`, `llm_only_labels`, `disagreement`, `llm_spans`, `rejected`, `status` (`agreed`, or `rule_only` when the labeler failed; provisional, not gold).

### Results (250 orders = 200 T1 + 50 dev; gpt-6-luna; bootstrap over orders, 1000 resamples)
| gold | orders | labeler answered | with agreed label | fully concordant | with disagreement | mean labels rule / labeler / agreed |
|---|---|---|---|---|---|---|
| G1 | 250 | 250 | 169 | 69 | 181 | 1.49 / 2.20 / 1.21 |
| G3 | 250 | 250 | 249 | 53 | 197 | 6.92 / 8.14 / 6.32 |

| gold | pooled kappa rule vs labeler | 95% CI | Dice |
|---|---|---|---|
| G1 | 0.598 | [0.554, 0.638] | 0.657 |
| G3 | 0.839 | [0.819, 0.857] | 0.840 |

Rule-only comparison (plan 5.9: rule-only, labeler-only, agreed): G1 rule-only 373 labels (192 orders with at least one), labeler-only 549 (229), agreed 303 (169); agreement keeps 81% of the rule labels. G3 rule-only 1,730 (249 orders), labeler-only 2,035 (250), agreed 1,581 (249); keeps 91%. The agreed G1 gold leaves 81 of 250 orders with no factor label (so "answerable" recall on those is undefined), and 70 order-factor labels the rules alone would have kept are dropped.

G1 by factor (kappa [CI]): antecedents 0.77, flight_risk 0.72, custody_period 0.66, charge_sheet_filed 0.62, health_age_family 0.63, parity 0.56, trial_delay 0.44, gravity_and_punishment 0.27 [0.03, 0.46], weak_prima_facie 0.25 [0.18, 0.33], witness_tampering 0.85 (n 10), statutory_bar 0.91 (n 6), undertrial_period 0 (rule 2, labeler 0: too few to read).
G3 by field: event 0.96, sections 0.81, co_accused_bail 0.70, arrest_date 0.66, trial_stage 0.55, charge_sheet_filed 0.48, previous_bail 0.26 (rule 7, labeler 41).

Disagreement types:
- G1 labeler-only is dominated by `weak_prima_facie` (101 of 249): the model counts "falsely implicated", "totally false", "no material" which the keyword rules miss; also `trial_delay` 32, `custody_period` 29, `charge_sheet_filed` 20 ("custodial interrogation is not required", which the rule only matches in some wordings). Rule-only is dominated by `parity_with_co_accused` (21: the rule fires on any mention of "co-accused", also when the co-accused's role is described, not parity argued) and `charge_sheet_filed` 11. Agreed-only gold drops both kinds, so recall is scored against a conservative set and weak_prima_facie is thin (74 agreed).
- G3: sections (rule-only 114, labeler-only 238: the rule reads sections out of citations and list formats the model leaves out, and the model finds written-out acts), `charge_sheet_filed` (labeler says "False" for "investigation still pending" and sometimes for text such as "till filing of the charge sheet", a spurious label the rules do not give), `previous_bail` (the model reads "bail turned down earlier"; the rules need "earlier application ... rejected").
- Span rejections: G1 3 (`span_not_in_text`); G3 322: `date_not_in_span` 282 (dates the model normalised from words or OCR noise such as "o1.10.2018", "09.1O.2025", "CrimeNo.499of2023dated09.12.2023"), `bad_date` 17 (a year or case number given as a date), `span_not_in_text` 18, `section_not_in_span` 6. Conservative by design: those dates are not in gold, and the rules cannot read them either.

### Second labeler (Sarvam, small sample)
- `mimo-v2.6-flash` is not served on the chat endpoint for this key: the API answers 400 "Input should be one of sarvam-105b, sarvam-105b-conversations" (released by the ledger, INR 0). The second labeler is therefore `sarvam-105b` (open-weight, non-Qwen), public text, run id `gold-labeler2`, run cap INR 5 (`VS_SARVAM=public` exported after `.env`, which sets `VS_SARVAM=off`).
- G1 on a random sample of 80 orders: kappa gpt-6-luna vs Sarvam-105B 0.784 [0.726, 0.836]; rules vs gpt 0.594, rules vs Sarvam 0.586. The two LLM labelers agree with each other much more than either agrees with the keyword rules.
- G3 on Sarvam: only 5 of 30 orders returned a valid JSON object (7 replies were not JSON, probably cut off at the 3,000-token limit or with thinking text; the replies were not stored) and the run cap then refused the rest. Inter-labeler G3 kappa 0.79 rests on 5 orders and must not be quoted. Not retried to stay inside INR 5.
- Sarvam spend of this task: INR 4.77 of the run cap of 5 (G1 INR 1.36 for 83 calls, G3 INR 3.40 for about 17 orders with retries); the ledger refused the call that would pass the run cap.

### Spend
- OpenAI (from the ledger, purposes `gold-g1` and `gold-g3`): G1 0.0320 USD, G3 0.1019 USD, pilot of 20 orders included: **0.134 USD** for 250 orders x 2 tasks (about 0.0005 USD per order). Run cap 0.40 was set (`VS_OPENAI_RUN_ID=gold-labeler`); whole-project total after: 0.203 of 4.50. No call failed.

## Files written (all gitignored, under `data/`)
- `data/interim/gold_candidate/`: `raw_openai-gpt-6-luna_{g1,g3}.jsonl`, `raw_sarvam-sarvam-105b_{g1,g3}.jsonl` (labels and spans, resumable), `g1.jsonl`, `g3.jsonl` (candidate gold records), `agreement_report.{json,md}`.
- `data/testsets/t1_gold_candidate/{cases,dev}.jsonl`: copies of the T1 files with G1 and G3 replaced by the agreed records (old extra keys kept, `gold_source` added). The original T1 files are untouched.

## Commands
```
# label (needs .env keys; public text only; OpenAI run cap 0.40 USD)
bash -c 'set -a; . ./.env; set +a; export VS_MODELS=auto VS_EXTERNAL=public VS_OPENAI_RUN_CAP_USD=0.40 VS_OPENAI_RUN_ID=gold-labeler; exec .venv/bin/python -m vakeel_sahayak.pipelines.gold.agreement run --labeler openai --workers 6 --out data/interim/gold_candidate'
# second labeler (Sarvam; VS_SARVAM must be exported AFTER .env)
bash -c 'set -a; . ./.env; set +a; export VS_MODELS=auto VS_SARVAM=public VS_SARVAM_RUN_CAP_INR=5 VS_SARVAM_RUN_ID=gold-labeler2; exec .venv/bin/python -m vakeel_sahayak.pipelines.gold.agreement run --labeler sarvam --task g1 --n 80 --workers 4 --out data/interim/gold_candidate'
# offline: report, candidate gold files, test-set copies
.venv/bin/python -m vakeel_sahayak.pipelines.gold.agreement report --primary-slug openai-gpt-6-luna --second sarvam-sarvam-105b --out data/interim/gold_candidate
.venv/bin/python -m vakeel_sahayak.pipelines.gold.agreement apply  --primary-slug openai-gpt-6-luna --out data/interim/gold_candidate --dest data/testsets/t1_gold_candidate
```
**Exact swap command** (the lead decides; run only after the freeze decision, and regenerate the manifests and hashes afterwards because `manifest*.json` and `blind_sealed.json` describe the old files):
```
mv data/testsets/t1 data/testsets/t1_rule_only_backup && mkdir data/testsets/t1 && cp data/testsets/t1_rule_only_backup/*.json data/testsets/t1/ && cp data/testsets/t1_gold_candidate/{cases,dev}.jsonl data/testsets/t1/
```
Also swap `data/interim/t1_work/gold/g1.jsonl` and `g3.jsonl` for `data/interim/gold_candidate/g1.jsonl` and `g3.jsonl` if downstream code reads the work folder.

## Caveats and not done
- Agreement is between two labelers that can share blind spots; the rules are not independent of the factor tagger that builds paragraph metadata. Results should still be re-run with each label source alone (evaluation plan 5.9): all three label sets (`rule_labels`, `llm_labels`, `labels`) are in every record.
- G1 agreed gold is conservative: 81 of 250 orders have no agreed factor, `weak_prima_facie` and `gravity_and_punishment` have low kappa. Counsel-style judgement of what "argued" means is not independently verified. Consider whether to merge confusable factors (plan risk table "Labelers disagree").
- The label sets of G4 to G7 (prosecution, court, conditions, rights) are not covered; the machinery (`run_labeler`, `agree_item`, `gold_report`) is task-agnostic but needs a prompt and schema per gold.
- Sarvam G3 second labeler not usable (see above); `mimo-v2.6-flash` and the other priced third-party models are not reachable on this key, so only `sarvam-105b` can be a second labeler.
- Character prices of Sarvam non-chat endpoints are unverified guesses; STT and Vision are unmetered.
- The `EvalLabeler.label()` path (Llama or confirm-the-candidates) is unchanged and still returns `NotImplementedError`-style provisional records when no client is available; `gold/*.build_gold` still use it. The new `agreement` module is the independent path.
- Pre-existing ruff findings remain in `tests/unit/models/test_openai.py`, `test_prefix.py`, `tests/unit/pipelines/gold/test_common.py`, `test_gold_modules.py` (not touched).
