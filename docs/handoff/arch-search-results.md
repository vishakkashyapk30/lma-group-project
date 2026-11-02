# Architecture search on Sarvam-105B (1-2 November 2026): results

Status: IN PROGRESS (this note is updated after every iteration). Branch `arch-search`. Inputs: the failure analysis in `docs/handoff/architecture-search-2026-11-01.md`.

## Rules followed
- Search cases `t1dev-000..029` only (`data/eval/dev_runs/sarvam_search/cases/t1_30.jsonl` = the first 30 rows of `data/testsets/t1/dev.jsonl`). The holdout `030..049` is touched once, at the end, for the winner only. The sealed blind slice was not opened.
- Sarvam-105B only (`VS_ALLOW_PAID=sarvam`, pseudonymised payloads); OpenAI stays locked. Budget for this job: INR 900 (ledger at start 229.44).
- No change to the gold, the scorer or any metric definition. M6 (unsupported-fact rate) is reported as defined. The separate metric M6a (`eval/scoring/split_metric.py`, case-fact sentences only) is extra, never a replacement, and is computed for every arm the same way.
- Every behaviour is an opt-in switch (`orchestration/switches.py`), default byte-identical (golden digests in `tests/unit/agents/vakeel/test_variants_golden.py`, `tests/unit/agents/test_arch_search_variants.py`), with a paper and a row in `docs/literature-to-code-map.md` ("Architecture search").

## What was built
| Id | Switch | What it does |
|---|---|---|
| X1 | `signal_source='merge'` | factor picker: dossier first, facts-text rules (wider custody patterns) for what the dossier lacks; the facts text is offered to the drafter for a factor the dossier says nothing on |
| X2 | `argument_policy='fact_law_split'` | case-fact sentences are near-verbatim spans of the facts text (checked by `span_share`, 0.8), legal-basis sentences carry only `[A:]`; never mixed |
| X3 | `sparring_scope='all_factors'` | one more Abhiyojak call on factors with no ground and no objection (cap 4) |
| X4 | `abstention='strict'` | after repair, failing sentences and "the record is silent" sentences leave the argument and become open issues; an empty ground is not emitted |
| X5 | `draft_source='facts_text'` | Vakeel drafts from the raw facts text; the dossier still drives the planner and Gate 1 |
| X6 | `critic_material='union_free'` | Abhiyojak's own stores searched twice: ground-keyed and filtered, plus facts-keyed and unfiltered (isolation kept) |
| X7 | `objection_grounding='by_id'` | an objection reference naming offered material under the wrong store label or field spelling is resolved by id instead of discarded (Full on Sarvam kept 66 objections and discarded 230; 263 of 320 dropped references named a paragraph that had been offered) |
| H1, H1m1..H1m6 | combinations | all of X1-X6, and leave-one-out arms (defined, not all run) |
| `S13:<field>=<value>,...` | grid point | any combination without a new id (used for the iteration arms) |

Driver: `scripts/midsub/arch-search-sarvam-queue.sh <arm> ...` as a systemd user unit (4 processes in all, 2 shards per arm). Scoring: `python -m vakeel_sahayak.eval.scoring score --runs <copy of one arm> --slice dev --gold-source agreed --out ...` with `VS_M6_CHECKER=minicheck` (one arm per call; about 30 to 90 minutes of CPU each). Tables: `scripts/midsub/arch_search_compare.py` (means and paired differences to Full) and `scripts/midsub/arch_search_table.py` (win/loss/tie against every baseline). Per-case CSVs: `docs/results/search/`.

Baselines: B4 was rerun on the new code (same 30 cases). B0, B1, B2, B3, B5, B6 are the Sarvam block rows of `docs/results/midsub/sarvam/per_case_agreed.csv` (same 30 cases, same scorer and gold, older code stamp; their runners do not read any switch added here), labelled `b*_old`.

## Iteration 1 (commit e1fc7ee): single switches

Means on the 30 search cases (objection recall on 11 gold orders, factor metrics on 4, answerable coverage on 11):

| arm | obj. recall | obj. precision | answerable cov. | coverage | factor recall | factor prec. | factor F1 | citation prec. | fabricated | M6 | tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| full | 0.364 | 0.225 | 0.379 | 0.643 | 0.500 | 0.188 | 0.417 | 0.823 | 0.000 | 0.989 | 95,413 |
| b0 | 0.000 | - | 0.000 | 0.200 | 0.000 | - | 0.000 | - | - | 0.949 | 3,315 |
| b1 | 0.000 | - | 0.182 | 0.267 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.912 | 5,599 |
| b2 | 0.000 | - | 0.000 | 0.133 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.965 | 3,812 |
| b3 | 0.000 | - | 0.000 | 0.267 | 0.250 | 0.500 | 0.250 | 0.500 | 0.000 | 0.901 | 5,412 |
| b4 | 0.273 | 0.048 | 0.242 | 0.075 | 0.500 | 0.188 | 0.417 | 0.011 | 0.933 | 0.947 | 118,183 |
| b5 | 0.364 | 0.361 | 0.167 | 0.074 | 0.500 | 0.188 | 0.417 | 0.000 | 0.643 | 0.956 | 76,978 |
| b6 | 0.000 | - | 0.000 | 1.000 | 0.750 | 0.467 | 0.625 | - | - | 0.959 | 0 |
| a7 | 0.364 | 0.361 | 0.167 | 0.068 | 0.500 | 0.188 | 0.417 | 0.143 | 0.643 | 0.952 | 71,502 |
| X1 | 0.091 | 0.029 | 0.424 | 0.724 | 0.500 | 0.188 | 0.417 | 0.583 | 0.008 | 0.900 | 106,305 |
| X3 | 0.364 | 0.183 | 0.379 | 0.643 | 0.500 | 0.188 | 0.417 | 0.823 | 0.000 | 0.989 | 114,481 |
| X4 | 0.455 | 0.476 | 0.530 | 1.000 | 0.500 | 0.286 | 0.500 | 0.880 | 0.000 | 0.981 | 85,838 |
| X5 | 0.273 | 0.104 | 0.333 | 0.677 | 0.500 | 0.188 | 0.417 | 0.632 | 0.000 | 0.889 | 96,858 |
| X6 | 0.545 | 0.315 | 0.379 | 0.643 | 0.500 | 0.188 | 0.417 | 0.823 | 0.000 | 0.989 | 94,458 |

Full paired comparison (with intervals): `docs/results/search/compare_iter1.md`; win/loss/tie per baseline: `docs/results/search/wlt_iter1.md` (Full 23 W / 12 L / 32 T over 11 metrics x 7 baselines; X4 26/9/32; X5 23/7/37).

Readings:
- X4 is the strongest single switch: coverage 1.000 (ties B6, beats the rest), objection precision 0.476, answerable coverage 0.530, citation precision 0.880, fewer tokens. It does not move M6 (0.981): the remaining sentences are authority sentences, which the facts cannot entail.
- X5 is the only switch that moves M6 with an interval that excludes zero (paired -0.100 [-0.150, -0.053] vs Full; wins vs B0, B4, B5, B6), but it lowers citation precision (0.632) and objection precision.
- X6 raises objection recall (+0.182 [0.000, 0.455]) at no token cost; X3 adds objections but no recall (its extra objections land on non-gold factors, and many are discarded as ungrounded, see X7).
- X1 lowers M6 (0.900) but its objections collapsed on this run (0.091); Sarvam objections are noisy run to run (0 to 8 per case), which X7 addresses.
- Iteration 2 (commit 568d445) added X7.

## Cells that cannot be won (stated before any further iteration)
- Tokens against B0-B3 and B6: these are one-call or no-call baselines (0 to 6k tokens against 85k+). No agentic arm can win this cell; reported, not chased.
- Coverage against B6: the scorer counts every B6 ground as emitted (a template cannot decline), so B6 is 1.000, the ceiling. The best possible result is a tie (X4 reaches it).
- Factor recall, precision and F1: defined on 4 search orders (precision on 1-8). With n = 4 a bootstrap interval excludes zero only if every order moves the same way; against B6 (a 7-factor template whose recall is by construction, see `eval/baselines/b6_expert_rule.py`) the only way to win recall is to argue more factors, which is gaming (plan C3). Reported as ties or losses.
- Objection precision against B0-B3 and B6: undefined (they raise no objections).

## Spend
Ledger: 229.44 at start; 291.60 after iteration 1 (about INR 62 for 9 arms x 30 cases, most Full-identical calls hit the response cache).

## Next (being run)
X2 (single), X7 (single), S13 X1+X4+X5+X7, S13 X1+X4+X5+X6+X7, S13 X4+X6+X7. Then the winner is renamed to a fixed id, Full/B4/A7 and the winner are rerun on that commit, the holdout is run once, and the ablations are run on the winner.
