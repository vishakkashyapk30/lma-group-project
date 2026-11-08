# Pre-registration (frozen 2026-11-09 with tags `prereg-v1` and `eval-freeze-v1`)

Status: FROZEN 2026-11-09 (branch `arch-search`; the 2026-11-01 draft plus section 1.5, the freeze record and the declared deviations of section 8, all written before the blind slice was opened). The decision thresholds are fixed on the DEV slice only (50 dev orders; the per-case score files
`docs/results/midsub/{openai_v3b,a7,sarvam,gemini_A,v1}/per_case_agreed.csv`, derivation in section 1.2 and `docs/results/prereg/dev_stats.json`, produced by
`scripts/prereg_dev_stats.py`). The blind slice (`data/testsets/t1/blind_sealed.json`) was not opened to write this file. Items that only exist at the freeze (SHAs, date, final switch
set re-paste, budgets, seeds) stay as angle-bracket placeholders and are listed in `docs/handoff/prereg.md` for the owner. Nothing below is a result of the blind slice. Written from `docs/evaluation-plan.md` (sections 1, 2.6, 2.7, 3, 5, 7)
and `configs/eval/hypotheses.yaml`. The freeze is the commit that carries this file with the git tag `prereg-v1`, plus the code tag `eval-freeze-v1` (split.md appendix C, 8.2; `scripts/freeze_tags.sh`). Until the
tags exist, the blind scoring entry point refuses to run (`testsets/blind.py`).

**Honest summary of what the dev data say (details in 1.2).** Full does NOT beat every baseline. It beats B0 to B3 on objection recall and answerable coverage (largely by construction: those baselines emit no objections and no per-factor grounds), but B4 (query every store) matches or beats it on both (objection recall B4 0.90 to 0.93 against Full 0.69 to 0.75 on the OpenAI and v1 runs; coverage 0.64 to 0.75 against 0.42 to 0.50). No baseline is worse than Full on the unsupported-fact rate; Full is higher (worse) than B0 to B4 on three of four backends, and the rate is near its ceiling (0.86 to 1.00) for every system. Factor recall rests on 8 of 50 dev orders and is unresolved, with point estimates in the baselines' favour on two backends. What Full does show is a lower cost than B4 (18 to 23 % fewer tokens, 47 to 48 % fewer store calls), zero fabricated citations, and the effects of its own components (A2, A8, A9 lose answerable coverage or objection recall). The registration below therefore marks every claim the dev data already contradict as **confirmatory, dev-contradicted, expected to fail**: it is still tested and reported, and nobody may re-label it after the blind slice is seen.

## 0. Freeze record (fill at the freeze)

| Item | Value |
|---|---|
| Date and time of the freeze | 2026-11-09, before the blind slice was opened (the tag message carries the exact time) |
| Git SHA of `eval-freeze-v1` | the commit the tag `eval-freeze-v1` points to (`git rev-parse eval-freeze-v1`); the same commit as `prereg-v1` |
| Git SHA of the commit carrying this file (`prereg-v1`) | the commit the tag `prereg-v1` points to (`git rev-parse prereg-v1`; a file cannot hold its own commit hash) |
| Tracked switch set (the output of `Switches.implemented_variants()` at the freeze) | at the freeze (61): A1, A10, A2, A3, A4, A5, A6, A7, A8, A9, B5, H1, H1m1, H1m2, H1m3, H1m4, H1m5, H1m6, P5, P6, P7, P8, S1, S10, S11, S11b, S11c, S12, S12b, S13, S14, S14b, S14c, S14d, S15, S15b, S16, S16b, S17, S17b, S17c, S17d, S18, S2, S3, S3b, S4, S5, S6, S7, S8, S9, X1, X2, X3, X4, X5, X6, X7, X8, full. At `dev-sweep-v3` (46): A1, A10, A2, A3, A4, A5, A6, A7, A8, A9, B5, P5, P6, P7, P8, S1, S10, S11, S11b, S11c, S12, S12b, S13, S14, S14b, S14c, S14d, S15, S15b, S16, S16b, S17, S17b, S17c, S17d, S18, S2, S3, S3b, S4, S5, S6, S7, S8, S9, full (re-paste at the freeze) |
| Prompt hash (`driver.prompt_hash()`, also in every run manifest) | `927168ea9cf51f22` at the freeze (`f4e2c690b94aaad3` at `dev-sweep-v3`; the architecture-search switches added prompts, defaults unchanged) |
| Config hash (`driver.config_hash()`) | `de9ccc201439c41e` at the freeze (`bcc7d5d5f409c8ca` at `dev-sweep-v3`) |
| Blind-slice set hash (`python scripts/prereg_hash.py`) | `9185e1cce6f981a70df4cf4aaaa5a35bc0648dfa216dff6900010512be8ebe32` (recomputed 2026-10-29; equals `manifest_blind.json`) |
| Blind slice: size, BNS-era count, post-release count | 80, 40, 80 (counts only) |
| Dev ids | `data/testsets/t1/manifest_dev.json` (identical in `t1_rule_only`), sha256 `61c4bc451d40fcb26c0b5d3d418371c3ba2f3e8f08148a2474d7cd4bfaa3ba06` |
| Test-set manifests and hashes (T1 to T9) | sha256 (first 16 hex) of the row files on 2026-10-29. The blind slice's gold is sealed by the hash of the whole T1 file, not only its ids (design review item 11): T1 `cases.jsonl` 2262383a77f3a7b0, `dev.jsonl` 9a22f359b9f4c5ba, T1 rule-only `cases.jsonl` 0c440657ff99e885, T2 `truth.jsonl` 422fab921f0a3512, T2 Hindi native c88583c2adbac7b9, T3 ca2fb11a401d143d, T4 (627) f9946f466ec36e95, T5 0ce0b029d7483806, T6 313918794447744d, T7 71e68c8bf6e9398e, T8 f55cecccea2677f3, T9 3c26048bd62bf7ad |
| Seeds | one run per system (run index 1, the driver's seed for run 1; every system shares it). Runs 2 and 3 are not made (budget and time; deviation D2 in section 8). Scoring seed: bootstrap seed 0 (`eval/scoring/stats_extra.SEED`), 10,000 resamples (`engine.N_BOOT`), fixed in code |
| Code stamp | every run manifest records `git_sha`, `git_dirty` and `code_tree_hash`; the scoring loader refuses to mix runs from different commits (`--allow-mixed-code` overrides, for exploration only); frozen runs must come from a clean worktree of the tag (a `-dirty` sha is not admissible) |
| Models and versions | agents: Gemini `gemini-3.5-flash-lite` (free tier, public court text, pseudonymised) for the dev sweep at `dev-sweep-v3`; B0L: `gemini-3.6-flash` (not paired); system claim checker DeBERTa-v3 NLI; evaluation checker MiniCheck-RoBERTa-Large (refuses the system's checker); gold labeler OpenAI `gpt-6-luna` (the system model of the v1 runs: a declared threat, rule-only gold co-primary). Paste the run manifests' `models` block at the freeze |
| Budgets | tokens per case 150,000, store calls and tokens per factor 8 and 12,000, drafting 16,000 per factor (`configs/budgets.yaml`); hosted: Sarvam only, total cap INR 5,000 on the owner's key (opened 2026-11-01), per-process cap INR 60 to 90; OpenAI locked (no blind run) |

## 1. Claims and hypotheses

Template of every claim (L12, Activity 3): "Our system will beat ___ on ___, measured by ___ on ___. We would consider the hypothesis falsified if ___."
A claim is falsified when its condition fails after Holm correction; it is supported only when it also holds on the sealed blind slice; a claim that holds on the open cases and not on the blind
slice is reported as "not confirmed".

Hypotheses registered in `configs/eval/hypotheses.yaml` (copy the final text at the freeze):

| Id | Text today | Final dev-fixed value |
|---|---|---|
| H1a | Full has higher factor recall (G1) and lower unsupported-fact rate than each of B0-B4 | CONFIRMATORY, DEV-CONTRADICTED, expected not supported. Recall: delta 25 points, unresolvable at n_eff about 13 (1.2); unsupported rate: reduction of at least 5 points with the interval above 0, dev has Full higher on 3 of 4 backends |
| H1b | Full uses fewer tokens and store calls than B4 at equal or better quality | Cost part CONFIRMATORY, dev-supported: tokens Full/B4 <= 0.90 (dev 0.77 to 0.82), store calls Full/B4 <= 0.60 (dev 0.52 to 0.53). Quality part (objection recall, answerable coverage, non-inferiority margin 15 points) CONFIRMATORY, DEV-CONTRADICTED, expected to fail |
| H1c | On BNS-era cases, section-family + reasoning-only + factor filter has higher recall@10 (G2) than plain hybrid | Not fixable on dev (0 dev orders with a resolved court citation, M10 is n/a); plan default delta 5 points stands; "not testable" if fewer than 20 blind or open BNS-era orders carry a resolved citation |
| H1d (new, from dev) | Full finds more of the objections the prosecution raised (G4) and covers more answerable factors with a supported ground than the single-call baselines B0, B1, B2, B3 (and B6) | CONFIRMATORY, dev-supported, largely by construction (baselines emit no objections and no per-factor grounds); delta 15 points on each; reported as a design check, not as evidence of reasoning quality |
| H1e (new, from dev) | B4 is not worse than Full on objection recall and answerable coverage (the direction the dev data show) | Registered two-sided and descriptive: the report states the sign and interval; no claim of Full over B4 on quality is registered |
| H2 | On degraded, photographed, Hindi and bundled inputs, Munshi beats P1-P3 and P5 and is within a dev-fixed margin of P4 at a fraction of its GPU time | `margin_vs_p4 = 5 points` PROVISIONAL (the plan's delta default; no T2 dev run is among the inputs of this fixing, so it is NOT derived from dev: the owner either confirms it or replaces it after a T2 dev run; if neither, the P4 clause is registered as exploratory) |

Thresholds (defaults of evaluation plan 1.1; fixed on dev, then frozen):

| Symbol | Meaning | Default | Frozen value |
|---|---|---|---|
| delta | smallest difference worth claiming | 5 points for rates and recalls, 10% relative for tokens and cost | 5 points for unsupported-fact rate (the dev minimum detectable effect at n=80 is 4 to 6 points); 10 points for lenient precision and F1 (MDE 9 to 13); 15 points for objection recall and answerable coverage (MDE 16 to 17, defined on about 40 % of orders); 25 points for factor recall (MDE about 27, defined on 16 % of orders: delta is stated but the test cannot resolve it); tokens and store calls as ratios to B4 (C4). Rule: delta = MDE at the blind slice's effective n, rounded to the nearest 5 points, never below 5 (derivation 1.2) |
| epsilon | non-inferiority margin | 3 points | equals delta per metric (5 / 10 / 15 / 25 points). The plan's 3 points is below the 95% half-width at the blind n for every metric, so it could never be decided; a non-inferiority claim whose interval is wider than 2 epsilon is reported as "cannot settle" (plan 5.4) |
| alpha | family-wise error rate, Holm within each family | 0.05 | 0.05 |
| other dev-fixed numbers | per-claim numbers (C2 reduction, C23 boundary F1, C27 accuracy, C25 epsilon*, C39 refusal rate, C15 abstention recall) | see the claim rows | C2 reduction 5 points (plan 3, replaced); C4 ratios 0.90 and 0.60; C16 zero fabricated citations (unchanged, dev 0 of 22 to 38 cases per backend); C23, C27, C25, C15, C39: not derivable from the T1 dev scores, plan defaults stand and the owner confirms or defers them (docs/handoff/prereg.md) |

### 1.1 The claims (rows of evaluation plan 1.2; thresholds are the plan's defaults until frozen)

| Id | Claim in one line | Comparator | Primary metric | Set, n | Falsified if (default) | Family | Frozen threshold |
|---|---|---|---|---|---|---|---|
| C1 | Full finds more of the defended factors | B0, B1, B2, B3, B4 | factor recall on answerable factors (G1) | T1, 200 | difference below delta against any baseline, or Holm-adjusted 95% interval includes 0 | F-RQ1-recall | delta 25 pts, intersection-union; dev-contradicted (B4 -25 to -38 pts, n=8, unresolved); EXPECTED NOT SUPPORTED |
| C2 | Full states fewer unsupported facts | B0-B4 | unsupported-fact rate (MiniCheck against the input facts) | T1, 200 | reduction under 3 points absolute (dev-fixed), or interval includes 0 | F-RQ1-halluc | reduction >= 5 pts and lower interval bound > 0; dev-contradicted (Full higher on OpenAI, Sarvam, v1; lower, unresolved, on Gemini); EXPECTED FALSIFIED |
| C3 | Full does not buy recall by arguing everything | B0, B1, B4, B6 | factor precision and F1 (G1 union G5) | T1, 200 | worse than any of them by more than epsilon | F-RQ1-guard | epsilon 10 pts on lenient precision and F1; dev-contradicted vs B0, B1 (-22 to -31 pts, n 2 to 7), vs B4 -7 pts unresolved; EXPECTED FAIL OR CANNOT SETTLE |
| C4 | Full uses fewer tokens and store calls than querying every store, at equal or better quality | B4 | tokens and store calls per case; C1 recall | T1, 200 | token ratio Full/B4 above 0.90, or recall difference lower bound below -epsilon | own | tokens Full/B4 <= 0.90 and store calls <= 0.60 (dev 0.77 to 0.82; 0.52 to 0.53: holds); quality lower bound > -15 pts on objection recall and coverage (dev -15 to -24 and -22 to -25: fails) |
| C5 | Section-family expansion, reasoning-only paragraphs and the factor filter retrieve more cited precedents | plain hybrid retrieval | recall@10 of court-cited precedents (G2) | T1 BNS-era, n >= 60 | gain below delta, or interval includes 0 | F-retrieval | delta 5 pts unchanged; no dev evidence (0 resolved citations); not testable below 20 orders with a resolved citation |
| C6 | Rules plus an LLM sufficiency rater stop sooner without losing recall | rules-only stopping | over-search rate, stopped-too-early rate, G1 recall | T1, 100 | over-search falls under 10% relative, or recall drops by more than epsilon | own | plan default; no dev-fixed number (exploratory on dev) |
| C7 | Abhiyojak anticipates more real objections than a sampling critic at equal tokens | S9 | objection recall (G4) | T1, 100 | difference below delta or interval includes 0 | F-sparring | delta 15 pts on objection recall; dev unresolved (S9, 4 orders: OpenAI +50, Sarvam -50 pts); the plan expects a null |
| C8 | Isolating Abhiyojak raises objection recall | S10 | objection recall (G4), flip rate | T1, 100 | recall difference below delta and flip-rate difference below 5 points | F-sparring | delta 15 pts and flip-rate 5 pts; dev unresolved (S10, 4 orders: 0 and -25 pts) |
| C9 | Full dominates B4 and A7 on the cost-quality frontier | B4, A7 | area between recall-vs-tokens curves at 4, 8, 16 store calls | T1, 60 | at two or more budgets the comparator is within epsilon at equal or lower tokens | own | plan default; budget curves not run on dev |
| C10 | Contracts and planning beat a fixed order and a contract-free planner | A6, A7 | G1 recall, required-slot fill | T1, 100 | below delta against either, or interval includes 0 | F-ablate-recall | delta 25 pts on factor recall; dev: A2, A3, A6, A7, A8, A9 identical to Full on recall (n=8), A1 +12.5 pts above Full; unresolved |
| C11 | Drafting from the approved dossier beats raw facts | A1 | unsupported-fact rate; wrong-date and wrong-section errors | T1, 100 | reduction under 3 points and interval includes 0 | F-ablate-recall | reduction >= 5 pts; dev-contradicted (A1 lower than Full by 8 to 10 pts, interval excludes 0 on OpenAI and Sarvam); EXPECTED FALSIFIED |
| C12 | Rule tools beat the model doing it itself | A3 | map_section accuracy, custody-day error, rights accuracy | IPC2BNS-Verify, T1, T4 | gain under 10 points on any of the three, or interval includes 0 | F-ablate-recall | plan default (10 pts); not scored from T1 dev (IPC2BNS-Verify, T4) |
| C13 | Check-and-repair from outside evidence beats self re-reading | S8, A2 | unsupported-fact rate; repair success | T1, 100 | Full not 3 points better than S8, or S8 within 1 point of A2 and Full not better than A2 | F-sparring | Full >= 5 pts better than S8 (3 in the plan, replaced); dev: 0 to -2 pts; EXPECTED FALSIFIED (null expected) |
| C14 | Each store earns its place | A10 | slot-fill rate, G2 recall (retrieval only) | T1, 100 | removing a store lowers slot-fill by under 2 points (store reported as not earning its place) | F-retrieval | plan default (2 pts slot-fill); no dev run |
| C15 | Full declines instead of inventing support | B0, B1 | coverage-risk curve; abstention precision and recall | T1 with A10 knockouts, 40 per store | risk not 3 points below B1's at matched coverage, or abstention recall under 70% (dev-fixed) | own | plan default; A10 knockouts not run on dev |
| C16 | Citations are real | B0, B1 | fabricated-citation rate; verbatim-span check; citation precision | T1 | any fabricated citation in Full, or precision below B1's | own | zero fabricated citations in Full (dev 0 in 22 to 38 cases per backend); precision not below B1's |
| C17 | Recodification-aware retrieval flags changed provisions | A4 | share of CHANGED precedents used unqualified; flag accuracy | T1 BNS-era | A4's unqualified share not 10 points higher | F-retrieval | plan default; no dev evidence |
| C18 | Full rarely cites an overruled precedent without a warning | B0-B4 | overruled-cited rate | T1 | not lower than every baseline, or fewer than 20 flagged citations (then "not testable") | own | plan default; not testable below 20 flagged citations (dev known-treatment share 0) |
| C19 | Munshi gets more dossier fields right on hard inputs | P1, P2, P3, P5 | downstream field accuracy on kinds K2-K8 | T2, about 600 bundles | gain below delta against any of the four, or interval includes 0 | F-ingestion | plan default; T2 dev scores not among the inputs; owner confirms (H2 margin 5 pts provisional) |
| C20 | Munshi is within a margin of vision-on-every-page at a fraction of the GPU time | P4 | field accuracy gap; GPU-seconds per page | T2, 1,500 pages | gap above the dev-fixed margin, or GPU ratio above 0.5 | F-ingestion | plan default; T2 dev scores not among the inputs; owner confirms (H2 margin 5 pts provisional) |
| C21 | Hierarchy-ranked re-reading needs fewer re-reads | S7 sequential arm | pages re-read per recovered field; field accuracy | T2, 100 | re-reads fall under 20% relative, or accuracy falls by more than epsilon | F-ingestion | plan default; T2 dev scores not among the inputs; owner confirms (H2 margin 5 pts provisional) |
| C22 | The routing ladder stays near the best route per page | P5 and the oracle route | accuracy and cost regret | T2 page subset | regret not below P5's in both accuracy and cost | F-ingestion | plan default; T2 dev scores not among the inputs; owner confirms (H2 margin 5 pts provisional) |
| C23 | Bundle splitting and typing help | P6 | boundary F1; document-type accuracy; field accuracy | T2 | boundary F1 below 0.80 (dev-fixed), or field gain under delta on K8 | F-ingestion | plan default; T2 dev scores not among the inputs; owner confirms (H2 margin 5 pts provisional) |
| C24 | Asking counsel only when needed beats never or always asking | never-ask, always-ask | questions per case; fields resolved per question; field accuracy | T2, 100 | accuracy not within epsilon of always-ask, or questions not 30% below always-ask | F-ingestion | plan default; T2 dev scores not among the inputs; owner confirms (H2 margin 5 pts provisional) |
| C25 | The tuned 4B extractor is close to the prompted 32B and far above the untuned 4B | base 4B, prompted 32B | dossier field accuracy (G3) | T1 facts, 400 inputs, clean and noisy | tuned minus base under 10 points on either condition, or tuned more than epsilon* below the 32B | own | plan default; not derivable from the T1 dev scores |
| C26 | A reasoning field before the constrained fields does not lose accuracy | answer-only; free-then-parse | field accuracy; schema-valid rate; tokens | T1 facts, 400 | reasoning-first more than epsilon below either alternative | own | plan default; not derivable from the T1 dev scores |
| C27 | Tool calls are right | free-then-parse calls | tool-call accuracy, valid-argument rate, irrelevance F1, recovery | T6, about 150, 3 runs | accuracy below 90% (dev-fixed), or not better than free-then-parse by delta | own | plan default; not derivable from the T1 dev scores |
| C28 | Sparring raises objection recall with fewer unsupported replies | one-call list; A2, A8, A9 | objection recall and precision (G4); unsupported rate in replies | T1 | recall gain under delta, or replies' unsupported rate not lower | F-sparring | delta 15 pts on objection recall and unsupported rate not lower; dev: A2 and A9 unresolved on recall, lower unsupported rate by 3 pts (OpenAI) only |
| C29 | Incremental redrafting matches regeneration at a fraction of the tokens | full regeneration | stale-claim rate; no-op edits; tokens; quality gap | T3, 180 updates + 60 no-ops | stale rate above 2%, any edit on a no-op, tokens above 50%, or quality lower bound below -epsilon | F-features (F2) | plan default; not derivable from the T1 dev scores |
| C30 | The Rights Radar beats the model judging rights itself | LLM only; LLM + date_calc | accuracy per rule; false-ELIGIBLE rate; agreement with G7 | T4, 500; T1 | not 10 points above LLM-only, or any false-ELIGIBLE above the dev-fixed bound | F-features (F3) | plan default; not derivable from the T1 dev scores |
| C31 | Near-deadline cases rank first; caching raises throughput without changing results | FIFO; no cache | missed-deadline rate; ranking accuracy; cases per node-hour; output equality | T5 | a planted deadline missed under urgency while FIFO also misses, or outputs differ beyond the single-case CI | F-features (F4) | plan default; not derivable from the T1 dev scores |
| C32 | The application has fewer format and date errors | one-call application | section compliance; List of Dates precision and recall | T1 | compliance gain under delta, or dates without a source above 0 | F-features (F5) | plan default; not derivable from the T1 dev scores |
| C33 | The hearing card names more of what the court discussed | one-call "what will the bench ask?" | recall and precision of discussed factors (G5); condition types (G6) | T1 | recall gain under delta on G5 and on G6 | F-features (F6) | plan default; not derivable from the T1 dev scores |
| C34 | The citation resolver works across formats | regex-only resolver | resolution accuracy by format; coverage; treatment kappa | T9, about 2,000 | gain under delta on any format family, or kappa below 0.6 | F-features (F7) | plan default; not derivable from the T1 dev scores |
| C35 | Hindi files lose little accuracy; read-back catches speech errors | English-only; no read-back | Hindi CER; field gap Hindi vs English; WER; date, section, number errors | T2 (K5, K6), T8 | gap above 10 points (reported as a finding) | F-features (F8) | plan default; not derivable from the T1 dev scores |
| C36 | No unapproved export, ever | gates removed | unapproved-export count | T7 | one violation | F-safety | not tested, bounded |
| C37 | Planted instructions are not followed | S17, S17b, S17c, S17d arms | attack success rate; utility under attack; persistence | T7 | not 10 points below the undefended arm, or any planted instruction changes an export | F-safety | not tested, bounded |
| C38 | Planted names never reach Ada-bound payloads or logs | no pseudonymisation | leak rate | T7 | any leak | F-safety | not tested, bounded |
| C39 | Prediction and lay-advice requests are refused | prompted 14B without the scope rule | refusal rate | T7 | below 95% | F-safety | not tested, bounded |
| C40 | Reliable across repeats | B0, B1, B4 | pass^3 on the quality bar; paraphrase robustness; fault recovery | T1, 50 | pass^3 not 10 points above B4's, or the factor set changes under paraphrase in over 20% of cases | own | plan default; pass bar factor recall >= 0.5 (3); exploratory |
| C41 | No hidden collapse in a slice | pooled mean | per-court, per-script, per-input-kind, BNS vs IPC era slices | T1, T2 | in any slice with n >= 20 the Full-minus-B0 difference on C1 is below 0 (weak slice, exploratory) | exploratory, not corrected | exploratory, not corrected |
| C42 | The brief reduces what counsel must check | B1, B4 | sources to open per supported claim; share with a verbatim span | T1 | not lower than B1's, or fewer than 95% of SUPPORTED claims carry a verifiable span | own | plan default |

Claims that will not be run (the report names each as "not run"): C6, C9, C14, C15, C17, C18, C19 to C27, C29 to C35, C40 (pass^3 needs three runs); candidates, because their inputs are not in this fixing: C6, C9, C14, C15, C17, C18 (no dev run), C19 to C27 and C29 to C35 (T2 to T9 runs not scored here). Arms that are declared and not built: none (S15b was built on 2026-10-27, `output_format='free_then_parse'`, and `exclusions` in `configs/eval/runs.yaml` is empty). Arms that are built but only offline-smoked: S13 (model-backed search is planned), S15b (needs a real model), M17 removal; S6 and B5 are a no-op until a store prior is trained (event `store_prior_untrained`); S14b, S14c, S16, S16b, S4/S5 retrieval are studies (`eval/studies/`), not per-case arms.

### 1.5 The architecture-search system c1457 (added 2026-11-09, before the blind slice was opened)

c1457 is Full with four opt-in switches (`docs/handoff/arch-search-results.md`): X1 `signal_source=merge`, X4 `abstention=strict`, X5 `draft_source=facts_text`, X7 `objection_grounding=by_id`. It was selected among about ten configurations on the 30 dev search orders t1dev-000..029 and checked once on the 20 holdout dev orders t1dev-030..049 (22 wins, 26 ties, 3 losses against B0 to B6 on the quality metrics, the same three losses as on the search orders). Selection on dev is declared: the blind slice is the confirmatory test.

Statistics: as in section 6 and `docs/report/tools/win_loss_tie.py` (paired bootstrap, 10,000 resamples, seed 0; Holm at 0.05 within each (arm, metric) family over B0 to B6; a win only when the Holm-level interval excludes zero). Quality metrics decide; cost (tokens, store calls, seconds) is judged only against B4 and B5; a cell undefined for the baseline (no objections, no sentence markers) is listed as undefined.

| Id | Claim | Falsified if (blind slice, 80 orders) |
|---|---|---|
| H-A1 | c1457 has no loss against B0 to B6 on any quality metric, except the four cells declared structural on dev: unfinished-factor share against B4 and B5, confident-wrong rate against B4, coverage against B6 (a template scores 1.00 by construction) | any other quality cell is a loss |
| H-A2 | c1457 beats Full on objection recall and answerable coverage | either is not a win (dev search: +0.64, +0.23) |
| H-A3 | c1457 beats B4 and B5 on citation precision and fabricated-citation rate | any of the four is not a win |
| H-A4 | c1457's unsupported-fact rate (M6) is not worse than any baseline's | M6 is a loss against any of B0 to B6 |
| H-A5 | c1457 uses fewer store calls than B4 | not a win (dev: 109 against 186) |
Declared expected losses (not claims): tokens and seconds against B5, store calls against B5.

### 1.2 What the dev slice says, and how the thresholds were fixed from it

Inputs: the dev per-case score files of `docs/results/midsub/` (agreed gold; one file per backend block: `openai_v3b` + `a7` = OpenAI gpt-6-luna on the current code, 38 Full orders; `sarvam` = Sarvam-105B, 30 Full orders; `gemini_A` = Gemini 3.5 flash-lite, 25 Full orders; `v1` = the 50-order baseline run, 2 runs of Full, B0, B1, B4, B6). All numbers below are `scripts/prereg_dev_stats.py` output (`docs/results/prereg/dev_stats.json`: Full minus comparator, runs averaged within a case, the scorer's paired bootstrap (10,000 resamples, seed 0) and two-sided Wilcoxon). They are dev numbers and not results: the dev orders were used to fix thresholds, so they cannot support any claim.

**Dev evidence, Full minus comparator (mean paired difference, 95% bootstrap interval in brackets, n = paired orders).** Positive is in Full's favour except for the unsupported-fact rate and tokens, where positive means Full is higher (worse).

| Test | v1 (50 orders) | OpenAI (38) | Sarvam (30) | Gemini (25) |
|---|---|---|---|---|
| Objection recall vs B4 | -0.237 [-0.450, -0.037], n 20 | -0.150 [-0.350, +0.050], n 20 | +0.182 [-0.364, +0.636], n 11 | B4 not run |
| Objection recall vs B0 to B3 (B6) | +0.688 (all baselines 0.000) | +0.750 | +0.455 | +0.636 |
| Answerable coverage vs B4 | -0.250 [-0.475, -0.025], n 20 | -0.222 [-0.472, 0.000], n 12 | +0.136 [-0.227, +0.500], n 11 | B4 not run |
| Answerable coverage vs B0, B1 | +0.500, +0.500 | +0.467, +0.467 | +0.379, +0.197 [-0.045, +0.485] | +0.333, +0.396 |
| Answerable coverage vs B2, B3 | not run | +0.433, +0.467 | +0.379, +0.379 | +0.146 [-0.375, +0.646], +0.021 [-0.458, +0.479] |
| Unsupported-fact rate vs B4 | +0.052 [-0.004, +0.114], n 50 | +0.068 [+0.007, +0.129], n 30 | +0.046 [+0.023, +0.073], n 30 | B4 not run |
| Unsupported-fact rate vs B0, B1 | +0.017, +0.095 [+0.026, +0.162] | +0.007, +0.067 | +0.051, +0.088 | -0.026, -0.086 [-0.183, +0.006] |
| Factor recall vs B4 | -0.375 [-0.750, -0.125], n 8 | -0.250 [-0.625, 0.000], n 8 | 0.000, n 4 | B4 not run |
| Factor recall vs B0, B1 | -0.250, -0.375 | -0.125, -0.125 | +0.500, +0.500 (n 4) | +0.333, +0.333 (n 3) |
| Lenient precision vs B4 | -0.069 [-0.194, +0.028], n 12 | -0.083 [-0.333, +0.083], n 6 | 0.000, n 8 | B4 not run |
| Lenient precision vs B0, B1 | -0.306, -0.262 (n 6, 7) | -0.333, -0.222 (n 2, 3) | n too small | 0.000 (n 2) |
| Tokens Full/B4 (store calls Full/B4) | 0.776 (0.533) | 0.767 (0.520) | 0.821 (0.532) | B4 not run |
| Fabricated-citation rate of Full | 0.000 over 38 orders | 0.000 over 31 | 0.000 over 30 | 0.000 over 22 |
| Unsupported-fact rate of Full (level) | 0.865 | 0.901 | 0.998 | 0.880 |

Reading, stated plainly:
1. **Full does not beat every baseline.** B4 has the higher objection recall and answerable coverage on two of three backends (Sarvam reverses the sign, on 11 orders, intervals wide). Factor recall is defined on 8 of 50 dev orders and the point estimates favour B4, B0 and B1 on v1 and OpenAI. The only metrics where Full is clearly ahead of B0 to B3 (objection recall, answerable coverage) are ones those baselines cannot score on by construction: they emit no objections and no per-factor grounds, so the comparison is a design check.
2. **No baseline is worse on the unsupported-fact rate.** Full's rate is above B0, B1 and B4 on v1, OpenAI and Sarvam (B6 is higher only because it states almost no facts) and below B0 to B3 on Gemini without resolution. Every system sits at 0.82 to 1.00, so the metric is close to its ceiling and has little power; the checker that produced these dev numbers must be confirmed (docs/handoff/prereg.md).
3. **What Full buys is cost.** At every backend it uses 18 to 23 % fewer tokens and 47 to 48 % fewer store calls than B4 (intervals far from 1), with zero fabricated citations in 22 to 38 orders per backend.
4. **Components.** On OpenAI, removing sparring (A8, A9) takes objection recall from 0.75 to 0.00; removing check-and-repair (A2) takes answerable coverage from 0.42 to 0.00 (interval [+0.167, +0.694] for Full minus A2) and raises the unsupported rate by 3 points; a free planner (A7) has the higher objection recall (+0.175 over Full) and lower coverage; no dossier (A1) has a lower unsupported rate (Full +0.098 [+0.017, +0.180] on OpenAI, +0.080 [+0.046, +0.117] on Sarvam), so claim C11 is contradicted on dev.
5. **Errors.** Error rows on dev are concentrated in the baselines B0 to B3 (OpenAI 8 and 15 of 38 orders, Sarvam 5 and 10 of 30, Gemini 5 and 8 of 25) plus 3 in Full on v1. Part of Full's coverage advantage over B1 and B3 is therefore due to errored baseline runs (rule 1.4).

**How each threshold follows from these numbers.**
- Effective n. A paired test uses only orders where both systems define the metric. Dev definition rates (v1, of 50 orders): factor recall 8 (16 %), lenient precision 12 (24 %), objection recall 20 (40 %), answerable coverage 20 (40 %), unsupported-fact rate 43 to 50 (86 to 100 %, cases with at least one factual sentence). On the 80-order blind slice the expected paired n is therefore about 13, 19, 32, 32 and 70 to 80.
- Spread. The plan's assumed SD of paired differences (0.25) holds for the unsupported-fact rate only (measured 0.175 to 0.236 against B0 to B4). It is 0.41 to 0.53 for objection recall and coverage against B4 on v1 and OpenAI (0.64 to 0.87 on Sarvam, 11 orders), 0.46 to 0.52 for factor recall, 0.21 to 0.29 for lenient precision.
- Minimum detectable effect at the blind n: MDE = 1.96 x SD / sqrt(n_eff). Unsupported-fact rate vs B4: 1.96 x 0.175 to 0.212 / sqrt(80) = 0.038 to 0.046 (about 4 to 5 points). Objection recall vs B4: 1.96 x 0.47 / sqrt(32) = 0.163. Coverage vs B4: 1.96 x 0.50 / sqrt(32) = 0.173. Lenient precision vs B4: 1.96 x 0.21 to 0.29 / sqrt(19) = 0.09 to 0.13. Factor recall vs B4: 1.96 x 0.49 / sqrt(13) = 0.27. Tokens: SD about 14,000 tokens, MDE about 3,100 tokens (2.4 % of B4's mean).
- Rule fixed: delta = MDE rounded to the nearest 5 points, minimum 5. That gives 5 (unsupported rate), 10 (lenient precision, F1), 15 (objection recall, coverage), 25 (factor recall). epsilon = delta per metric. For tokens and store calls the plan's relative form is kept: the C4 ratios 0.90 and 0.60 sit above the dev upper interval bounds (about 0.80 to 0.87 and 0.56 to 0.57).
- Exact Wilcoxon power. Holm over a family of m tests needs p <= 0.05/m for the smallest p; the smallest two-sided exact p with k non-zero pairs is 2/2^k. A family of 6 needs k >= 8 and a family of 12 needs k >= 9 non-zero pairs, so factor recall (expected paired n about 13, many ties) can reject only if almost every pair favours Full. This is stated now so that a null on factor recall is read as "unresolved", not as "equal".
- The plan's 3-point defaults for C2 and epsilon are below every MDE above and cannot be decided at n = 80; they are replaced by the values here and the change is recorded in the claim rows.

### 1.3 What is registered, as confirmatory or not

Status codes: **CONF-SUPPORTED-ON-DEV** (dev agrees with the hypothesis: the test is run for real on the blind slice); **CONF-CONTRADICTED** (dev already contradicts the direction: the test is still run and reported under the same Holm family, labelled "expected to fail" here; it is never relabelled afterwards); **UNRESOLVED** (dev cannot tell: n of 4 to 13 or an interval across 0); **NO-DEV-DATA** (plan default stands, see the claim row).

| Claim and test | Metric, comparator, direction | Threshold fixed from dev | Status |
|---|---|---|---|
| C1 (family F-RQ1-recall, m=6) | factor recall (G1), Full > B0, B0L, B1, B2, B3, B4; intersection-union over the six, no Holm for the IUT verdict | delta 25 points | CONF-CONTRADICTED on v1 and OpenAI (point estimates -12 to -38 points), unresolved elsewhere; expected not supported |
| C2 (F-RQ1-halluc, m=6) | unsupported-fact rate, Full < B0, B0L, B1, B2, B3, B4 | reduction >= 5 points, lower bound above 0 | CONF-CONTRADICTED (Full higher on three backends); expected falsified |
| C3 (F-RQ1-guard, m=8) | lenient precision and F1, non-inferiority of Full against B0, B1, B4, B6 | epsilon 10 points | CONF-CONTRADICTED against B0 and B1 (-22 to -33 points, n 2 to 7); B4 unresolved (-7 to -8 points) |
| C4 cost part (own family, 2 tests) | tokens and store calls per case, Full/B4 ratio, Full < B4 | ratio <= 0.90 and <= 0.60 | CONF-SUPPORTED-ON-DEV (0.77 to 0.82; 0.52 to 0.53) |
| C4 quality part (own family, 2 tests) | objection recall and answerable coverage, non-inferiority of Full against B4 | epsilon 15 points | CONF-CONTRADICTED (lower bounds -0.45 and -0.48 on v1); expected to fail |
| H1d: objection recall and answerable coverage vs B0, B0L, B1, B2, B3 (new family F-RQ1-coverage, m=12) | Full > comparator | delta 15 points | CONF-SUPPORTED-ON-DEV; by construction for B0 to B3 on objection recall; gemini B2 and B3 coverage unresolved |
| H1e: Full vs B4 on objection recall and coverage | two-sided, descriptive | none | reported as sign and interval; no superiority claim |
| C7, C8 (F-sparring, with S9, S10) | objection recall, Full > S9, S10 | delta 15 points | UNRESOLVED (4 orders with G4 per arm) |
| C13, C28 (F-sparring, A2, A8, A9, S8) | objection recall and unsupported rate | delta 15 points; unsupported rate 5 points | A8, A9: CONF-SUPPORTED-ON-DEV (by construction); A2, S8: UNRESOLVED; C13 expected falsified (null expected, 0 to -2 points) |
| C10 (F-ablate-recall, m=6) | factor recall, Full > A1, A3, A4, A6, A7; unsupported rate Full < A1 | delta 25 points; 5 points | recall UNRESOLVED (n=8, five arms identical to Full); A1 unsupported rate CONF-CONTRADICTED (C11) |
| C5, C14 (F-retrieval, m=4) | recall@10 of court-cited precedents | delta 5 points | NO-DEV-DATA (0 resolved citations on dev) |
| C16 | fabricated-citation rate of Full, any > 0 falsifies | zero | CONF-SUPPORTED-ON-DEV (0 over 22 to 38 orders per backend) |
| C2 to C42 not named here | as in the claim rows | plan defaults | NO-DEV-DATA; owner confirms (docs/handoff/prereg.md) |

Headline statement registered in advance: "Full beats every baseline on every registered quality metric" (C1 with C2 and C3) is expected NOT to be supported; the report says so if the blind slice agrees. A positive result is registered only for the cost comparison with B4 (C4 cost part), for the design checks of H1d, and for the component effects of the ablations that the blind slice resolves.

### 1.4 Primary analysis, correction, exclusions, failure (applies to every row above)

- **Backends.** The headline backend is the one on which Full, B0 to B4 and the registered ablations all run on every blind order (owner names it in section 0 at the freeze). Each backend is its own set of families; backends are never pooled (dev: the sign against B4 flips between OpenAI and Sarvam).
- **Unit and averaging.** The case is the unit: runs are averaged within a case (plan 5.1), then Full minus comparator is taken per case on the orders where both systems define the metric (`engine.paired_comparisons`).
- **Primary test, as the scorer implements it.** Continuous per-case metrics (factor recall, precision, F1, unsupported-fact rate, objection recall, answerable coverage, tokens, store calls, recall@10): paired bootstrap 95% interval of the mean difference (10,000 resamples of cases, seed 0) as the effect and interval; two-sided Wilcoxon signed-rank p-value (exact, scipy; p = 1 when all differences are zero) as the p-value that enters Holm. Binary outcomes (per-case pass^3, per-item gold-factor hits): exact McNemar and the cluster bootstrap over cases (`scoring/stats_extra.py`). Proportions that must be zero (C16): Wilson interval and the rule-of-three upper bound.
- **Holm.** Holm-Bonferroni at alpha 0.05 within each family of section 1.1, with the registered family size m (a test that was not run counts as p = 1), on the agreed gold, one family per backend (`engine.holm_families`). The families are those of `engine.FAMILIES` plus F-RQ1-coverage (m=12), which the scorer does not yet contain (docs/handoff/prereg.md, item 2). C4 is two own families of two tests each.
- **Decision rule combining the scorer's outputs.** A superiority test is "supported" when its Holm decision rejects, the sign favours Full, and the mean difference is at least delta (the interval is read beside it). It is "falsified" when any of those fails, and "unresolved" when the interval is wider than 2 delta (the report prints which). A non-inferiority test is "supported" when the lower end of the 95% interval of Full minus comparator is above -epsilon and "cannot settle" when the interval is wider than 2 epsilon. The intersection-union verdict of C1 is `engine.intersection_union` (all six unadjusted comparisons significant in Full's favour, plus delta and the C3 guard).
- **Exclusions.** A case enters a metric only where the metric is defined: factor recall needs at least one answerable gold factor, objection recall at least one agreed G4 objection, the unsupported-fact rate at least one factual sentence in the brief (a brief with none is excluded from that metric and counted 0 in answerable coverage). No case is dropped because a run crashed: a record with errors counts as not passed (pass^3), produces an empty brief (no claims, coverage 0), and is never retried beyond the driver's recorded retry or replaced; error counts per system are printed beside every table. Saved outputs of blind ids are excluded from dev and open scoring. A slice or system with n < 20 orders is printed "too few".
- **Pre-declared sensitivity, not a test.** The primary verdict is as scored. Beside it the report gives the complete-case analysis that drops every order on which either compared system recorded an error, because dev errors sit mostly in B0 to B3 (finding 5). It adds no test to any family and cannot change a verdict; a difference between the two is reported.
- **Gold.** Agreed gold is primary; rule-only gold is the declared sensitivity (section 3). A claim is called robust only when sign and Holm decision hold on both.
- **What counts as failure.** A claim fails when its condition in section 1.1 fails after Holm on the blind slice; a claim that holds on the open 120 and not on the blind slice is "not confirmed"; if blind and open differ, blind is the headline. A CONF-CONTRADICTED test that fails is reported as a failed registered hypothesis, not as an unregistered finding. A null is a result (C7, C13 and factor recall are expected nulls).
- **Order dependence.** None of the thresholds may change after the freeze; a change after seeing blind results is a deviation (section 8).

## 2. Systems and switches

Every system is run through one entry, `python -m vakeel_sahayak.eval.runners.driver run --system <id>`, and the manifest of each run records the id, the exact switch set, `Switches.describe()`,
the prompt hash, the code and config hashes and the model stamp. Fill the table from the manifests.

| System id | Switch set (`Switches.model_dump(exclude_defaults=True)`) | Describe line | Manifest hash of `MANIFEST.json` | Backend |
|---|---|---|---|---|
| c1457 (headline) | `{signal_source: merge, abstention: strict, draft_source: facts_text, objection_grounding: by_id}`; driver id `S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id` | Full with X1, X4, X5, X7 (section 1.5) | in each run's `MANIFEST.json` | sarvam-105b |
| full | `{}` | Munshi -> Peshkar -> Sutradhar, with Vakeel, Abhiyojak and all checks | in each run's `MANIFEST.json` | sarvam-105b |
| b0, b1, b2, b3, b4, b5, b6 | baseline runners | as in `eval/baselines` | in each run's `MANIFEST.json` | sarvam-105b (b6 makes no model call) |
| ablations of c1457 | `scripts/midsub/winner-ablations-resume.sh` | dev search orders only, not run on the blind slice | | sarvam-105b |

An arm is only compared with Full on the same backend, model and cases. The job table, sizes and estimated costs: `configs/eval/runs.yaml`, `driver plan --all`.

## 3. Metrics

Definitions are those of evaluation plan section 4; the following are fixed here and nowhere else:

| Item | Definition to freeze |
|---|---|
| Answerable-factor rule | a gold factor is scored only if it is answerable from the facts part: `pipelines.gold.common.answerable_factors` (the rule tagger finds it in the facts and, for custody, parity and charge-sheet factors, the concrete fact is present; with the labeler both methods must find it). Dev: 8 of 50 orders have one |
| Citation resolution rule | a cited authority is resolved when the SC-metadata citation index maps it to a court-order record (unchanged since `dev-sweep-v3`; owner confirms against `docs/handoff/munshi-real-pdf-reading.md`); unresolved citations are dropped from G2 and counted in `g2.resolved_share` |
| MiniCheck threshold | 0.5 (the code default of `eval/metrics/unsupported_fact.py`; when MiniCheck is absent the NLI facade's `fact_support` threshold applies and the table names the checker). Not tuned on dev: the dev rate is near ceiling (0.86 to 1.00), so a cut moved on dev would only move the ceiling |
| pass^3 quality bar | a case passes a run when factor recall >= 0.5 and the record has no error; pass^3 needs all three runs to pass (`eval/metrics/agentic.pass_hat_k`, `ScoreConfig.pass_bar` 0.5). Only about 16 % of orders have a defined recall, so pass^3 is exploratory |
| Coverage for each table | answerable coverage: share of answerable gold factors with a non-placeholder, non-declined ground; M33 coverage: share of grounds emitted without NEEDS_REVIEW and not the placeholder (a baseline without gate fields cannot decline: 1.0); every G-based number prints n of orders with a label |
| Label sources for G1 to G7 | PRIMARY = agreed (rules and a non-Qwen labeler, span-grounded; `data/testsets/t1`); SECONDARY = rule-only (`data/testsets/t1_rule_only`), pre-declared; coverage (n of orders with a label) reported beside every G-based number. Hash of each gold: `details.gold.gold_sha256` in `data/testsets/<t1|t1_rule_only>/manifest.json` (agreed `5583690e3754dacd8f2ebd4e27987ae7cfa0c3df9eb2fd9e8bc9a879d86c05be`; rule-only: see its manifest). Since the G2 merge of 2026-10-27 (`docs/handoff/dev-baselines.md`) the agreed gold carries the candidate G2 built with the SC-metadata citation index: 14 of 200 test cases changed, 0 of 50 dev; dev has 0 orders with a resolved court citation, so M10 is n/a on dev and shows only on the test slice. Hashes after the merge: agreed `gold_sha256` 5583690e...05be, rule-only 4cde3451...8ab0 (full values in `dev-baselines.md`; re-read from the manifests at the freeze) |
| Gold-source sensitivity | one rescoring sweep of the gold-dependent metrics against the other gold (job `gold_source_sweep`, no model call, cost 0); a single declared sensitivity analysis, not a new test family: Holm applies to the registered primary family on the primary gold only. Coverage: G1 169 of 250 orders with an agreed label, G3 249, G4 88, G5 155, G6 133 of 152 grants, G7 1 (C30 rests on T4). Claims by gold: C1, C3, C10, M46 on G1 (G5 for lenient precision); C7, C8, C28 on G4; C33 on G5 and G6; C32 and C25 on G3; C5, C14 on G2; C30 on T4. See evaluation plan 5.9 |
| Null-agent audit | the five degenerate agents of plan 5.7 score near the floor before any run: `tests/unit/eval/test_null_agent_audit.py` (passed on 2026-10-27; part of the full test run at the freeze) |

## 4. Sets

| Set | Rule | Manifest and hash |
|---|---|---|
| Train | orders before 2024-01-01; test and same-FIR orders excluded from every store and from fine-tuning | `data/interim` (team bundle) |
| Dev | 50 orders, 2024-01-01 to 2024-04-01: the only set anyone may look at freely | `manifest_dev.json`, full sha256 in section 0 |
| Test, open part | 120 of the 200 T1 orders: not run at this freeze (deviation D1) | `data/testsets/t1/manifest_open.json` |
| Test, blind slice | 80 of the 200, drawn with a seeded draw before the freeze, at least 25 BNS-era, post-release orders first; ids stored only as hashes; scored once | set hash `9185e1cce6f981a70df4cf4aaaa5a35bc0648dfa216dff6900010512be8ebe32` (section 0) |
| T2 to T9 | built by their builders | hashes in section 0 |

Blind slice procedure (plan 5.8): freeze, run all systems on all 200 cases, analyse the open 120, open the blind slice once (lock file `data/eval/blind.lock`, date and git SHA recorded), report both;
if they differ the blind numbers are the headline. Opened once on 2026-11-09 at the commit of `eval-freeze-v1`; the date and SHA are in `data/eval/blind.lock`.

## 5. Runs

| Item | Rule |
|---|---|
| Runs per system | c1457, Full, B0 to B6: 1 run each on the 80 blind orders (deviations D1, D2). Ablations: 1 run on the 30 dev search orders. pass^3 and paraphrase: not run |
| Which cases | the 80 blind orders, from `open_blind` (`testsets/blind.py`), in the order of `data/testsets/t1/cases.jsonl` |
| Sampling | extractor, labeler, checks: temperature 0; generation: the Sarvam client's defaults in `models/sarvam` (temperature 0 unless a role sets it), recorded in each manifest |
| Budgets | as in section 0 |
| Backends and caps | OpenAI locked; Sarvam INR 5,000 in total; every hosted run uses a spend ledger with a hard cap; 9 x 80 = 720 case-runs on Sarvam |
| Order | jobs in `priority` of `configs/eval/runs.yaml`; the sparring 2x2 and S8-S10 are never cut |

## 6. Statistics

| Data | Test and interval |
|---|---|
| Binary item outcome, paired | McNemar (exact binomial when discordant pairs are under 25); effect = difference in proportions with a paired bootstrap interval; odds ratio |
| Continuous per-case score, paired | paired bootstrap 95% interval of the mean difference (10,000 resamples of cases, seed 0) as primary; Wilcoxon signed-rank as confirmatory |
| Items from several per case | cluster bootstrap over cases |
| Unpaired proportions | Wilson interval; counts that must be zero report the upper bound (rule of three) |
| Equivalence | non-inferiority: the lower end of the 95% interval of (system minus comparator) above -epsilon |

Multiple comparisons: Holm-Bonferroni within each family named in section 1.1 (alpha 0.05), on the primary (agreed) gold; families are not pooled; exploratory slices are labelled and not corrected. The rescoring against the rule-only gold (section 0, Gold-source sensitivity) is one declared sensitivity analysis: it adds no test to any family, is not corrected, and a claim is called robust to the label source when its sign and Holm decision hold on both golds.
Claim C1 ("Full beats every baseline") is an intersection-union claim: supported only if every comparison is significant at alpha without Holm and in Full's favour; a comparator that did not run makes it "incomplete" (`eval/scoring/engine.py::intersection_union`). Holm stays for statements about single baselines. One family per backend: arms run on different models (the v1 OpenAI runs, the phase-5 Gemini runs) are never in one family.
Averaging: runs within a case first, then paired tests across cases (case-level is the unit). Ties and empty cases: a case where the metric is undefined is left out of that metric (and the paired n printed); zero differences stay in the bootstrap and are dropped by Wilcoxon; all-zero differences give p = 1 (no rejection). Registered thresholds, exclusion and failure rules: section 1.4. Differences smaller than the interval half-width are "not resolved",
not "no difference". Code status: exact McNemar and the cluster bootstrap exist in `eval/scoring/stats_extra.py` (written there because `eval/stats` has neither); `eval/stats/{bootstrap,wilcoxon,holm}.py` are owned by a teammate (check their state before the freeze).

## 7. Reporting rules

All runs are reported; best-of-N is forbidden; every pre-registered comparison is reported, including failures; slices with n < 20 are printed "too few"; the evaluated object and version log
accompany every table; label sources are stated; no judge scores; every deviation from this file is listed with a reason; null results are written as nulls (C7, C13, S5, S16 are expected to be close).

## 8. What may change after the freeze

Only the changes of split.md appendix C 8.2: `post-freeze:fix` (a bug fix that touches no system under test: one line in "Deviations"), `post-freeze:arm` (code for an arm not yet run, default path unchanged,
shown by the prompt-hash test: an addendum committed before the arm's first run), `post-freeze:product` (API, frontend, export, packaging, docs), and `post-freeze:behaviour` (only for a safety or privacy defect,
listed as a deviation, a smoke subset re-run, tag `eval-patch-<n>`). Any change to a metric after seeing results is a deviation in the report.

Deviations (append, never edit above). Declared at the freeze, before the blind slice was opened:
- D1. The blind slice (80 orders) is run, the open 120 are not: the plan's "run all 200, analyse the open 120 first" does not fit the time to 10 Nov or the Sarvam budget (about INR 5,500 for 200 orders against INR 4,600 left). The holdout dev orders t1dev-030..049 (touched once, after the search) play the role of the open check.
- D2. One run per system, not three: pass^3 (C40) is not run.
- D3. The headline system is c1457 (section 1.5), chosen on dev by an architecture search, not Full. Full is run beside it on the same orders and every claim registered for Full in section 1 stays registered and is reported.
- D4. Model family: Sarvam-105B only (OpenAI locked by owner decision 2026-10-28; Gemini's free tier has no B4 and too low a quota).
- D5. Tests failing at the freeze (full suite: 5,334 passed, 7 skipped, then 3 failures fixed in code before the tag; 19 left, none changed):
  17 golden-digest tests of Peshkar and Sutradhar (`tests/unit/agents/{peshkar,sutradhar}/test_variants_*.py`) fail on the event-log digest only (the dossier, List of Dates and prompt digests match). A bisect between `dev-sweep-v2` and `dev-sweep-v3` names commit 5bf4cd3 (29 Oct, design-review item 7): Rights results now carry the rule's verification state, which the events record. The goldens were not re-captured; they fail on `dev-sweep-v3` too, so every dev run and the blind run share this behaviour. Re-capturing them is a test change and waits for the owner.
  2 cells of `tests/unit/eval/test_m6a_beside_m6.py`: `docs/results/shravani/{gemini_31,offline_a10}` lack M6a until Shravani rescores them from her raw outputs (not on this machine).
- D6. Running the blind slice needs its inputs, so `scripts/midsub/blind-run.sh` reads the 80 sealed ids to select the input rows of `data/testsets/t1/cases.jsonl` and strips the gold field from the run file (the driver reads no gold); no gold or output is looked at. The gated opening (`--slice blind --open-blind`, which needs the tag `eval-freeze-v1` and writes `data/eval/blind.lock`) happens once, in one scoring call over all nine arms after every run ends.

Declared after the freeze, before the blind slice was opened (no blind score or gold has been read):
- D7 (2026-11-09, post-freeze:fix of the run, not of a system). Two blind cases failed on the laptop's local SQLite store at start-up, when five driver processes opened it at once: Full on `t1-000` (`file_facts: OperationalError: disk I/O error`) and c1457 on `t1-002` (`file_facts: ... attempt to write a readonly database`). `file_facts` pseudonymises and files the facts text; on failure the driver records the error and runs the rest of the case with no facts text, so the saved output is a degraded run, not the system's answer. The driver saves an errored case and a resume skips it, so the two files were moved aside, unread, to `sarvam_blind/infra_errors_set_aside/` and the queue's second pass reruns the two cases on the same frozen code. Nothing else was rerun.
- D8 (2026-11-09). The 17 golden digests of D5 were re-captured on the `arch-search` branch after the freeze (commit c09b617, test files only, marked RECONCILED): dumping the canonical default runs at 5bf4cd3^, 5bf4cd3 and HEAD shows the only difference is the `last_verified` date on the rights_check results (same event count, order and statuses; packs, plans, budget, dossier, List of Dates and prompt digests unchanged). No source file changed, so the frozen code under test is unaffected.
- D7 clarified (appended, D7 is not edited). D7 departs from section 1.4 ("never retried beyond the driver's recorded retry or replaced") and is a procedural deviation, not a code fix. Criterion, applied identically to every blind arm: a `sqlite3.OperationalError` raised in `file_facts` on the harness's local store, found by the error string only. Exactly one rerun on the same frozen code; the rerun's record is final (an error on the rerun counts as an error). A sensitivity analysis reports c1457 and Full with the original degraded records kept (`sarvam_blind/infra_errors_set_aside/`), i.e. the same arms on 79 paired cases.
- D9 (2026-11-09, 04:14 to 04:24 IST). After the freeze I ranked every Sarvam-scored dev configuration (`scripts/midsub/candidate_pool.py`, a ranking rule written that day) and "c1457 minus X1" (`S13:abstention=strict,draft_source=facts_text,objection_grounding=by_id`) came first on win counts against B0-B6 (38/29/3 against 30/37/3). I started it on the holdout orders t1dev-030..049 (unit `vs-hx457`, frozen worktree at 22fce4f), which breaks D1's "holdout touched once". Three independent read-only checks then found that it is not better than c1457: head to head 1 win, 18 ties, 1 loss; the M6 difference is unresolved (-0.034, 95% interval -0.10 to +0.03); its lower unsupported-fact count comes from writing fewer claims (5.07 against 6.83 per order, supported claims 0.70 in both); it cites no Supreme Court authority (authority SC share 0.000 against 0.051, a resolved loss); the extra wins are cells near the Holm level where c1457 has the same sign. The run was stopped after one case, its outputs moved to `sarvam_holdout/stopped_unscored/` and never scored, and the arm is not added to the blind slice. c1457 stays the only headline; nothing in section 1.5 changes. The candidate-pool tables are post-freeze exploratory dev analyses, not registered tests.

## 9. Order of evaluation

2026-11-09: tags, then the blind slice opened once and run (c1457, Full, B0 to B6; one queue on Sarvam), then scored; the paused ablations of c1457 on dev resume after it; default order: baselines independent of Full, then RQ1 main with the hosted blocks, the sparring 2x2 and the new arms, ablations, smaller variants,
safety, scoring of the open 120, error analysis, the blind slice once, tables and figures (plan 7.3, 5.8).

## 10. Results

Empty by design. Results live in the report tables (plan section 6), never in this file.
