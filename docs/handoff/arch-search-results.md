# Architecture search on Sarvam-105B (1-2 November 2026): results

Status: WINNER CHOSEN (3 Nov); holdout and ablations running (this note is updated after every iteration). Branch `arch-search`. Inputs: the failure analysis in `docs/handoff/architecture-search-2026-11-01.md`.

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

## Iteration 2 (commit 568d445): X7, X2, and combinations

| arm | obj. recall | obj. precision | answerable cov. | coverage | factor recall | factor prec. | factor F1 | citation prec. | fabricated | M6 | tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| X2 | 0.000 | 0.000 | 0.045 | 0.199 | 0.000 | 0.000 | 0.000 | 0.795 | 0.000 | 0.730 | 94,457 |
| X7 | 1.000 | 0.203 | 0.379 | 0.643 | 0.500 | 0.188 | 0.417 | 0.823 | 0.000 | 0.989 | 111,991 |
| c457 = X4+X6+X7 | 0.909 | 0.182 | 0.530 | 1.000 | 0.500 | 0.286 | 0.500 | 0.880 | 0.000 | 0.981 | 105,397 |
| c1457 = X1+X4+X5+X7 | 1.000 | 0.192 | 0.606 | 0.972 | 0.500 | 0.214 | 0.417 | 0.681 | 0.000 | 0.895 | 121,065 |
| c14567 = X1+X4+X5+X6+X7 | 1.000 | 0.195 | 0.515 | 0.956 | 0.250 | 0.083 | 0.167 | 0.698 | 0.000 | 0.903 | 119,269 |

- X7 (resolve an objection's reference by id) lifts objection recall from 0.364 to 1.000 on the 11 gold orders: the objections were there, they were being discarded for a store-label slip. Objection precision stays about 0.2 (Full raises 3 to 5 objection factors per order against 1 gold factor).
- X2 failed on Sarvam: most grounds could not meet the 80% verbatim rule and ended empty or NEEDS_REVIEW (coverage 0.199); dropped.
- c1457 is the best combination so far. Satvik's table (`docs/report/tools/win_loss_tie.py`, seeded paired bootstrap, Holm per arm and metric over B0-B6; merged on main 29297d0 and used from iteration 2 on): c1457 27 wins, 28 ties, 4 losses, 49 too-few cells; Full 14 wins, 33 ties, 12 losses. The 4 losses of c1457: `unfinished_factor_share` against B4 and B5, `confident_wrong_rate` against B0 and B4. M6 is no longer a loss against any baseline (ties after Holm; point estimates 0.895 against 0.90-0.97). Tables: `docs/results/search/wlt_iter2.md`, every comparison in `docs/results/search/wlt/search.csv`.

### Why the four remaining losses are structural (declared, not chased)
- `unfinished_factor_share` (M18, factors stopped with a required slot unfilled) against B4 and B5: B4 has one `fused` slot that is filled whenever any store returns anything, and B5 has no contract slots, so both are near 0 by construction. Full's contracts name required evidence; an unfilled slot is the system telling counsel what is missing. Removing the loss means removing the contracts or relabelling slots as optional, which changes what the metric counts rather than the quality.
- `confident_wrong_rate` (M35, emitted sentences supported neither by the facts nor by the rest of the order) against B4 (n = 14) and B0 (n = 6): B4 emits 7.5% of its grounds (coverage 0.075) and B0 writes claims in 6 of 30 orders, so their few emitted sentences are a selected subset. c1457 emits 97% of its grounds and most of its sentences state law from a cited precedent, which the facts cannot entail. Lowering M35 needs either declining most grounds (losing coverage, where c1457 now wins against B0-B5 and ties B6) or dropping the legal reasoning; both are gaming the trade-off, not improving the brief.

## Iteration 3 (commit 1ef5495): X8 and the final reruns
- X8 (`fact_grounding='verbatim'`): after repair, a case-fact sentence that paraphrases the record is replaced by the record sentence itself (no model call, nothing added, law sentences untouched).
- The scorer now emits M6a (`unsupported_case_fact_rate`) and its count `n_case_fact` beside M6 (`eval/scoring/engine.METRICS`, `case_metrics.py`); every committed per-case CSV under `docs/results` was given the two columns from its stored outputs by `scripts/midsub/add_m6a.py` (no other column touched), so `tests/unit/eval/test_m6a_beside_m6.py` runs.
- Running now (unit `vs-final`, root `data/eval/dev_runs/sarvam_final`, all on commit 1ef5495): c14578 (= c1457 + X8), c1457, Full, B4, A7, B0, B1, B2, B3, B5, B6 on the 30 search cases, so the final table has one code stamp.

## Final table (3 Nov): every arm rerun on one code tree (b44ddeae; git 1ef5495 for c1457, faddcbb for Full and B0-B6, no src or config difference), 30 search cases
Per-case CSVs and the win/loss/tie table: `docs/results/search/final/` (Satvik's `win_loss_tie.py`, seeded paired bootstrap, Holm over B0-B6 per arm and metric, a win only when the interval excludes zero; 25 quality metrics, M6a beside M6).

| arm | obj. recall | obj. prec. | answerable cov. | coverage | citation prec. | fabricated | M6 | M6a | confident wrong | tokens |
|---|---|---|---|---|---|---|---|---|---|---|
| full | 0.364 | 0.225 | 0.379 | 0.643 | 0.823 | 0.000 | 0.989 | 0.844 | 0.980 | 95,413 |
| **c1457** | **1.000** | 0.192 | **0.606** | 0.972 | 0.681 | 0.000 | **0.895** | **0.472** | 0.893 | 121,065 |
| c14578 (+X8) | 1.000 | 0.198 | 0.606 | 0.972 | 0.681 | 0.000 | 0.895 | 0.444 | 0.893 | 120,492 |
| a7 | 0.364 | 0.361 | 0.167 | 0.068 | 0.143 | 0.643 | 0.952 | 0.583 | 0.429 | 71,502 |
| b0 | 0.000 | - | 0.000 | 0.400 | - | - | 0.989 | - | 0.969 | 3,331 |
| b1 | 0.000 | - | 0.182 | 0.367 | 0.167 | 0.000 | 0.966 | - | 0.903 | 5,506 |
| b2 | 0.000 | - | 0.091 | 0.500 | 0.000 | 1.000 | 0.953 | - | 0.916 | 3,671 |
| b3 | 0.000 | - | 0.000 | 0.367 | 0.056 | 0.000 | 0.983 | - | 0.940 | 5,393 |
| b4 | 0.273 | 0.048 | 0.242 | 0.075 | 0.011 | 0.933 | 0.947 | 0.845 | 0.301 | 118,183 |
| b5 | 0.364 | 0.361 | 0.167 | 0.074 | 0.214 | 0.643 | 0.953 | 0.625 | 0.524 | 76,842 |
| b6 | 0.000 | - | 0.000 | 1.000 | - | - | 0.981 | - | 0.947 | 0 |

Win / tie / loss against B0-B6 (cells with fewer than 5 paired cases or a metric undefined on both sides are not counted):

| arm | wins | ties | losses | losses are |
|---|---|---|---|---|
| full | 11 | 49 | 10 | M6 vs B4, B5; M6 count vs B5; coverage vs B6; over-search vs B5; unfinished-factor share vs B4, B5; confident-wrong vs B0, B4, B5 |
| **c1457** | **30** | 37 | **3** | unfinished-factor share vs B4, B5; confident-wrong vs B4 |
| c14578 | 33 | 33 | 4 | the three above and confident-wrong vs B5 |
| a7 | 7 | 47 | 5 | coverage vs B0-B3, B6 |

**Winner: c1457**, driver id `S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id` (X1 + X4 + X5 + X7). It has the fewest losses; X8 adds one loss (confident-wrong vs B5) for 3 more wins, so it is not taken. No arm beats every baseline on every metric: the three losses left are the structural cells declared above (B4 and B5 have no required-evidence slots; B4 emits 7.5% of its grounds, so its few sentences are a selected subset). Removing them would mean removing the evidence contracts or declining most grounds, i.e. changing what the metric counts, not improving the brief. Citation precision falls from 0.82 to 0.68 against Full (still a win over B4 and B5, which fabricate) and tokens rise 27%.

## Running (unit `vs-winner`, commit of `scripts/midsub/winner-holdout-ablations.sh`)
1. Holdout `t1dev-030..049`, touched once: c1457, Full, B0-B6 (`data/eval/dev_runs/sarvam_holdout`).
2. Ablations on the 30 search cases (`data/eval/dev_runs/sarvam_ablate`): c1457 rerun on this commit; leave-one-out (no X1, no X4, no X5, no X7); A1-A4 and A6-A9 applied on top of c1457 (`no_dossier`, `no_check_repair`, `no_tools`, `plain_retrieval`, `fixed_router`, `free_planner`, `no_sparring`, both).
Log: `data/eval/dev_runs/winner.log` (prints HOLDOUT_DONE, ABLATE_DONE). Score each arm with the scratchpad pattern of `score.sh` (one arm per call, `VS_M6_CHECKER=minicheck`).

## Evidence for the unfinished-factor loss (7 Nov)
On the 30 search cases the winner plans 130 factors and 47 end with a required slot MISSING: witness_tampering 18 (trial_stage, witness_examination), antecedents 18 (antecedents), flight_risk 8 (community_roots), 3 others. A regular-expression search of the **facts text only** (not the gold) finds none of these four slots stated in the record for any of the 62 missing slots (antecedents 0/18, trial stage 0/18, witness examination 0/18, community roots 0/8). MISSING is therefore the true state: the record is silent. Filling the slots would be fabrication; not planning those factors would drop the prosecution concerns counsel has to prepare for. B4 and B5 score near zero only because they have no required slots. The loss is reported as it is.

## Owner decisions (7 Nov)
- Quality metrics decide "beats every baseline". Cost (tokens, store calls, seconds, INR) is a separate efficiency table, judged only against B4 and B5 (the baselines with comparable capability); against the one-call baselines (B0-B3) and the template (B6) it is shown, not counted. Undefined cells (a baseline that produces no objections or no sentence markers, so objection precision or M6a cannot be computed) are listed as undefined.
- Factor recall, precision and F1 are reported on all 50 dev orders (search + holdout, after the holdout check), since the 30 search orders give only 4 scorable orders.
- The M6a test stays as written; Shravani rescores `docs/results/shravani/{gemini_31,offline_a10}` from her raw outputs before arch-search goes to main.
- No test is changed to make it pass. The four existing tests edited on this branch only add the new switch names and arm ids to the registry lists (marked `# RECONCILED`); no assertion was removed or loosened.

## After the reboot of 4 Nov
The holdout block finished (9 arms x 20 cases). The ablation queue stopped mid-way; `scripts/midsub/winner-ablations-resume.sh` (unit `vs-ablate2`) resumes it. A1, A2, A8 and A9 cannot sit on top of all four winner switches (the Switches validator refuses the combinations), so they drop the switch they conflict with: A1 drops X1 and X5 (with no dossier everything reads the facts), A2 drops X4, A8 drops X7, A9 drops X4 and X7. Scoring: `scripts/midsub/autoscore-arms.sh` (units `vs-autoscore-holdout`, `vs-autoscore-ablate`).

## Freeze and blind run (9 Nov)
- Tags `prereg-v1` and `eval-freeze-v1` on 22fce4f (pushed). Pre-registration section 1.5 registers H-A1 to H-A5 for c1457; deviations D1 to D6 in its section 8.
- Unit `vs-blind` runs `scripts/midsub/blind-run.sh` in the worktree `.claude/worktrees/agent-a8400ab774cc73e44`, which stays **detached at eval-freeze-v1 and must not be edited or committed in** until the blind run ends (a new shard would record another git SHA or a dirty tree, and the scorer refuses mixed code). Report work happens in `.claude/worktrees/report-arch` (branch `arch-search`), with `VS_RUNS=<that worktree>/data/eval/dev_runs python3 scripts/midsub/final_tables.py`.
- Log: `data/eval/dev_runs/blind.log` in the run worktree; prints BLIND_RUNS_DONE, then BLIND_SCORED (one gated scoring call, `--slice blind --open-blind`, writes `data/eval/blind.lock`), then resumes the paused ablations (`vs-ablate2`) and scores them, then ALL_DONE.
- Test suite at the freeze: 22 failures in the full run, 3 fixed in code (runner for `arch_search`, the BGE-M3 job as an interactive script, no owner home paths); 19 remain and are declared in D5 (17 stale golden digests since 5bf4cd3, which needs an owner decision on re-capturing them; 2 M6a cells waiting for Shravani's rescore). No test was edited.

## Is c1457 the best configuration we have? (9 Nov, post-freeze, exploratory; pre-registration D9)
`scripts/midsub/candidate_pool.py` (output `docs/results/search/candidate_pool/summary.md`) compares every Sarvam-scored configuration, like for like only:
- Literature sweep (S1-S18, P5-P8, A5, A1-A9), each against the sweep's own Full (same code tree 7ad6ed41 and scorer; its M6 family used the offline stand-in checker): no variant improves on Full. Most tie on 10 orders; S1, S15, S17, S18 lose citation precision; S5 wins SC authorities and known treatment but loses citation precision and recall. So the sweep's best is Full itself, and the search started from Full.
- Architecture-search arms on one tree (b44ddeae, MiniCheck), against B0-B6 by the search's rule (fewest losses, then wins): c1457 and "c1457 minus X1" (X4+X5+X7) both have the 3 structural losses; X4+X5+X7 has 38 wins against 30. Head to head c1457 is better on SC authorities and known treatment and worse on the unsupported-fact count (2/17/1); the M6 difference is unresolved. Three independent checks (statistics, provenance, protocol) found the count gain comes from writing fewer claims (5.07 against 6.83 per order; supported claims 0.70 in both) and the extra wins are cells near the Holm level where c1457 has the same sign. Neither dominates; c1457 stays the headline. A holdout run of X4+X5+X7 was started and stopped after one case (D9), unscored.
- c1457 against Full head to head: 7 better, 10 tied, 3 worse (worse: citation precision, citation recall, unfinished-factor share).
- No configuration beats every baseline and every ablation on every metric. The cells nobody wins are the structural ones above, plus citation precision and recall where drafting from the facts text (X5) trades citation precision for faithfulness.
- Caveats: one run per arm, and the c1457 "second run" of the ablation batch is a response-cache replay (1846 of 1846 calls), not a replication; run-to-run variance on live Sarvam calls is not measured.
