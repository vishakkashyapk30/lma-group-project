# Architecture search, 1 November 2026: why Full loses and what to try

Status: analysis only (nothing was run that costs money; no code or other docs were edited). Inputs: per-case CSVs in `docs/results/midsub/{openai_v3b,a7,gemini_A,sarvam,v1}/per_case_agreed.csv`, raw outputs in `lma/sweep-v3/data/eval/dev_runs/{openai_block_v3,sarvam_block_v3,gemini_block}/outputs/<arm>/t1dev-*.json`, the case files beside them (`cases/*.jsonl`, which hold `facts_text` and gold), and the scorer code (`eval/metrics/unsupported_fact.py`, `eval/scoring/case_metrics.py`). The one sentence-level re-scoring below ran MiniCheck-RoBERTa-Large locally (cut 0.5, as the scorer does) over the sentences of Full, A1 and A7 on OpenAI (counts match the CSV exactly: Full 148 of 165, A1 98 of 127, A7 111 of 129). Gemini and Sarvam sentences were not re-scored; their structural counts (tags, dossier fields, objections) are from the raw JSON.

## 0. Candidate table (ranked by expected gain per cost)

| # | Switch idea (all opt-in, default byte-identical) | Target metric | Mechanism in one line | Extra tokens per case | Anchor |
|---|---|---|---|---|---|
| X1 | `signal_source: "dossier" -> "merge"` | factor recall (8 orders), answerable coverage, objection recall | Sutradhar's factor picker reads the dossier first and fills every field the dossier lacks from the raw facts rules (`signals_from_text`) | 0 (rules) | Sufficient Context (R1) for "the field is missing, read the source"; IntrAgent (plan S7) |
| X2 | `argument_policy: "single" -> "fact_law_split"` plus extractive fact sentences | unsupported-fact rate (M6) | Case-fact sentences are written from spans of the facts text and checked against them; legal-principle sentences move to `Ground.legal_basis` (checked against the cited paragraph, scored by citation precision) | 0 to -5% | ALCE (Gao et al., EMNLP 2023); Claimify (ACL 2025); plan V2 |
| X3 | `sparring_scope: "per_ground" -> "all_factors"` (all-store retrieval inside the objection step) | objection recall (20 orders), guard objection precision | After the per-ground round, Abhiyojak raises at most one objection for each factor that has no ground, from the B4-style fused all-store pack of that factor | +5k to +9k (one more raise call), +10 to 30 store calls | Plan A1/A2 (Abhiyojak); Debate or Vote (equal-cost fairness); CourtEval (optional) |
| X4 | `abstention: "flag" -> "strict"` | M6, confident-wrong rate; guards: coverage, factor recall | A sentence that fails the claim check, or says "the record does not state ...", leaves `argument` and becomes an open issue (nothing dropped silently) | 0 | Trust-Score / Trust-Align (ICLR 2025); Conformal Factuality (ICML 2024); plan V4, V6 |
| X5 | `draft_source: "dossier" -> "facts_text"` (dossier kept for gates and open issues only) | M6, objection recall | The drafter quotes the raw facts, as A1 does, while contracts, authorities and sparring stay as in Full: "A1 drafting plus Full retrieval" | about 0 | CRITIC (outside evidence); plan C11 (A1) |
| X6 | `critic_material: "contract" -> "union_free"` | objection recall | Abhiyojak sees the contract packs plus the free-plan packs (A7 style) so it has material on more factors; drafting is untouched | +3k planner, +8k raise, +30 store calls (about +10%) | Debate or Vote; AFlow/ADAS for searching the combination |
| X7 | H1 = X1 + X5 + X2 + X4 (+ X3), the combined best-of-ablations arm | all four | The A1 and A7 gains without their losses (A1 keeps coverage 0.9; A7 loses it at 0.33) | about +6k vs Full | S13 (searched grid on dev) |

Order of work: X1, X4, X2 first (zero tokens, each fixes a defect measured below), then X3 and X5, then X6, then X7 on the survivors. Section 4 gives dev usage; section 5 lists the limits.

## 1. What the three families show (from the CSVs)

Means over scored orders; n is the number of orders with the metric defined.

| Family, arm | unsupported rate (all orders) | objection recall (n=20 OpenAI, 11 Sarvam, 11 Gemini) | answerable coverage (n=12, 11, 8) | factor recall (n=8, 4, 3) |
|---|---|---|---|---|
| OpenAI Full (38 orders) | 0.901 | 0.750 | 0.467 (15) | 0.250 |
| OpenAI B4 (30) | 0.821 | 0.900 | 0.639 (12) | 0.500 |
| OpenAI A1 (28) | 0.788 | 0.889 (18) | 0.233 (10) | 0.375 |
| OpenAI A7 (30) | 0.869 | 0.925 | 0.389 (12) | 0.250 |
| OpenAI B0 to B3 | 0.82 to 0.87 | 0.000 | 0.00 to 0.03 | 0.375 |
| Sarvam Full (30) | 0.998 | 0.455 | 0.379 | 0.500 |
| Sarvam B4 (30) | 0.952 | 0.273 | 0.242 | 0.500 |
| Sarvam A1 / A7 | 0.917 / 0.957 | 0.455 / 0.364 | 0.303 / 0.167 | 0.25 / 0.50 |
| Gemini Full (25) | 0.880 | 0.636 | 0.458 | 0.333 |
| Gemini A1 (10) | 0.752 | 0.500 (4) | 0.500 (2) | 0.500 (2) |

Paired differences on the orders both arms have (Full minus arm; bootstrap 95% interval, 2000 resamples):
- Unsupported rate, A1: OpenAI +0.098 [0.020, 0.179], Gemini +0.151 [0.035, 0.270], Sarvam +0.080 [0.046, 0.116]. A1 is lower in all three families, and the interval excludes 0 in all three.
- Unsupported rate, B4: OpenAI +0.068 [0.008, 0.130], Sarvam +0.046 [0.023, 0.073]. Every baseline B0 to B4 is lower than Full on OpenAI and on Sarvam (OpenAI B0 to B4 0.82 to 0.87 against 0.90; Sarvam 0.90 to 0.97 against 0.998). On Gemini the order is reversed: Full (0.880) is below B0 to B3 (0.89 to 0.95; paired Full minus B1 -0.086 [-0.183, 0.002], minus B3 -0.087 [-0.212, 0.031]) and only A1 (0.752) is lower. So the loss to baselines on this metric is a two-family result, and the Gemini baselines write short unchecked text.
- Objection recall: Full minus B4 is -0.150 [-0.350, 0.050] on OpenAI (the interval contains 0) and +0.182 [-0.273, 0.636] on Sarvam. So "B4 beats Full on objection recall" is not established on 20 orders, only that Full does not beat it. Full minus A7 is -0.175 [-0.350, -0.025] on OpenAI (A7 is better), +0.091 on Sarvam.
- Answerable coverage: Full minus B4 is -0.222 [-0.472, 0.000] on OpenAI, +0.136 on Sarvam; Full minus A2 is +0.417 [0.167, 0.694] (check and repair earns this).
- Objection precision (objection factors that are gold, OpenAI): Full 0.228, B4 0.118, A1 0.212, A7 0.176; Sarvam Full 0.250, B4 0.049. Full beats B4 on precision in both families, so on F1 of objections it is ahead, not behind.
- Factor recall and precision (v1, 50 orders, 8 scorable): Full 0.250 (16 order-runs), B0 0.500, B1 0.625, B4 0.625, B6 (expert rules) 0.875; factor F1 Full 0.208 against B6 0.771. On OpenAI the baselines B0 to B3 have lenient factor precision 0.889 against Full 0.500, because they argue one or two factors. This is a loss the earlier handoff did not list.
- Cost: Full uses 85k to 97k tokens per case; B0 to B3 use 2k to 5k; B4 126k (OpenAI). "Beat every baseline on all metrics" cannot hold for tokens or latency against B0 to B3; the plan's cost claim (C4) is against B4 only. The search below targets quality metrics and uses tokens as a budget.

## 2. Diagnosis by stage, with counts

### 2.1 Unsupported-fact rate: the metric and the drafter disagree about what "supported" means

What is measured: `unsupported_fact_counts` splits every ground's `argument` into sentences (3 words or more) and asks MiniCheck whether `facts_text` of the case entails each one. `facts_text` is the order's own facts, median 179 words (range 73 to 558). The system's own checker (`agents/vakeel/agent.py: check_claims`) instead checks each sentence against the source it cites: a dossier field or the cited precedent paragraph. The two checkers are not looking at the same premise.

OpenAI Full, 165 sentences, 148 unsupported (MiniCheck re-score):

| Sentence kind (by tag and wording) | sentences | unsupported | share of all unsupported |
|---|---|---|---|
| Legal-principle sentences carrying `[A:doc#para]`, not an absence statement | 85 | 81 | 55% |
| Absence statements ("the record does not state ...", "no facts about antecedents") | 41 | 35 | 24% |
| Sentences with a pseudonym token (`Person-N`, age bands) | 11 | 11 | 7% |
| Case-fact sentences from dossier fields (`[F:fir]`, `[F:sections]`, `[F:personal]` ...), none of the above | 20 | 13 | 9% |
| Other (untagged) | rest | rest | 5% |

Therefore about 86% of the unsupported count is structural: a precedent's holding, a statement of what is missing, or a pseudonymised name cannot be entailed by the case's facts, whatever the system does. By check state, from the same re-score: NEEDS_REVIEW sentences 36 of 36 unsupported, REPAIRED 70 of 74 (95%), SUPPORTED 42 of 55 (76%). "SUPPORTED" by the system's checker is still 76% unsupported by MiniCheck against the facts. By stance: adverse 122 of 128, favourable 26 of 37.

Counterfactual rates (OpenAI, same sentences, dropped rather than rewritten, so these are bounds, not predictions):

| Sentences kept | Full | A1 | A7 |
|---|---|---|---|
| all (as scored) | 148/165 = 0.897 | 98/127 = 0.772 | 111/129 = 0.860 |
| minus NEEDS_REVIEW sentences | 112/129 = 0.868 | 86/107 = 0.804 | 31/49 = 0.633 |
| minus absence statements too | 99/110 = 0.900 | 27/41 = 0.659 | 29/46 = 0.630 |
| case-fact sentences only (also minus `[A:]`) | 23/30 = 0.767 | 14/24 = 0.583 | 29/46 = 0.630 |

Reading: (a) dropping abstentions alone does not help Full (0.868, 0.900) because most of its remaining sentences are `[A:]` sentences; (b) even the case-fact-only subset of Full (0.767) is worse than A1's (0.583), so the dossier is itself a poor source of case-fact sentences; (c) A7 looks good only when 80 of its 129 sentences (all NEEDS_REVIEW, all unsupported) are removed, which is why its coverage is 0.33.

Why A1 is lower: it writes case-fact sentences in the words of the facts (`[F:facts_text]`, 59 sentences, 38 unsupported = 64%) while Full's dossier sentences are 45 of 55 unsupported (82%), and it uses fewer `[A:]` sentences per case (62 over 28 orders, 2.2, against 99 over 38 orders, 2.6). Dossier sentences fail because the dossier value is not the order's wording: pseudonymised names and age bands ("Person-1 is aged about 51-64 years" against "aged 68"), and in `t1dev-011` the antecedents field holds the current case number (Kutra P.S. case 115 of 2023, which is the case itself) so the brief states it as an antecedent entry (score 0.27) under a favourable stance. The dossier injects wrong or unmatched statements; it is not neutral.

Repair: Full minus A2 (no check and repair) is -0.029 [-0.058, -0.006] on OpenAI and +0.007 [0.000, 0.019] on Sarvam. Repair removes about 3 points on OpenAI and nothing on Sarvam; it does not add unsupported sentences, but it does not make `[A:]` sentences entail from the facts either (REPAIRED sentences are 95% unsupported). Of 165 Full grounds on OpenAI, 74 are REPAIRED, 55 SUPPORTED, 36 NEEDS_REVIEW; Gemini 24/69/17; Sarvam 42/22/36.

Sarvam Full is 0.998 because 166 of its 209 sentences are `[A:]` (79%), against 99 of 165 (60%) on OpenAI and 130 of 204 (64%) on Gemini. The rate tracks the share of authority sentences almost one to one.

### 2.2 Factor recall and answerable coverage: the intake stage starves the planner

The dossier (Munshi then Peshkar) has 13 fields. Fields filled per case at Gate 1, Full: OpenAI 2.8 on average (6 of 38 orders have none filled), Gemini 3.0, Sarvam 1.8 (3 of 30 none). `arrest_date`, `custody_days`, `co_accused_bail`, `antecedents`, `previous_bail`, `first_remand` are unresolved in 34 to 38 of 38 OpenAI orders. Yet the facts often state them: `t1dev-033` and `t1dev-046` say "languishing in jail since 04.01.2024 / 23.11.2023" and all 13 dossier fields come back unresolved.

`pick_stances` (`agents/sutradhar/factor_pick.py`) is a rule engine over the dossier signals: custody_period needs `custody_days`, parity needs a granted co-accused, trial delay needs a stage. With empty fields those factors are NOT_APPLICABLE, and three factors are always on by rule (gravity, antecedents, flight risk, each adverse when nothing is known). Result over the 375 grounds of Full across the three families: gravity 93, antecedents 93, flight risk 93, witness tampering 40, weak prima facie 29, health 18, charge sheet 9, and zero custody_period, parity or trial delay grounds. In the 8 factor-scorable orders the gold factors are custody_period (4 orders), parity (4), weak prima facie (2), antecedents (2), and one each of charge sheet, flight risk, health; the factors Full argued are almost always gravity, antecedents, flight risk, witness tampering. That is the factor-recall ceiling (0.25) and the low factor precision (0.15 to 0.50).

A1 uses `signals_from_text` (raw-facts rules: `custody_days`, `charge_sheet_status`, `co_accused_outcome`) and reaches factor recall 0.375 (Full 0.250; n=8, one gold factor moves the mean by 0.06 to 0.125) and answerable coverage within noise of Full (paired Full minus A1 +0.067 [-0.233, 0.333], n=10); B4 and B6 get recall by arguing 12 or all factors (C3 in the plan flags this). So the lever is X1, not more retrieval.

### 2.3 Objection recall: the objection set is bounded by the grounds, and B4 wins by breadth

Abhiyojak objects against grounds (`against: G2`); the objection factor is the ground's factor. Gold G4 has 23 factor labels over 20 orders (1.15 per order: gravity, antecedents mostly). OpenAI, 20 gold-bearing orders:

| Arm | objections per case | distinct objection factors | grounds | gold items with a ground | gold items with an objection (of 23) | recall |
|---|---|---|---|---|---|---|
| Full | 5.0 | 3.95 | 4.7 | 19 | 17 | 0.750 |
| A1 | 6.1 | 4.80 | 4.1 | 20 | 20 | 0.900 |
| A7 | 7.3 | 5.55 | 4.7 | 19 | 21 | 0.925 |
| B4 | 9.4 | 8.75 | 12.0 | 23 | 21 | 0.900 |
| A8 (no sparring) | 0 | 0 | 4.7 | 19 | 0 | 0.000 |

Full misses 6 of 23 gold items: 2 have no ground and no objection (parity, `t1dev-039` and `-047`), 4 have a ground but no objection (antecedents in `-034` and `-043`, gravity in `-037`, charge sheet in `-049`); 2 other gold items had no ground yet were objected, so the general mode already reaches some uncovered factors. Abhiyojak often answers antecedents with "the record shows nothing" (example `t1dev-001`). B4's recall comes from 12 grounds, hence 8.75 distinct factors per order against 1.15 gold; its objection precision is 0.118 against Full's 0.228. The metric (recall of gold factors among objection factors) rewards breadth; the plan's C3 guard (precision, F1) is the check against that. A7 reaches 5.55 distinct factors with the same 4.7 grounds, so its gain comes from Abhiyojak receiving more raw material (free-plan packs), not from more grounds. Hypothesis to confirm in `_events`: Abhiyojak declines to object where its three stores returned nothing for the factor.

Sparring costs 38k tokens on OpenAI (Full 95k, A8 57k) and 30k on Sarvam (97k against 67k). Verdicts on Full's own replies: 129 UNANSWERED, 49 PARTLY, 13 ANSWERED of 191 on OpenAI: the replies mostly do not rebut, which is a quality problem for the product but does not enter recall.

### 2.4 What each stage contributes to the failures (summary)

| Stage | Evidence | Metrics hurt |
|---|---|---|
| Intake (dossier extraction) | 2.8 of 13 fields filled; custody facts missed when present in the text; one wrong antecedent; pseudonym and age-band values that do not match the facts | factor recall, factor precision, answerable coverage, M6 |
| Planner (`pick_stances`) | rule needs dossier fields; always-on adverse factors; 0 of 375 grounds on custody, parity, trial delay | factor recall, objection recall (no ground, no objection) |
| Drafter | 60 to 79% of sentences are `[A:]` principles; 25% are absence statements | M6 (structural) |
| Claim check and repair | checks against the cited source, not the facts; repair helps coverage (+0.42) and costs nothing in M6 | none (it is not the cause) |
| Sparring | bounded by grounds; declines where no material; replies unanswered | objection recall |

## 3. Candidates in detail

Common rules: each is a `Switches` field with a validator against incompatible planner switches (see `_variants_need_the_planner`), an entry in `ARCHITECTURE` and `VARIANT_DESCRIPTIONS`, a line in `IMPLEMENTED_VARIANTS`, a paper citation in the docstring, a row in `docs/literature-to-code-map.md`, and a golden test that the default run is byte-identical (`tests/unit/agents/*/test_variants_golden.py`). Ids below are working names (S19 to S25); none exists yet. Tokens are per case against Full at about 95k (OpenAI).

**X1 `signal_source="merge"` (S19).** Change `agents/sutradhar/factor_pick.py`: a `signals_merged(dossier, text, before, rights)` that takes dossier values where status is stated, else `signals_from_text`; `plan_context` in `agents/sutradhar/planning.py` selects it; reasons must name "the facts text" for the merged fields (the `where` string already exists). Mechanism: fixes the dossier starvation of 2.2 without a model call. Also feed the same text-derived custody date to `date_calc` so `custody_days` is computed, not guessed. Target: factor recall (8 orders) and answerable coverage; guard: factor precision (it will add grounds, so watch lenient precision and the C3 F1). Risk: the text rules read only what `pipelines/order_facts.py` matches ("languishing in jail since" may need a pattern; check `custody_days` on `t1dev-033` and `-046` first, offline, at zero cost). Cost 0 tokens. Test: offline run on the 50 dev orders to see which factors move (free), then Gemini on the search split.

**X2 `argument_policy="fact_law_split"` (S20).** Change `agents/vakeel/prompts.py` and `claims.py`: the drafter writes two lists per ground, `case_facts` (each sentence must be a near-verbatim span of `facts_text`, with a character-span reference, checked deterministically by `tools/drafting/claims.py` and by the claim NLI against the span) and `legal_basis` (principle sentences with `[A:doc#para]`, checked against the paragraph as today). `Ground.argument` is rendered from both for the lawyer, so the brief reads the same, but `schemas/bail_brief.py` needs a `legal_basis` field and the export must show it. Expected effect on M6 as currently defined: only if the scorer reads `case_facts` alone. This is a measurement decision and must not be made after seeing results: the owner and the pre-registration (`docs/preregistration.md`) must decide, before the freeze, whether M6 is (a) all argument sentences against `facts_text` (today), or (b) case-fact sentences against `facts_text` plus authority sentences against their cited paragraph (M6a and M6b), applied identically to every arm including the baselines (their `[A:]`-tagged sentences are split the same way). Under (a) X2 cannot lower the rate, per the table in 2.1. Under (b) the case-fact subset is 30 of 165 sentences for Full today, so M6a must be reported with its count and with answerable coverage (the scorer already refuses to reward a silent brief). Cost: about 0 to -5% tokens (shorter fact sentences, same authority calls). Anchors: ALCE (citation recall and precision by NLI), Claimify (decontextualised, entailed claims), plan V2.

**X3 `sparring_scope="all_factors"` (S21).** Change `agents/abhiyojak/agent.py` (`raise_objections`) so that after the per-ground round it runs the `general` objection mode (prompt text already exists: "When the ground is null these are the general objections") for each of the 12 factors that has no ground and for which the pack is non-empty, using the B4 fused pack (`run_b4` in `agents/sutradhar/baselines.py`) instead of the three Abhiyojak stores. Constraints to protect precision: at most 1 objection per uncovered factor, every objection must carry a `grounds` pointer (the prompt already forbids objections with nothing to point to), a cap of 4 extra objections per case, and an objection raised only when the fused pack for the factor has at least one item above a score floor fixed on the search split. Target: objection recall on the 20 orders. Guard: objection precision must stay at or above B4's (0.118 OpenAI, 0.049 Sarvam) and no worse than Full's minus 0.05; report objection F1. Cost: one more raise call (+5k to +9k) and up to 30 store calls. Anchors: plan A1 (equal-cost critic fairness: S9 is the same-budget comparison) and Debate or Vote.

**X4 `abstention="strict"` (S22).** Change `agents/vakeel/agent.py` `repair_or_flag` and `_finish`: a sentence that fails after the repair rounds, or that matches an absence template ("record does not state", "no facts"), is removed from `argument` and written as an open issue (type `NEEDS_REVIEW` or `MISSING_EVIDENCE`, which the brief already has), keeping the "nothing dropped silently" rule. A ground left with no sentence is not emitted, and its factor stays visible as an open issue. Add a threshold on the NLI support score calibrated on dev with the constructed negatives of plan V4 (corrupt dates and section numbers of court-written sentences; no hand labels). Target: M6 and confident-wrong rate. Guards: coverage, factor recall (a dropped ground is a lost factor; this is why X1 comes first). Expected size from 2.1: small alone (Full 0.897 to 0.868 by dropping NEEDS_REVIEW sentences), larger combined with X2 and X5. Cost 0 tokens. Anchors: Trust-Score and Trust-Align (refusal as part of the score), Conformal Language Model Factuality (back off until a stated share is correct).

**X5 `draft_source="facts_text"` (S23).** Change `agents/vakeel/agent.py` evidence building (`_evidence_for`) and `facts.py` so the drafter's fact source is the raw facts (as A1) while Sutradhar keeps its contracts and the dossier still drives Gate 1 and the open issues. Today `no_dossier` switches both the planner signals and the drafter source at once; this separates them so the A1 gain on M6 (A1 lower by 0.10, 0.15 and 0.08 in the paired OpenAI, Gemini and Sarvam comparisons) can be taken without A1's loss of coverage (A1 answerable coverage 0.233 on OpenAI against Full 0.467; unpaired and n=10, so read as a warning not a result). Target: M6 and objection recall. Cost about 0. Anchor: plan C11, CRITIC (outside evidence).

**X6 `critic_material="union_free"` (S24).** Change `agents/abhiyojak/agent.py` `_material` to merge the contract-pack items with the free-plan packs of `run_free_planner` (A7). A7 shows that more raw material raises objection recall (+0.175 on OpenAI, interval excludes 0) with the same grounds. Cost about +10% tokens. Risk: more unanswerable objections; watch objection precision. Anchor: the AFlow and ADAS idea for composing arms found on dev (S13).

**X7 H1, the combined arm.** `Switches(signal_source="merge", draft_source="facts_text", argument_policy="fact_law_split", abstention="strict", sparring_scope="all_factors")`; ablate one at a time from H1 (leave-one-out) rather than adding one at a time, because the effects are not additive (X4 needs X1; X2 needs the scorer decision). Report A1 and A7 plain beside it: the point of H1 is to keep A1's M6 and A7's objection recall without A7's collapse of coverage (0.33 OpenAI, 0.07 Sarvam) and A1's loss of the dossier checks that the product promises.

Also checked, not recommended: more single-switch variants. Most of S1 to S18 are indistinguishable from Full on 10 orders (OpenAI 0.92 to 1.00, Sarvam 0.97 to 1.00 on the unsupported rate); S9 (sampling critic) shows objection recall 0.5 on 4 orders, too few to rank.

## 4. How to test on dev with the existing driver

No paid calls. Use the offline stand-in for plumbing and the factor-pick change, and the Gemini free tier (public dev orders only; about 10 Full cases a day per key, day rolls over at 12:30 IST) for model-dependent arms. Sarvam is open under the owner's cap; do not use it for search.

1. Switch plumbing as in `docs/handoff/ev-01-switches.md`; each candidate becomes an arm in `configs/eval/sweep_dev.yaml` (id `S19` ...), run with `python scripts/sweep_dev.py run --phase 5 --arms S19 --n 30 --shards 2 --parallel 1` on the Gemini 3.5 flash-lite backend, exactly as `scripts/midsub/sweep-v3-phase2-A.sh` does for Full and the baselines. Score with `python -m vakeel_sahayak.eval.scoring score --runs <outputs> --slice dev --gold-source agreed --out <dir>`, then rebuild tables with `docs/report/tools/make_result_tables.py`.
2. Always run Full and A1, B1, B4 on the same orders in the same backend (paired comparison). The existing Gemini outputs already cover Full and B0 to B3 on 25 orders and A1 on 10; B4 has not been run on Gemini and is needed (OpenAI/Sarvam B4 cannot be rerun).
3. X1 and X4's rule parts first, offline, free: print for each of the 50 dev orders the picked factors and the grounds before and after, and compare with the 8 gold orders.
4. Decide the M6 definition (X2) before running anything for the final table; add M6a and M6b to the scorer (`eval/metrics/unsupported_fact.py`, which already exposes `sentence_support`) and rescore the stored outputs of every arm and family at zero model cost, so the change applies to all arms equally.
5. Per candidate, report the paired difference to Full and to the best baseline with a bootstrap interval, the count of orders behind it, tokens per case, and the guards (objection precision and F1, factor precision, coverage, citation precision).

## 5. Dev gold limits and the search/holdout split

Gold on dev is thin: factor metrics are defined on 8 of 50 orders, objection recall on 20 (23 gold factor labels), answerable coverage on 20; Gemini scores 3, 11 and 8 of these on its 25 orders; per-family intervals above are wide (objection recall CI half-width about 0.2 to 0.45). Do not rank candidates by a point difference below 0.10 on any of these.

Gold-bearing dev orders:
- G4 (objection recall, 20): 003, 004, 007, 009, 010, 011, 012, 013, 019, 020, 023 | 031, 034, 036, 037, 039, 043, 047, 048, 049.
- G1 (factor recall, 8): 003, 009, 011, 025 | 033, 039, 045, 046.
- Answerable coverage (20): 003, 009, 011, 012, 014, 017, 021, 023, 025, 028, 029 | 033, 035, 038, 039, 044, 045, 046, 048, 049.

Proposal: search on orders `t1dev-000` to `t1dev-029` (the orders every family already ran: G4 11, G1 4, coverage 11; free metrics such as M6 and coverage use all 30) and keep `t1dev-030` to `t1dev-049` as a holdout (G4 9, G1 4, coverage 9; OpenAI has only 8 of these scored) that is touched once per surviving candidate family, with the thresholds frozen before that run. Two disclosures: (i) this analysis looked at all 20 G4 orders and all 8 factor orders to count misses, so the holdout is not blind to the diagnosis; the candidates are justified by structural counts over all orders (fields filled, sentence kinds, factors never grounded), not by per-order tuning, and each rule threshold must be fixed on the search split only; (ii) the real confirmation is the sealed blind slice after the freeze (timeline in the report), and any candidate that wins on dev but not there is reported as not confirmed. The expected ceiling is small: with 8 factor orders a recall change of one gold factor moves the mean by 0.06 to 0.125, so factor recall should be treated as a guard and judged on the open slice after the freeze (no manual annotation, per the hard rule).

Do not game the recall metrics: "argue all 12 factors" and "object on all factors" have recall 1.0 by construction (plan C3 and section 5.7). Every candidate that adds grounds or objections (X1, X3, X6) reports precision and F1 beside recall and must stay above B4's precision.

## 6. What "beats every baseline on all metrics" can honestly mean

- Quality metrics only: unsupported rate, objection recall and precision, factor recall and precision, answerable coverage, citation precision, coverage, confident-wrong rate. Tokens, latency and cost cannot beat B0 to B3 (2k to 5k tokens against 85k to 97k) and the plan does not claim it (C4 is against B4).
- M6 under today's definition is dominated by the scorer's premise (facts only) and by absence statements; some baselines score 0.82 because they write few sentences. Beating them there needs X2 and X4 together with the metric decision of section 3, taken before the freeze and applied to all arms. If the owner keeps today's definition, the defensible claim is the paired-CI statement (Full is not worse than the baselines by more than the margin, and no unsupported authority), not superiority.
- Each added gain must survive the three families; at present A1's M6 gain is consistent in all three (paired intervals exclude 0), the objection-recall gaps are not, and factor recall is not resolvable on dev.

## 7. Next steps (in order)

1. Owner decision on M6a and M6b (section 3, X2) and on the `facts_text`-only premise; record in `docs/preregistration.md`.
2. X1 offline check on `t1dev-033`, `-046`, `-009`, `-011` (does `custody_days` read "languishing in jail since ..."?), then implement the three zero-token switches X1, X4, X5 with golden tests.
3. Run B4 on Gemini on the search split; run S19, S22, S23 and H1 on Gemini 3.5 flash-lite, 30 orders, paired with Full and A1.
4. X3 with the precision guard; X6 only if X3 leaves objection recall below B4 on the search split.
5. One holdout run of the survivors; then freeze thresholds, tags `prereg-v1` and `eval-freeze-v1`, then the blind slice once.
6. Frontend and backend follow the winner only after step 5; if no candidate beats the baselines on the guarded metrics, report H1's paired differences honestly rather than changing the metric afterwards.

Method note: sentence splits use `eval/feature_common.sentences_of`; MiniCheck from `models/hf/lytang--MiniCheck-RoBERTa-Large`, cut 0.5; premises are `facts_text` from `cases/*.jsonl`. The absence-statement and `Person-N` classes are regex rules over the sentence text (a heuristic classification of already-scored sentences, not a new metric). Scripts were scratch and not committed.
