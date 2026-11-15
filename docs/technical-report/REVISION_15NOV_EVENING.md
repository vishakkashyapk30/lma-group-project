# Revision of the technical report, 15 Nov 2026 (evening)

Files: `technical_report.tex`, `technical_report.pdf`. Built with `build.sh`: 17 pages, body on printed pages 1 to 8 (PDF pages 3 to 10), no LaTeX warnings, no undefined references; the one overfull box (the Contents rule, line 103) was already there. Every `\cite` key exists in `references.bib`; no reference added.

## (a) Change summary by brief section

1. **Framing.** Subtitle is now "A Multi-Agent Harness for Evidence-Grounded Bail Drafting"; "harness" is defined in Section 2 and used throughout. Abstract, introduction, contributions and conclusion follow the research question (does a structured multi-agent harness ground drafting better than simpler systems, and which decisions matter), the actual process (Full, no consistent edge, failure analysis, search on development data, VS-Final, sealed test) and keep Full and VS-Final apart. Agent specialisation is not presented as beneficial in itself.
2. **Evaluation scope.** Introduction separates intended application, evaluated task, demonstrated engineering and next validation steps. The six demo cases are described as demonstrating the interface and workflow. Figure 1 caption says the sealed evaluation starts at Sutradhar with the facts text, so Munshi, Pairokar and the Rights Radar are covered by tests and demos, not by that evaluation. No readiness claim.
3. **Metrics.** M6 defined in Section 5 as "not entailed by the case facts", stated not to be a hallucination rate, with the cause (legal propositions cannot be entailed by facts). M6a reported beside it; the paired M6a comparison is now given (below). Fabricated-citation rate (validity) separated from citation precision (support); unsupported, unverifiable and legally incorrect separated. "Confident wrong" renamed (see (d)).
4. **Reference labels.** "Gold without annotators" is now "Automatically derived reference labels". kappa 0.60, 0.84, 0.78 kept; implications stated (agreement is consistency not correctness; filtering favours clear cases, 81 of 250 orders without an agreed factor and 88 with an agreed objection; orders record what the court discussed; model labels are not expert annotation). Expert validation is future work; no human results introduced. "Gold" replaced in prose, glossary and appendix tables.
5. **Ablations.** Section 7 sorts them into single-switch removals (X1, X4, X5, X7, A3, A4, A6, A7), combined removals (A1, A2, A8, A9) and the free planner (measurement artefact). A2 cannot be separated from X4 (X4 alone costs 4 of A2's 5 cells), A8 equals the X7 removal (the same 2 cells). "Check and repair and sparring earn their place" is removed. Table A7 rows and caption mark the combined removals. All numbers kept. The main-text ablation table was moved out (it duplicated Table A7).
6. **Results communication.** W/T/L explained at every appearance as metric-by-baseline comparison outcomes (120 comparisons: 25 metrics x 7 baselines minus 13 too few and 42 undefined), not cases or trials; Holm stated as within system, baseline family and metric. Results lead with task metrics and paired intervals, trade-offs together (citation precision 0.85 to 0.71, unfinished factors 0.17 to 0.40). Five hypotheses kept, H-A1 falsified. Sample sizes per metric (factor recall 9, objection recall 25, answerable coverage 32, M6a 43/27) stated.
7. **Cost.** New "Cost and latency" paragraph: seconds 719/398/269/160, tokens 122,387/98,814/120,614/79,877, store calls 110/103/188/89, retrieval-call efficiency separated from system efficiency, usability not studied. Table A5 errors row clarified (see (d)).
8. **Transparency.** Limitations section lists: 80 of 200 orders, one model family, one run, exploratory reruns on development orders, post-freeze restarts and scorer repair, small effective samples, undefined cells, post-freeze reserve exploratory and not run on the sealed slice. Deviations table kept. Caveats are stated once where the metric is defined, with their cause, and gathered with causes in Section 9 (owner's tone note applied).
9. **Writing.** Slogans removed ("parts earn their place", "more parts is not better until measured"), claims tied to measurements, repetition between abstract, results and conclusion cut. Banned-word scan clean.
10. **Conclusion.** Three findings (Full did not consistently beat simpler systems; failure-driven changes improved several measures; remaining gaps have causes), a discussion of agents versus evidence contracts, abstention and handoffs, explicit non-generalisation, what would close the gaps.
11. **Presentation.** Glossary and appendix terms updated (agreed labels, doubly unsupported rate, W/T/L, M6, M6a, fabricated citations). Candidate table moved to Appendix F (Table A8) to keep the body within 8 pages; ablation table is Table A7. Title page design, blue headings, contents layout and numbered contributions unchanged.

## (b) Remaining concerns (need experiments or human review)

- No expert validation of the labels or of briefs; the proxy metrics are untested against lawyer judgement.
- M6a: 0.43 versus 0.75 are means over different orders (43 and 27); on the 16 shared orders the paired difference is -0.161 (-0.443 to +0.115). The M6a improvement is not established.
- Sealed slice is one model family, one run, 80 orders; objection recall rests on 25 orders and factor recall on 9.
- The scorer does not grade the sparring judge's verdicts; the post-freeze reserve gain is visible only in the judged share and was not run on the sealed slice.
- Latency (719 s) was measured with concurrent runs on a hosted endpoint; no controlled timing and no user study.
- Whether a model-side error in 6 VS-Final orders was an unexpected failure cannot be told from the logs.
- Carried-over numbers (worked case, 55%/9% flagged sentences, 2.8 of 13 fields, 66/230 objections, store sizes, privacy counts, development-slice and holdout figures, ablation rows) were not re-derived in this pass beyond the cross-checks below; they come from the previous version, which `scripts/check_consistency.py` covers for the long report. Recommend one run of it.

## (c) Consistency audit (verified in this pass)

Paths are under `docs/results/search/final_report/`.

| Number (location) | Source | Status |
|---|---|---|
| Objection recall 0.52 / 0.73 (abstract, Sec 6, Table 3) | `means_blind.csv` (0.5173, 0.732) | OK |
| Answerable coverage 0.36 / 0.61 | `means_blind.csv` (0.3594, 0.6094) | OK |
| Citation precision 0.85 / 0.71 | `means_blind.csv` (0.8453, 0.713) | OK |
| M6 0.99 / 0.89; M6a 0.75 / 0.43 | `means_blind.csv` (0.9863, 0.8882; 0.7531 n=27, 0.4291 n=43) | OK |
| Fabricated 0.00 vs B4 0.95, B5 0.64 | `means_blind.csv` (0.9545, 0.6389) | OK |
| Doubly unsupported 0.97 / 0.87; unfinished 0.17 / 0.40 | `means_blind.csv` (0.9727, 0.8652; 0.1654, 0.3986) | OK |
| Paired M6 -0.098 [-0.135, -0.063] n=79; citation precision -0.133 [-0.209, -0.060] n=77; doubly unsupported -0.101 [-0.143, -0.062] | `wlt_blind_c1457_vs_full.csv` | OK (new in text) |
| Paired M6a -0.161 [-0.443, +0.115] n=16, tie | `wlt_blind_c1457_vs_full.csv` | OK (new in text) |
| H-A2 +0.215 [+0.024, +0.400] n=25; +0.250 [+0.109, +0.406] n=32 | `summary.md` line 103 area | OK |
| H-A3 citation precision diffs +0.691, +0.724 | `summary.md` | OK |
| M6 vs baselines -0.05 to -0.12, vs B0 [-0.100, -0.001] | `summary.md` H-A4 line | OK |
| H-A1 +1.875 [+0.875, +3.067] | `summary.md` H-A1 line | OK |
| W/T/L 46/69/5 and 29/76/15; rule-only 45/70/5 and 29/74/17 | `summary.md` lines 76, 136 | OK |
| 120 comparisons = 175 - 13 - 42 | arithmetic from `summary.md` | OK |
| Seconds 719/398/269/160; tokens 122,387/98,814/120,614/79,877; store calls 110/103/188/89 | `summary.md` lines 83 to 94 | OK |
| Ratios 2.7x B4, 41% fewer store calls than B4 | arithmetic (719/269, 1-110/188) | OK |
| kappa 0.60 [0.55, 0.64] factors, 0.84 fields; 0.78 second labeler; rules vs model 0.59 | `docs/handoff/gold-labeler.md` lines 31 to 48 | OK |
| 81 of 250 orders without agreed factor; 88 with agreed objection | `gold-labeler.md` lines 77, 90 | OK |
| 80 of 200 test orders | `docs/preregistration.md` line 229, D1 | OK |
| Sparring reserve 227/233, 53/207, 130/233, 23/207, tokens 120,643 to 151,434, over-search 0.0107 to 0.0258 (+0.0152 [0.0046, 0.0276]), objection recall p=0.061 | `reserve_dev.md` lines 7, 8, 37, 48, 58, 59 | OK |
| Sample sizes: factor recall 9, objection recall 25, answerable coverage 32, M6a 43 | `means_blind.csv` (n= markers) | OK |
| Errored baseline records B1 25, B3 25 | `summary.md` line 57 | OK |
| Table A5 rows (149, 17, 1.0%, 3.8%, 1.7%, 80/80/79/78, 175/60/126/49) | `tool_calls_blind.csv` | OK |
| Errored-order breakdown for VS-Final (76 budget, 63 not found, 64 + 16 bad argument, 6 model-side) | frozen event logs read-only, `sarvam_blind/outputs/<arm>/_events/*.jsonl`, same counting rule as `scripts/midsub/tool_call_stats.py` | NEW, derived here |
| Contributions and abstract counts 30/37/3, 11/49/10, 22/26/3, 10/40/5 | `summary.md` lines 7, 15; Table A1 | OK |
| Other carried-over figures (see (b)) | previous version | NOT re-derived |

No number in the old text was changed to a different value. Wording changes only: "confident wrong" to "doubly unsupported", "gold" to "reference labels", "Unsupported-fact" now glossed as "not entailed by the facts".

## (d) Brief numbers and claims that did not match the artefacts

- All numbers quoted in the brief matched the artefacts (0.52/0.73, 0.36/0.61, 0.85/0.71, 0.99/0.89, 0.75/0.43, 0.89, 0.43, 0.71, 0.00, 719/398/269/160 s, 80 of 200, kappa 0.60 and 0.84, 46/69/5).
- Interpretation points the artefacts qualify: (1) M6a 0.75 versus 0.43 compares different order sets and is a tie when paired (above). (2) "Citation validity improved" holds against B4 and B5 only; Full is also 0.00. (3) The 2.7x slower versus B4 comes with a statistically tied token count.
- **Renamed metric:** "confident wrong" is now "doubly unsupported rate". `confident_wrong` in `src/vakeel_sahayak/eval/metrics/citations.py` computes the share of emitted sentences whose MiniCheck score against the facts is below the cut and that the rest of the same order also does not entail. That does not establish legal incorrectness. The report says once that the code calls it `confident_wrong_rate` (M35).
- **Table A5 errors row.** It counts an order if its event log has any typed error result of a tool call or any non-privacy model-side error (`scripts/midsub/tool_call_stats.py`). It therefore mixes expected refusals (budget exhaustion in 76 of 80 VS-Final orders, empty lookups in 63, bad arguments in at least 71) with model-side errors (model unavailable, failed extraction, invalid structured output in 6 orders). All 80 orders ended with a complete brief. The logs do not show whether the model-side errors were unexpected or expected fallbacks, so the caption describes that ambiguity. The row label is now "Orders with at least one typed error in the log". The scored per-order error flag (`n_errors`) is 0 for all VS-Final orders.
