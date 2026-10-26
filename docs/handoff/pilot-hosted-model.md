# Hosted-model pilot (VI-08): the Full system on `gpt-6-luna`

Date 2026-10-25. Nothing is committed. OpenAI spend of this task: about 0.052 USD (whole project 0.058 of the 4.50 cap).

## What was fixed
| Problem of pilot-3 | Cause | Fix (files) |
|---|---|---|
| Vakeel and Abhiyojak refused by the boundary; Peshkar's dossier empty | the driver passed raw T1 names; a stale case shelf from earlier runs still held raw text; the `auto` NLI needed torch | `eval/runners/driver.py`: `file_facts` pseudonymises like Munshi's Filer (same alias map, saved so `assert_pseudonymised` knows the names), plus `learn_caption_names` (court-order captions: `X ... Petitioner`, `S/O LATE X`, `Mr.X, Adv.`, `JUSTICE X`, capitals included, which the intake rules miss); only the pseudonymised text is filed and put in `state.facts_text`; `_fresh_shelf` deletes an evaluation case's old folder (ids `t<digit>...-`) before filing |
| Boundary false positives on public ids and text | 12-digit court ids (`HPHC010225332022`) matched the ID-number rule; "The State", "Vs" were taken for names; the client-level check applied generic name rules to the public `corpus` of a prompt | `privacy/pseudonymise.py` (`_NOT_A_PERSON`, ID rule skips 4 capitals + 12 digits), `privacy/boundary.py` (identifier fields, `assert_public_text`, `split_public_corpus`), `models/sarvam/policy.py` (case side checked in full; corpus checked for this case's names, PII, binary only: the same rule `guard_outbound(public=)` already applies; **please review this policy choice**) |
| `ModuleNotFoundError: torch` | `auto` NLI | CPU torch 2.14 and transformers 5.20 installed in `.venv` (`pip install torch --index-url https://download.pytorch.org/whl/cpu`, then `.[nli]`, a new optional extra); `models/nli.py` `AutoNliClient` (real DeBERTa from `models/hf/...` when it can run, else offline with the reason in `nli_status()`, the manifest (`nli`), `meta.nli` and an `nli_backend` event; `VS_MODELS=real` still raises); `models/factory.py`. DeBERTa on CPU: 6.5 s to load, 0.46 s per claim |
| Tests must not change because torch is now installed | auto mode would pick DeBERTa and local vision clients | `tests/conftest.py` sets `VS_NLI=offline` and `VS_HEAVY_CLIENTS=offline` (new gates in `models/factory.py`) |
| 314 s per case | each search re-read every vector blob and BM25 scored every row for terms like "of", "bail" (150 s per `search_reasoning` call) | `stores/hybrid.py`: per-process cached dense matrix; on stores of 20,000+ rows BM25 drops terms present in more than 15% of rows (keeps at least 2; `VS_BM25_PRUNE=0` turns it off; every fixture is unaffected). Search 153 s to 3.5 s. Small ranking change on real stores only |
| ERROR events | see below | `agents/sutradhar/agent.py` (`ask_user` step refused in `_step_problem`), `agents/base.py` and `models/sarvam/fallback.py` (an `llm_call` event now names the engine and why the hosted client was skipped; ERROR `model_unavailable` carries `primary_failed`), `models/openai/api.py` (`VS_OPENAI_NO_CACHE=1` for measurement) |

## The ERROR and BUDGET_HIT events, explained
- `permission_denied ... SUTRADHAR may not call ask_user`: a planned step used a slot tool that is counsel-facing. Now rejected in planning.
- `privacy_boundary ... doc_ids ... ID number`: court ids read as 12-digit ID numbers. Fixed.
- `model_unavailable ... vLLM localhost:8001` and Peshkar's `extract_failed`: not outages. The OpenAI client was refused by the boundary, the role's local fallback (vLLM, or the 4B model needing peft) then failed. The real reason is now in `primary_failed`.
- `gate_not_approved export refused`: intended, the scripted export attempt with Gate 2 closed. One per case.
- BUDGET_HIT: real caps working as designed (8 store calls and 12,000 tokens per factor). The first pilot hit it because Abhiyojak was retrieving for grounds that failed to draft.
- Remaining refusal, one per case: an objection-bank row (public order) contains a bank account number (`corpus.refusals[n].text`), so that Abhiyojak call is refused and falls back to nothing. Correct behaviour of the gate, but it costs one sparring call. Option: mask PII in corpus rows before sending.

## Commands
```
bash -c 'set -a; . ./.env; set +a; export VS_DATA_DIR="$PWD/data" VS_MODELS=auto VS_LLM_BACKEND=openai VS_EXTERNAL=pseudonymised VS_OPENAI_RUN_CAP_USD=0.30 VS_OPENAI_RUN_ID=<label> VS_OPENAI_NO_CACHE=1; exec .venv/bin/python -m vakeel_sahayak.eval.runners.driver eval-smoke --n 3 --out /tmp/claude-1000/run/<label>'
```
Without `VS_OPENAI_NO_CACHE=1` repeated identical prompts are answered from `data/openai/cache.sqlite` at zero cost (use it for reruns, not for measurements).

## Measurements (pilot-4f, cache off, three T1 dev cases; `data/eval/token_measure.json`)
| case | seconds | calls (Peshkar/Sutradhar/Vakeel/Abhiyojak) | tokens in / cached / out | USD | store calls |
|---|---|---|---|---|---|
| t1dev-000 | 140 | 24/5/11/4 | 63,179 / 9,822 / 3,205 | 0.0071 | 97 |
| t1dev-001 | 223 | 22/12/15/6 | 81,240 / 24,020 / 5,576 | 0.0088 | 110 |
| t1dev-002 | 152 | 23/4/10/4 | 66,376 / 8,505 / 3,108 | 0.0074 | 93 |
| mean | 172 | 47 | 70,265 / 14,116 / 3,963 | 0.0078 | 100 |

All calls were real `gpt-6-luna` calls, none fell back. Grounds: t1dev-000 3 REPAIRED; t1dev-001 G1 and G5 SUPPORTED, G2-G4 REPAIRED; t1dev-002 3 REPAIRED. Objections raised 3, 4, 3, almost all UNANSWERED (two PARTLY). Open issues 8, 10, 8. Export blocked in all, Gate 2 closed. Seconds: Peshkar's 24 sequential extraction calls take about 55 s, the rest is Vakeel check-and-repair and Abhiyojak. An earlier uncached run (4e) cost 0.0055 per case on average: the cached share of the prompt moves cost by about 2x.

## Quality notes (honest)
Read in full: t1dev-001 G1 and its sparring round. Facts are right (FIR 87/2023, Hili police station, NDPS sections 21(c), 22(c), 23(c), 27A, taken from the order) and nothing is invented; the cited paragraph exists and the claim check passed. But the argument is weak: the ground cites a decision that went against bail on gravity, so it states the State's point rather than counsel's; the reply to the objection restates the cited holding. Statutory position stays blank for t1dev-000 (the T1 facts text is only a caption). The T1 `facts_text` is very short, so most grounds rest on retrieved authorities, with open issues asking counsel for roots in the community, antecedents and dates.

## What remains
- Known failing stub tests unchanged (`test_metrics`, `test_stats`, `test_features`, `test_ingestion_pipelines`); `tests/unit/ingestion/test_signals.py::test_compute_signals_born_digital_pdf` fails independently of this work.
- The pseudonymiser is still rule based; real production intake should use the NER detectors (T1 is public data).
- (Fixed 2026-10-26, see the next section) A hosted rerun hit the per-factor token budget for `vakeel.reword_claim` and `abhiyojak.judge_reply` on t1dev-000.

## Fixes after the pilot (follow-up)
Done:
1. **Mask instead of refuse.** `agents/outbound.py` `mask_public`: `BaseAgent.ask` masks emails, phone numbers and ID or account numbers ([EMAIL], [PHONE], [ID-NUMBER], the tokens of `privacy.pseudonymise`) in the public `corpus` of every Ada-side call before the guard and the prompt; identifier fields (`doc_id`, `chunk_id`, ids, store, links) are untouched. The boundary is unchanged. Offline (laptop-side) runs are not touched. Test: `tests/unit/agents/test_outbound.py`.
2. **Party names in citations.** `normalise_citation` (same module), used by Abhiyojak's `_ground_view`: a citation with `X v. Y` is cut to its reporter or case-number form (`(2022) 10 SCC 51, para 14`, `Crl. M.C. No. 123/2020, para 5`), or to `Judgment <doc_id>, para N`; citations without parties are unchanged; `doc_id` and `para` stay beside it as the source link. Test in the same file.
3. **Peshkar in parallel.** `PeshkarAgent._extract_and_commit` reads the fields with `BaseAgent.parallel` (results merged in extraction order). Workers: `VS_PESHKAR_WORKERS` (1 to 16); unset means 1 with the offline backend (events byte-identical to before) and 4 with a hosted backend. The OpenAI ledger was already transactional (one SQLite connection per operation, `BEGIN IMMEDIATE`, safe across threads and processes); the only race was the lazy creation of the ledger and cache in `OpenAIApi`, now under a lock (`models/openai/api.py`). Tests: `tests/unit/agents/peshkar/test_agent.py` (workers env; same dossier with 1 and 4 workers). Wall-clock gain on a hosted run was not measured here.
4. **BM25 pruning, measured** on the real stores (read-only; script not committed), 30 queries each, the first 300 characters of randomly drawn rows of the store itself (seed 0, no labels), top 10, pruned (default 15% document-share cut) against `VS_BM25_PRUNE=0`:

| store (rows) | stage | overlap@10 mean (min) | Spearman on shared hits | seconds pruned / full |
|---|---|---|---|---|
| advocacy.objections (55,024) | hybrid search | 0.90 (0.5) | 0.92 | 0.11 / 0.29 |
| advocacy.objections | BM25 only | 0.80 (0.3) | 0.81 | 0.08 / 0.28 |
| caselaw.reasoning (161,247) | hybrid search | 0.82 (0.4) | 0.88 | 0.31 / 0.82 |
| caselaw.reasoning | BM25 only | 0.80 (0.0) | 0.88 | 0.23 / 0.80 |

   The hybrid overlap is at or above the 0.8 bar on both stores, so the 15% threshold was kept. It is only just above on `caselaw.reasoning` and single queries drop to 0.4, so freeze after one more check on the T1 retrieval analysis (to loosen, raise `BM25_COMMON_SHARE` in `stores/hybrid.py`). Timings are warm-cache and small here (the 150 s earlier was for a cold store and the longest queries).
5. **Pseudonymiser hook-in (privacy/ is Shravani's; about 13 lines in `privacy/pseudonymise.py`):** two `_PATTERNS` for judges after `Justice` (title case, and capitals including a name glued to the next heading word such as `SHARANORAL`), and `pseudonymise_text` puts a space after a detected name glued to the next word so the whole-word replacement finds it. Test: `tests/unit/privacy/test_pseudonymise_judge.py`. Shravani to review.

Hosted check (t1dev-000, cap 0.10 USD, cache off): Abhiyojak raised 3 objections, no `privacy_boundary` error and no refusal in the event log. Spent in that run: see manifest (`models.openai`).

Not done: Peshkar wall-clock speed-up not measured on the hosted backend; the Vakeel side was not changed for citations (its authorities travel in the public corpus).

## Follow-up 2026-10-26 (nothing committed)

### Per-factor token budget (bug fix, default behaviour changes by design)
Cause: the 12,000-token factor cap was one pool shared by Sutradhar (plan, reword query), Vakeel (draft, reword, reply) and Abhiyojak (raise, judge). From the pilot-4f event log of t1dev-000 the downstream steps alone used 12.0K (antecedents), 11.4K (flight_risk) tokens per factor, so repair and judge-reply were refused after retrieval and drafting had spent the pool. Fix (`orchestration/budgets.py`, `agents/base.py`, `config.py`, `configs/budgets.yaml`): two pools per factor. The 12K cap stays for the retrieval stage (Sutradhar, Peshkar, Munshi; the 8-store-call cap is untouched); Vakeel and Abhiyojak calls draw on a drafting pool of 16K (`drafting: {tokens: 16000}`, measured 12.0K to 12.8K plus about 25% headroom); the 150K case cap still bounds the total. `BudgetTracker.tokens_exhausted(factor, actor)` picks the pool; a charge without an actor counts as retrieval (old behaviour). BUDGET_HIT events carry limit `drafting_tokens` for the new pool. Pools survive `to_dict/from_dict` and `from_events`. Tests: `tests/unit/orchestration/test_budgets.py` (5 new). RECONCILED: `tests/unit/agents/vakeel/golden_default_run.json` events digest (the offline default run now logs 1 BUDGET_HIT where it logged 3; brief, sparring, card and budget digests are unchanged).
Hosted check (t1dev-000, cap 0.10 USD, cache off, run `budget-fix`): 5 `vakeel.reword_claim` and 2 `abhiyojak.judge_reply` calls, all ok on gpt-6-luna, no `BudgetExhausted`, no `model_failed`, no privacy error; the only BUDGET_HIT is the 8-store-call cap of gravity_and_punishment (working as a cap). Downstream tokens per factor: 12.8K, 12.2K, 7.1K (all under 16K). Cost of the run about 0.011 USD.

### Weak argument: authority stance (opt-in `Switches.authority_stance='outcome'`, variant id S18)
`agents/vakeel/stance.py` (design and paper in its docstring; row in `docs/literature-to-code-map.md`, Sweep 4). Outcome comes from the reasoning rows' `outcome` (read from the operative part by the store builders): in the current store 90,073 granted, 21,576 rejected, 2,816 withdrawn, 46,782 unrecorded rows. Test: `tests/unit/agents/vakeel/test_variants_authority_stance.py`. Not yet measured on T1 with a hosted model (next step: run t1dev-001 with and without the switch and count grounds that cite a refusal). Limits: a paragraph from a mixed order (some co-accused granted, one refused) takes the order's single outcome; 29% of rows have no outcome and count as unknown, so they are not demoted.

## Pseudonymiser: caption names

Problem: High Court captions name the party before the relation marker (`Sadhna Kushwaha, W/o Late Rakesh Roshan Kushwaha ...`), often glued to the word before (`ChhattisgarhSadhna Kushwaha`). The rules learned only names after a role word, so those names were missed, and the old `Late Rakesh Roshan` capture left `Late Person-5` / `Person-5 Kushwaha`, which the boundary's own title rule then flagged (t1dev-017 was refused for that).

Changes (`privacy/pseudonymise.py`; `privacy/boundary.py` only so the check ignores caption words the same way):
- New rules: a 2 to 3 word title-case or 1 to 4 word capitals name before `W/o S/o D/o R/o`, `wife of`, `son of`, `daughter of`, `alias`, `@`; one title-case word before `S/o W/o D/o` or ` @ `; a name before `Aged NN` (`AJMAL SHAH,AGED 19 YEARS`); capitals names after `S/O` (with `SHRI/SRI/LATE/SMT`, and `YEARSS/O.` glue); `alias`/`@` followed by a name; a camel-case pair after a marker (`S/o DasariRamanna`). `Late` joins the titles and is no longer part of the name.
- Glue: `_split_glued_before` puts a space before a learned name that follows a lowercase letter or digit (`ChhattisgarhSadhna`, `1Tapas`), only for capitalised spellings and first words of 3+ letters (4+ for one-word names), so places are not cut.
- Consistency: `leaked_name_tokens(text, mapping)` lists learned name tokens left in the output; `_sweep_name_tokens` replaces a surviving capitalised token (4+ letters, not a common particle, never lowercase in the text) by its alias.
- False-positive guards: caption words at the ends of a run (`Aged`, `Resident`, `For`, `At Present`, `And Another`, ...) are trimmed (`_trim_edges`), `No`, `Justice`, `Court` are not names; `State Of X` is judged before trimming.

Measured on all 250 T1 orders (dev 50 + cases 200), same path as `driver.file_facts` (caption rule, then learn, then clean) and `boundary._find_problems`:

| | before | after |
|---|---|---|
| orders the boundary refuses | 1 (t1dev-017) | 1 (t1-196: `S/o Kotakinda...` camel-case glue) |
| orders where the new, stricter boundary (new rules) would refuse the old output | 124 | 1 |
| orders with a party-name token of a name-before/after-marker proxy still in the output | 80 (160 tokens) | 5 (6 tokens) |

The proxy is an independent regex over the raw text (words before `W/o S/o D/o`, and after the markers), minus caption words; it is a leak estimate, not ground truth. Residual leaks are OCR damage: `TEERATH PRASHADKUSHWAHA` (name glued to name), `Arjun Kumar Sahnihave filed` (t1dev-018), `BARBHUIYA` as counsel name, `Kotakinda` + glued second name. Refusing these is correct. Known older behaviour not touched: the driver's caption rule (`learn_caption_names`) can learn odd strings (`For the petitioner`, `supported more at that time`), which then get replaced.

Tests: `tests/unit/privacy/test_caption_names.py`. Rerun the measurement with the loop in `driver.file_facts` over `data/testsets/t1/{dev,cases}.jsonl`.
