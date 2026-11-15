# Sparring reserve on the 30 development search orders (post-freeze, exploratory, not registered)

## Objections by outcome (shares of objections raised)

| arm | orders | raised | judged | ANSWERED | PARTLY | UNANSWERED (judged) | not judged | of which NOT_REPLIED_BUDGET | reply drafted |
|---|---|---|---|---|---|---|---|---|---|
| R0 | 30 | 207 | 53 (26%) | 15 (7%) | 8 (4%) | 30 (14%) | 154 (74%) | 0 | 143 (69%) |
| R1 | 30 | 233 | 227 (97%) | 72 (31%) | 58 (25%) | 97 (42%) | 6 (3%) | 0 | 232 (100%) |
| frozen D12 run 1 | 30 | 216 | 58 (27%) | 19 (9%) | 7 (3%) | 32 (15%) | 158 (73%) | 0 | 153 (71%) |

Reason classes of the verdicts (keyword classes of the judge's reason text; 'not judged' is the fail-safe text of a refused reply or judge call):

| arm | answered | partly | not judged | not replied (budget) | no supported reply | statutory bar (NDPS s.37) | restates / no facts or authority | other |
|---|---|---|---|---|---|---|---|---|
| R0 | 15 | 8 | 154 | 0 | 0 | 10 | 19 | 1 |
| R1 | 72 | 58 | 6 | 0 | 0 | 17 | 74 | 6 |
| frozen D12 run 1 | 19 | 7 | 158 | 0 | 0 | 16 | 15 | 1 |

Failed sparring calls (task, error: count) and reserve use:

- R0: abhiyojak.judge_reply BudgetExhausted: 151; abhiyojak.judge_reply PrivacyBoundaryError: 3; vakeel.reply_objection BudgetExhausted: 61; vakeel.reply_objection PrivacyBoundaryError: 3
- R1: abhiyojak.judge_reply ModelUnavailable: 1; abhiyojak.judge_reply PrivacyBoundaryError: 5; vakeel.reply_objection PrivacyBoundaryError: 1; reserve spent per order: mean 75933, max 157040; BUDGET_HIT of the reserve in 0 order(s)
- frozen D12 run 1: abhiyojak.judge_reply BudgetExhausted: 155; abhiyojak.judge_reply PrivacyBoundaryError: 3; vakeel.reply_objection BudgetExhausted: 60; vakeel.reply_objection PrivacyBoundaryError: 3

## Quality metrics: means and paired R1 minus R0 (30 orders answered without error in both arms)

Interval: 95% percentile interval of the seeded paired bootstrap (10,000 resamples), not adjusted for the metrics; the Holm column says whether the metric also survives Holm over all metrics (alpha 0.05). Exploratory.

| metric | n | better | R0 mean | R1 mean | R1 - R0 | 95% interval | p | excludes 0 | Holm |
|---|---|---|---|---|---|---|---|---|---|
| Factor prec. (strict) | 5 | higher | 0.1000 | 0.1000 | +0.0000 | [+0.0000, +0.0000] | 1.000 | no | no |
| Factor prec. (lenient) | 5 | higher | 0.1000 | 0.1000 | +0.0000 | [+0.0000, +0.0000] | 1.000 | no | no |
| Unsupported facts (M6) | 29 | lower | 0.8780 | 0.8987 | +0.0207 | [-0.0479, +0.0945] | 0.580 | no | no |
| Unsupported case facts (M6a) | 12 | lower | 0.4980 | 0.3333 | -0.1647 | [-0.5278, +0.1964] | 0.401 | no | no |
| Unsupported facts, count | 30 | lower | 5.3000 | 5.6000 | +0.3000 | [-0.9000, +1.5000] | 0.635 | no | no |
| Answerable coverage | 11 | higher | 0.6061 | 0.5152 | -0.0909 | [-0.3636, +0.1818] | 0.764 | no | no |
| Objection recall | 11 | higher | 0.7273 | 1.0000 | +0.2727 | [+0.0000, +0.5455] | 0.061 | no | no |
| Objection precision | 10 | higher | 0.1717 | 0.1900 | +0.0183 | [-0.0383, +0.0833] | 0.580 | no | no |
| Coverage | 30 | higher | 0.9500 | 0.9917 | +0.0417 | [-0.0167, +0.1250] | 0.326 | no | no |
| Fabricated citations | 28 | lower | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | 1.000 | no | no |
| Authorities: reasoning | 28 | higher | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | 1.000 | no | no |
| Authorities: SC | 28 | higher | 0.0807 | 0.0601 | -0.0205 | [-0.0627, +0.0152] | 0.316 | no | no |
| Authorities: before order | 28 | higher | 1.0000 | 1.0000 | +0.0000 | [+0.0000, +0.0000] | 1.000 | no | no |
| Good-law violations | 28 | lower | 0.0000 | 0.0000 | +0.0000 | [+0.0000, +0.0000] | 1.000 | no | no |
| Known treatment | 28 | higher | 0.0329 | 0.0238 | -0.0091 | [-0.0291, +0.0048] | 0.348 | no | no |
| Citation precision | 28 | higher | 0.7388 | 0.7855 | +0.0467 | [-0.0665, +0.1659] | 0.437 | no | no |
| Citation recall | 28 | higher | 0.7595 | 0.7854 | +0.0260 | [-0.0759, +0.1350] | 0.646 | no | no |
| Over-search | 30 | lower | 0.0107 | 0.0258 | +0.0152 | [+0.0046, +0.0276] | 0.001 | yes, worse | yes |
| Unfinished factors | 30 | lower | 0.4253 | 0.3495 | -0.0758 | [-0.1617, +0.0098] | 0.092 | no | no |
| Confident wrong | 29 | lower | 0.8735 | 0.8987 | +0.0252 | [-0.0431, +0.0979] | 0.486 | no | no |

Not compared (defined on fewer than 5 paired orders, as in the report): Factor recall (n=4), Factor F1 (n=4), Court-discussed recall (n=0), Recall@10 (n=0), Removal changes claim (n=0).

## Tokens and spend

| arm | orders | tokens per order (mean, scorer; R1 includes the reserve) | INR total (ledger) | Sarvam ledger rows | INR per order |
|---|---|---|---|---|---|
| R0 | 30 | 120643 | 55.6 | 1812 | 1.85 |
| R1 | 30 | 151434 | 69.0 | 2312 | 2.30 |
| frozen D12 run 1 | 30 | 120035 | not read |  |  |

## W/T/L against B0-B6 (the frozen `sarvam_final` baseline runs on the same 30 orders; Holm within each arm and metric, as in the report)

| arm | B0 | B1 | B2 | B3 | B4 | B5 | B6 | total W/T/L (+too few, undefined) |
|---|---|---|---|---|---|---|---|---|
| R1 | 3/3/0 | 3/10/0 | 3/3/0 | 3/3/0 | 8/6/2 | 6/9/2 | 4/2/0 | 30/36/4 (+43, 62) |
| R0 | 3/3/0 | 3/10/0 | 4/2/0 | 4/2/0 | 7/7/2 | 4/12/1 | 4/2/0 | 29/38/3 (+43, 62) |

Losses R1: Confident wrong vs B4; Over-search vs B5; Unfinished factors vs B4; Unfinished factors vs B5

Losses R0: Confident wrong vs B4; Unfinished factors vs B4; Unfinished factors vs B5

Exploratory and post-freeze. One run per arm; the model is not deterministic (the D12 spread of c1457 against B0-B6 between reruns was 30/31/3 and 35/28/3); R0 runs the current code, not the frozen code.
