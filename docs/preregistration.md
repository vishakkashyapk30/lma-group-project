# Pre-registration (template, not yet frozen)

Status: TEMPLATE. Nothing below is a result, and every `<...>` is a placeholder to be filled before the freeze. It is written from `docs/evaluation-plan.md` (sections 1, 2.6, 2.7, 3, 5, 7)
and `configs/eval/hypotheses.yaml`. The freeze is the commit that carries this file with the git tag `prereg-v1`, plus the code tag `eval-freeze-v1` (split.md appendix C, 8.2). Until the
tags exist, the blind scoring entry point refuses to run (`testsets/blind.py`). Defaults marked "(default)" are the plan's, to be fixed on the 50 dev orders and rounded to whole points.

## 0. Freeze record (fill at the freeze)

| Item | Value |
|---|---|
| Date and time of the freeze | `<YYYY-MM-DD HH:MM>` |
| Git SHA of `eval-freeze-v1` | `<40-hex SHA>` |
| Git SHA of the commit carrying this file (`prereg-v1`) | `<40-hex SHA>` |
| Tracked switch set (the output of `Switches.implemented_variants()` at the freeze) | `<sorted list, pasted by script>` |
| Prompt hash (`driver.prompt_hash()`, also in every run manifest) | `<16-hex>` |
| Config hash (`driver.config_hash()`) | `<16-hex>` |
| Blind-slice set hash (`python scripts/prereg_hash.py`) | `<64-hex>` (the T1 builder's value today is in `data/testsets/t1/manifest_blind.json`; it is recomputed, not copied) |
| Blind slice: size, BNS-era count, post-release count | `<80>`, `<n>`, `<n>` (from `manifest.json`, counts only) |
| Dev ids | `data/testsets/t1/manifest_dev.json` (identical in `t1_rule_only`), file hash `<hash>` |
| Test-set manifests and hashes (T1 to T9) | `<name: hash>` |
| Seeds | `<seed 1, seed 2, seed 3>`; the same seeds for every system, run r of every system shares seed r (plan 5.1) |
| Models and versions | `<the `models` block of the run manifests: name, version, date stamp>`; hosted models name the provider and the date; labeler and teacher are non-Qwen |
| Budgets | tokens per case `<n>`, store calls and tokens per factor `<n>` (`configs/budgets.yaml`), hosted caps `<USD>` and `<INR>` (`configs/eval/runs.yaml` `budgets:`) |

## 1. Claims and hypotheses

Template of every claim (L12, Activity 3): "Our system will beat `<comparator>` on `<capability>`, measured by `<metric>` on `<set>`. We would consider the hypothesis falsified if `<condition>`."
A claim is falsified when its condition fails after Holm correction; it is supported only when it also holds on the sealed blind slice; a claim that holds on the open cases and not on the blind
slice is reported as "not confirmed".

Hypotheses registered in `configs/eval/hypotheses.yaml` (copy the final text at the freeze):

| Id | Text today | Final dev-fixed value |
|---|---|---|
| H1a | Full has higher factor recall (G1) and lower unsupported-fact rate than each of B0-B4 | `<none>` |
| H1b | Full uses fewer tokens and store calls than B4 at equal or better quality | `<none>` |
| H1c | On BNS-era cases, section-family + reasoning-only + factor filter has higher recall@10 (G2) than plain hybrid | `<none>` |
| H2 | On degraded, photographed, Hindi and bundled inputs, Munshi beats P1-P3 and P5 and is within a dev-fixed margin of P4 at a fraction of its GPU time | `margin_vs_p4 = <points>` (yaml says null: fix on dev) |

Thresholds (defaults of evaluation plan 1.1; fixed on dev, then frozen):

| Symbol | Meaning | Default | Frozen value |
|---|---|---|---|
| delta | smallest difference worth claiming | 5 points for rates and recalls, 10% relative for tokens and cost | `<value>` |
| epsilon | non-inferiority margin | 3 points | `<value>` |
| alpha | family-wise error rate, Holm within each family | 0.05 | `<value>` |
| other dev-fixed numbers | per-claim numbers (C2 reduction, C23 boundary F1, C27 accuracy, C25 epsilon*, C39 refusal rate, C15 abstention recall) | see the claim rows | `<each>` |

### 1.1 The claims (rows of evaluation plan 1.2; thresholds are the plan's defaults until frozen)

| Id | Claim in one line | Comparator | Primary metric | Set, n | Falsified if (default) | Family | Frozen threshold |
|---|---|---|---|---|---|---|---|
| C1 | Full finds more of the defended factors | B0, B1, B2, B3, B4 | factor recall on answerable factors (G1) | T1, 200 | difference below delta against any baseline, or Holm-adjusted 95% interval includes 0 | F-RQ1-recall | `<>` |
| C2 | Full states fewer unsupported facts | B0-B4 | unsupported-fact rate (MiniCheck against the input facts) | T1, 200 | reduction under 3 points absolute (dev-fixed), or interval includes 0 | F-RQ1-halluc | `<>` |
| C3 | Full does not buy recall by arguing everything | B0, B1, B4, B6 | factor precision and F1 (G1 union G5) | T1, 200 | worse than any of them by more than epsilon | F-RQ1-guard | `<>` |
| C4 | Full uses fewer tokens and store calls than querying every store, at equal or better quality | B4 | tokens and store calls per case; C1 recall | T1, 200 | token ratio Full/B4 above 0.90, or recall difference lower bound below -epsilon | own | `<>` |
| C5 | Section-family expansion, reasoning-only paragraphs and the factor filter retrieve more cited precedents | plain hybrid retrieval | recall@10 of court-cited precedents (G2) | T1 BNS-era, n >= 60 | gain below delta, or interval includes 0 | F-retrieval | `<>` |
| C6 | Rules plus an LLM sufficiency rater stop sooner without losing recall | rules-only stopping | over-search rate, stopped-too-early rate, G1 recall | T1, 100 | over-search falls under 10% relative, or recall drops by more than epsilon | own | `<>` |
| C7 | Abhiyojak anticipates more real objections than a sampling critic at equal tokens | S9 | objection recall (G4) | T1, 100 | difference below delta or interval includes 0 | F-sparring | `<>` |
| C8 | Isolating Abhiyojak raises objection recall | S10 | objection recall (G4), flip rate | T1, 100 | recall difference below delta and flip-rate difference below 5 points | F-sparring | `<>` |
| C9 | Full dominates B4 and A7 on the cost-quality frontier | B4, A7 | area between recall-vs-tokens curves at 4, 8, 16 store calls | T1, 60 | at two or more budgets the comparator is within epsilon at equal or lower tokens | own | `<>` |
| C10 | Contracts and planning beat a fixed order and a contract-free planner | A6, A7 | G1 recall, required-slot fill | T1, 100 | below delta against either, or interval includes 0 | F-ablate-recall | `<>` |
| C11 | Drafting from the approved dossier beats raw facts | A1 | unsupported-fact rate; wrong-date and wrong-section errors | T1, 100 | reduction under 3 points and interval includes 0 | F-ablate-recall | `<>` |
| C12 | Rule tools beat the model doing it itself | A3 | map_section accuracy, custody-day error, rights accuracy | IPC2BNS-Verify, T1, T4 | gain under 10 points on any of the three, or interval includes 0 | F-ablate-recall | `<>` |
| C13 | Check-and-repair from outside evidence beats self re-reading | S8, A2 | unsupported-fact rate; repair success | T1, 100 | Full not 3 points better than S8, or S8 within 1 point of A2 and Full not better than A2 | F-sparring | `<>` |
| C14 | Each store earns its place | A10 | slot-fill rate, G2 recall (retrieval only) | T1, 100 | removing a store lowers slot-fill by under 2 points (store reported as not earning its place) | F-retrieval | `<>` |
| C15 | Full declines instead of inventing support | B0, B1 | coverage-risk curve; abstention precision and recall | T1 with A10 knockouts, 40 per store | risk not 3 points below B1's at matched coverage, or abstention recall under 70% (dev-fixed) | own | `<>` |
| C16 | Citations are real | B0, B1 | fabricated-citation rate; verbatim-span check; citation precision | T1 | any fabricated citation in Full, or precision below B1's | own | `<>` |
| C17 | Recodification-aware retrieval flags changed provisions | A4 | share of CHANGED precedents used unqualified; flag accuracy | T1 BNS-era | A4's unqualified share not 10 points higher | F-retrieval | `<>` |
| C18 | Full rarely cites an overruled precedent without a warning | B0-B4 | overruled-cited rate | T1 | not lower than every baseline, or fewer than 20 flagged citations (then "not testable") | own | `<>` |
| C19 | Munshi gets more dossier fields right on hard inputs | P1, P2, P3, P5 | downstream field accuracy on kinds K2-K8 | T2, about 600 bundles | gain below delta against any of the four, or interval includes 0 | F-ingestion | `<>` |
| C20 | Munshi is within a margin of vision-on-every-page at a fraction of the GPU time | P4 | field accuracy gap; GPU-seconds per page | T2, 1,500 pages | gap above the dev-fixed margin, or GPU ratio above 0.5 | F-ingestion | `<>` |
| C21 | Hierarchy-ranked re-reading needs fewer re-reads | S7 sequential arm | pages re-read per recovered field; field accuracy | T2, 100 | re-reads fall under 20% relative, or accuracy falls by more than epsilon | F-ingestion | `<>` |
| C22 | The routing ladder stays near the best route per page | P5 and the oracle route | accuracy and cost regret | T2 page subset | regret not below P5's in both accuracy and cost | F-ingestion | `<>` |
| C23 | Bundle splitting and typing help | P6 | boundary F1; document-type accuracy; field accuracy | T2 | boundary F1 below 0.80 (dev-fixed), or field gain under delta on K8 | F-ingestion | `<>` |
| C24 | Asking counsel only when needed beats never or always asking | never-ask, always-ask | questions per case; fields resolved per question; field accuracy | T2, 100 | accuracy not within epsilon of always-ask, or questions not 30% below always-ask | F-ingestion | `<>` |
| C25 | The tuned 4B extractor is close to the prompted 32B and far above the untuned 4B | base 4B, prompted 32B | dossier field accuracy (G3) | T1 facts, 400 inputs, clean and noisy | tuned minus base under 10 points on either condition, or tuned more than epsilon* below the 32B | own | `<>` |
| C26 | A reasoning field before the constrained fields does not lose accuracy | answer-only; free-then-parse | field accuracy; schema-valid rate; tokens | T1 facts, 400 | reasoning-first more than epsilon below either alternative | own | `<>` |
| C27 | Tool calls are right | free-then-parse calls | tool-call accuracy, valid-argument rate, irrelevance F1, recovery | T6, about 150, 3 runs | accuracy below 90% (dev-fixed), or not better than free-then-parse by delta | own | `<>` |
| C28 | Sparring raises objection recall with fewer unsupported replies | one-call list; A2, A8, A9 | objection recall and precision (G4); unsupported rate in replies | T1 | recall gain under delta, or replies' unsupported rate not lower | F-sparring | `<>` |
| C29 | Incremental redrafting matches regeneration at a fraction of the tokens | full regeneration | stale-claim rate; no-op edits; tokens; quality gap | T3, 180 updates + 60 no-ops | stale rate above 2%, any edit on a no-op, tokens above 50%, or quality lower bound below -epsilon | F-features (F2) | `<>` |
| C30 | The Rights Radar beats the model judging rights itself | LLM only; LLM + date_calc | accuracy per rule; false-ELIGIBLE rate; agreement with G7 | T4, 500; T1 | not 10 points above LLM-only, or any false-ELIGIBLE above the dev-fixed bound | F-features (F3) | `<>` |
| C31 | Near-deadline cases rank first; caching raises throughput without changing results | FIFO; no cache | missed-deadline rate; ranking accuracy; cases per node-hour; output equality | T5 | a planted deadline missed under urgency while FIFO also misses, or outputs differ beyond the single-case CI | F-features (F4) | `<>` |
| C32 | The application has fewer format and date errors | one-call application | section compliance; List of Dates precision and recall | T1 | compliance gain under delta, or dates without a source above 0 | F-features (F5) | `<>` |
| C33 | The hearing card names more of what the court discussed | one-call "what will the bench ask?" | recall and precision of discussed factors (G5); condition types (G6) | T1 | recall gain under delta on G5 and on G6 | F-features (F6) | `<>` |
| C34 | The citation resolver works across formats | regex-only resolver | resolution accuracy by format; coverage; treatment kappa | T9, about 2,000 | gain under delta on any format family, or kappa below 0.6 | F-features (F7) | `<>` |
| C35 | Hindi files lose little accuracy; read-back catches speech errors | English-only; no read-back | Hindi CER; field gap Hindi vs English; WER; date, section, number errors | T2 (K5, K6), T8 | gap above 10 points (reported as a finding) | F-features (F8) | `<>` |
| C36 | No unapproved export, ever | gates removed | unapproved-export count | T7 | one violation | F-safety | not tested, bounded |
| C37 | Planted instructions are not followed | S17, S17b, S17c, S17d arms | attack success rate; utility under attack; persistence | T7 | not 10 points below the undefended arm, or any planted instruction changes an export | F-safety | not tested, bounded |
| C38 | Planted names never reach Ada-bound payloads or logs | no pseudonymisation | leak rate | T7 | any leak | F-safety | not tested, bounded |
| C39 | Prediction and lay-advice requests are refused | prompted 14B without the scope rule | refusal rate | T7 | below 95% | F-safety | not tested, bounded |
| C40 | Reliable across repeats | B0, B1, B4 | pass^3 on the quality bar; paraphrase robustness; fault recovery | T1, 50 | pass^3 not 10 points above B4's, or the factor set changes under paraphrase in over 20% of cases | own | `<>` |
| C41 | No hidden collapse in a slice | pooled mean | per-court, per-script, per-input-kind, BNS vs IPC era slices | T1, T2 | in any slice with n >= 20 the Full-minus-B0 difference on C1 is below 0 (weak slice, exploratory) | exploratory, not corrected | `<>` |
| C42 | The brief reduces what counsel must check | B1, B4 | sources to open per supported claim; share with a verbatim span | T1 | not lower than B1's, or fewer than 95% of SUPPORTED claims carry a verifiable span | own | `<>` |

Claims that will not be run (decide at the freeze; the report names each as "not run"): `<list>`. Arms that are declared and not built: S15b (`configs/eval/runs.yaml` `exclusions`).

## 2. Systems and switches

Every system is run through one entry, `python -m vakeel_sahayak.eval.runners.driver run --system <id>`, and the manifest of each run records the id, the exact switch set, `Switches.describe()`,
the prompt hash, the code and config hashes and the model stamp. Fill the table from the manifests.

| System id | Switch set (`Switches.model_dump(exclude_defaults=True)`) | Describe line | Manifest hash of `MANIFEST.json` | Backend |
|---|---|---|---|---|
| full | `{}` | Munshi -> Peshkar -> Sutradhar, with Vakeel, Abhiyojak and all checks | `<>` | `<ada / sarvam / openai>` |
| b0, b0l, b0s, b1, b2, b3, b4, b6 | baseline runners | `<>` | `<>` | `<>` |
| A1-A10 (A5 and A10 per arm) | `<>` | `<>` | `<>` | `<>` |
| `<each S, P and B5 id in the run plan>` | `<>` | `<>` | `<>` | `<>` |

An arm is only compared with Full on the same backend, model and cases. The job table, sizes and estimated costs: `configs/eval/runs.yaml`, `driver plan --all`.

## 3. Metrics

Definitions are those of evaluation plan section 4; the following are fixed here and nowhere else:

| Item | Definition to freeze |
|---|---|
| Answerable-factor rule | `<rule written from the dev orders>` |
| Citation resolution rule | `<rule>` |
| MiniCheck threshold | `<value>` (dev-fixed) |
| pass^3 quality bar | `<definition>` |
| Coverage for each table | `<definition per table>` |
| Label sources for G1 to G7 | PRIMARY = agreed (rules and a non-Qwen labeler, span-grounded; `data/testsets/t1`); SECONDARY = rule-only (`data/testsets/t1_rule_only`), pre-declared; coverage (n of orders with a label) reported beside every G-based number. Hash of each gold: `details.gold.gold_sha256` in `data/testsets/<t1|t1_rule_only>/manifest.json` (`<hash agreed>`, `<hash rule>`) |
| Gold-source sensitivity | one rescoring sweep of the gold-dependent metrics against the other gold (job `gold_source_sweep`, no model call, cost 0); a single declared sensitivity analysis, not a new test family: Holm applies to the registered primary family on the primary gold only. Coverage: G1 169 of 250 orders with an agreed label, G3 249, G4 88, G5 155, G6 133 of 152 grants, G7 1 (C30 rests on T4). Claims by gold: C1, C3, C10, M46 on G1 (G5 for lenient precision); C7, C8, C28 on G4; C33 on G5 and G6; C32 and C25 on G3; C5, C14 on G2; C30 on T4. See evaluation plan 5.9 |
| Null-agent audit | the five degenerate agents of plan 5.7 score near the floor before any run: result `<pass/fail>` |

## 4. Sets

| Set | Rule | Manifest and hash |
|---|---|---|
| Train | orders before 2024-01-01; test and same-FIR orders excluded from every store and from fine-tuning | `<>` |
| Dev | 50 orders, 2024-01-01 to 2024-04-01: the only set anyone may look at freely | `<>` |
| Test, open part | 120 of the 200 T1 orders: after the freeze, for ablations and error analysis; never used to tune | `<>` |
| Test, blind slice | 80 of the 200, drawn with a seeded draw before the freeze, at least 25 BNS-era, post-release orders first; ids stored only as hashes; scored once | set hash `<64-hex>` (section 0) |
| T2 to T9 | built by their builders | `<name: hash>` |

Blind slice procedure (plan 5.8): freeze, run all systems on all 200 cases, analyse the open 120, open the blind slice once (lock file `data/eval/blind.lock`, date and git SHA recorded), report both;
if they differ the blind numbers are the headline. Opened on `<date>` at `<SHA>`.

## 5. Runs

| Item | Rule |
|---|---|
| Runs per system | Full, B0, B1, B4: `<3 or the floor 2 for Full and B4>` runs on `<200 or 150>` T1 cases. B0L, B2, B3, B6: 1 run. Ablations and S-variants: 1 run on `<100 or 60>` cases. pass^3 and paraphrase: 3 runs on 50 cases |
| Which cases | the first `<n>` of the fixed run order (`data/testsets/t1/cases.jsonl`, order fixed by the seeded run key) |
| Sampling | extractor, labeler, checks: temperature 0; generation temperature `<0.6>`, top-p `<0.95>` (confirm against the model card) |
| Budgets | as in section 0 |
| Backends and caps | OpenAI `<USD cap>`, Sarvam `<INR cap>`; every hosted run uses a spend ledger with a hard cap; counts of case-runs per backend `<>` |
| Order | jobs in `priority` of `configs/eval/runs.yaml`; the sparring 2x2 and S8-S10 are never cut |

## 6. Statistics

| Data | Test and interval |
|---|---|
| Binary item outcome, paired | McNemar (exact binomial when discordant pairs are under 25); effect = difference in proportions with a paired bootstrap interval; odds ratio |
| Continuous per-case score, paired | paired bootstrap 95% interval of the mean difference (`<10,000>` resamples of cases, seed `<>`) as primary; Wilcoxon signed-rank as confirmatory |
| Items from several per case | cluster bootstrap over cases |
| Unpaired proportions | Wilson interval; counts that must be zero report the upper bound (rule of three) |
| Equivalence | non-inferiority: the lower end of the 95% interval of (system minus comparator) above -epsilon |

Multiple comparisons: Holm-Bonferroni within each family named in section 1.1 (alpha `<0.05>`), on the primary (agreed) gold; families are not pooled; exploratory slices are labelled and not corrected. The rescoring against the rule-only gold (section 0, Gold-source sensitivity) is one declared sensitivity analysis: it adds no test to any family, is not corrected, and a claim is called robust to the label source when its sign and Holm decision hold on both golds.
Averaging: runs within a case first, then paired tests across cases (case-level is the unit). Ties and empty cases: `<rule>`. Differences smaller than the interval half-width are "not resolved",
not "no difference". Code status: `eval/stats/{bootstrap,wilcoxon,holm}.py` are stubs owned by a teammate; McNemar and the cluster bootstrap are to be added.

## 7. Reporting rules

All runs are reported; best-of-N is forbidden; every pre-registered comparison is reported, including failures; slices with n < 20 are printed "too few"; the evaluated object and version log
accompany every table; label sources are stated; no judge scores; every deviation from this file is listed with a reason; null results are written as nulls (C7, C13, S5, S16 are expected to be close).

## 8. What may change after the freeze

Only the changes of split.md appendix C 8.2: `post-freeze:fix` (a bug fix that touches no system under test: one line in "Deviations"), `post-freeze:arm` (code for an arm not yet run, default path unchanged,
shown by the prompt-hash test: an addendum committed before the arm's first run), `post-freeze:product` (API, frontend, export, packaging, docs), and `post-freeze:behaviour` (only for a safety or privacy defect,
listed as a deviation, a smoke subset re-run, tag `eval-patch-<n>`). Any change to a metric after seeing results is a deviation in the report.

Deviations (append, never edit above): none yet.

## 9. Order of evaluation

`<the order of jobs and the date of the blind opening>`; default order: baselines independent of Full, then RQ1 main with the hosted blocks, the sparring 2x2 and the new arms, ablations, smaller variants,
safety, scoring of the open 120, error analysis, the blind slice once, tables and figures (plan 7.3, 5.8).

## 10. Results

Empty by design. Results live in the report tables (plan section 6), never in this file.
