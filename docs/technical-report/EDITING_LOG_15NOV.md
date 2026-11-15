# Editing log, 15 November 2026

Rule applied: caveats live only in "Limitations and Future Work" (Section 8); everywhere else the report states what the project does and achieves. No measured number, table cell, W/T/L count or registered-hypothesis outcome was removed or changed. Scope hedges ("on the 80 sealed orders", "against seven baselines", "on development orders") stay.

## Caveats moved to Section 8

| Caveat | From | To |
|---|---|---|
| "the facts alone still fail to entail 0.89 ... a first draft for counsel" | Abstract, last sentence | Limitations, "What M6 measures" |
| "Our own experience shows why the test is needed ... did not beat every baseline" (defect framing) | Introduction | Reworded as the starting point of the test; the measured results stay in Section 3 |
| "an owner decision locked OpenAI and the free tier had no B4 run and too low a quota" | Section 3, "What ran on which model" | Limitations, "One model, one slice, one run" (Section 3 keeps a pointer) |
| "These wins are relative, and the absolute numbers remain low"; M6 0.89 reading; citation precision 0.71 reading (three in ten) | Results, "Absolute meaning" | Limitations, "What M6 measures" |
| 599 objections, 86% unanswered, 10% answered | Results, "Absolute meaning" | Limitations, "A sparring step starved by the token budget" (now with 68% never judged, 18% judged unanswered, 4% partly) |
| "single orders do not [survive a rerun]"; "hosted model is not deterministic"; per-order M6 62% / 0.13 and citation precision 93% | Results, "Reruns (D12)" | Limitations, "One model, one slice, one run" (Results keeps the W/T/L of both reruns and "2 of 225 cells") |
| "tools, the factor filter and the dossier are not resolved" | Section 7 | Removed as a hedge; the numbers (no more than one cell changes) stay |
| "did not take them [ablations] to the sealed slice" | Section 7 | Limitations, "One model, one slice, one run"; Section 7 states they ran on the 30 search orders |
| "Cost: pays for these gains in two places" | Section 4 | Reworded neutrally as "Effect on citations and tokens" (numbers unchanged) |
| "which is the price of drafting from the facts" | Results, "Main result" | Reworded: the three losses are named, then "follow from" drafting from the facts |
| "Why Full lost", "What failed, and why", "Losses that remain", "Two single fixes also failed" | Section 3 headings and wording | Headings and verbs made neutral; every number unchanged |
| Conclusion's "only after we diagnosed and fixed its failures", "One registered hypothesis failed, on a count that favours systems that write less", "Next, we will ..." | Conclusion | Conclusion states strengths and the four of five hypotheses; plans moved to "Future work" |
| Empty statutory position, statute-store error (43 of 398), post-freeze fixes | Limitations (existing) | Merged into "Statutory position and Rights Radar", with the radar's maximum-punishment lookups (BNS 109 with 3(5), NDPS clauses) added |

## New passages

- Section 2 (System), "Evaluator demo and Hindi interface": six recorded synthetic cases, pre-loaded, nine-step read-only tour with Next, real Gate 2, variety by offence and law, custody and rights, record quality, parity and history; the Hindi interface. Source: `docs/handoff/evaluator-demo.md`.
- Section 1: a clause in contribution (1) pointing to the demo and Hindi interface; one abstract clause.
- Section 4 (Final Method), "Sparring reserve (after the freeze)": the opt-in reserve, interleaved judging, NOT_REPLIED_BUDGET, 53 of 68 judged in the six final recordings, pointer to Limitations.
- Section 6 (Results), "What the means show": objection recall, answerable coverage, M6 and M6a stated as strengths, all from Table 4 and the hypothesis table.
- Section 8: rewritten as "Limitations and Future Work": paragraphs on M6 and citation precision, the starved sparring step and the reserve's measured status, statutory position and Rights Radar, one model/slice/run and variance, gold labels and the M6a historical repairs (D13, D14), privacy and scope, Future work.
- Conclusion rewritten around the strengths.
- Appendix: D13 and D14 rows in the deviation table (source: `docs/preregistration.md`, section 8), "Fourteen" in the caption and in Section 5 ("D1 to D14"); glossary entries for sparring reserve, NOT_REPLIED_BUDGET, evaluator demo, and D1 to D14.
- Layout only: the contents line spacing went from 1.12 to 1.05 so the contents stay on one page.

## Numbers added, with sources

| Number | Where | Source |
|---|---|---|
| 406 of 599 never judged (68%); 18% judged unanswered, 4% partly, 10% answered | Sec. 8 | `docs/handoff/objections-unanswered-2026-11-15.md` (blind slice counts: 406, 109, 26, 58 of 599) |
| 27% judged with no reserve (30 development orders) | Sec. 8 | `sparring-reserve-measurement.md`: D12 run 1, 216 objections, 158 not judged |
| 17% judged at 60000 (7 orders) | Sec. 8 | `sparring-reserve-measurement.md` |
| 98% judged on 8 orders at 120000, before the interleaving | Sec. 8 | The task instruction; no file in this tree contains it (see note) |
| 200000 reserve; 53 of 68 judged, 15 left for counsel, case 01 left 11 of 16 | Secs. 4, 8, glossary | `docs/handoff/evaluator-demo.md` |
| 55% and about 9% (flagged sentences) | Sec. 8 | already in the report (Section 3) |
| 0.20, 0.23, 0.35, 0.36, 0.52, 0.73, 0.61, 0.94 to 1.00 | Sec. 6 "What the means show" | report Table 4 and the hypothesis table |
| 62%, 0.13, 93% | Sec. 8 | moved from Results (D12) |
| D13 (70 cells, seven A10 arms), D14 (six arms, 12 rows, two orders, 15 Nov) | Sec. 8, appendix | `docs/preregistration.md` section 8 |
| "nine steps", "six cases" | Sec. 2 | `docs/handoff/evaluator-demo.md` |

Note: `docs/results/search/final_report/reserve_dev.md` does not exist; the report says the development-order measurement of the final configuration is in progress and gives no numbers from it. The 98% figure comes from the instruction and is not in any handoff note in this tree; `evaluator-demo.md` gives 8 of 67 judged at 120000 on the demo cases, a different set of orders.

## Left in place because it is a result

Table 3 (H-A1 falsified on one cell), all W/T/L counts including the 5 losses and Full's 15, the structural losses (unfinished factors, confident wrong, coverage against B6), the citation precision fall from 0.85 to 0.71 and 0.82 to 0.68, the D11 and D12 W/T/L, the unsupported-count loss to B5, the "Losses of VS-Final" paragraph, the rejected candidates with their reasons, and the ablation table with its A7 rows.


## Sparring-reserve measurement on the 30 development orders (added after the measurement finished)
Source for every number: `docs/results/search/final_report/reserve_dev.md` (sections named below), `docs/handoff/sparring-reserve-measurement.md`.

| Number | Where | Source |
|---|---|---|
| 227 of 233 judged (97%); 53 of 207 (26%) | body, limitations, abstract, glossary or appendix | "Objections by outcome": R1 judged 227 (97%), R0 53 (26%) |
| 72 answered, 58 partly answered; 130 of 233 = 56% | body | same table; arithmetic 72+58=130, 130/233=0.558 |
| 23 of 207 (11%) for the arm with no reserve | body | same table: 15+8=23, 23/207=0.111 |
| 0 orders ran out; mean 75,933, maximum 157,040 of 200,000 (long report) | body | "Failed sparring calls and reserve use" |
| tokens per order 120,643 to 151,434 (+26%); INR 2.30 against 1.85; INR 69.0 against 55.6 | body | "Tokens and spend": 151434/120643=1.255 |
| 20 paired metrics compared; over-search 0.0107 to 0.0258, +0.0152, [+0.0046, +0.0276], survives Holm | body, limitations | "Quality metrics" table (20 rows), Over-search row |
| objection recall 0.73 to 1.00, +0.27, [0.00, +0.55], p 0.061 | body | Objection recall row (the file's +0.2727 and [+0.0000, +0.5455] to two decimals) |
| W/T/L 30/36/4 against 29/38/3; extra loss over-search against B5 | body, limitations | "W/T/L against B0-B6" and the loss lists |
| 30/31/3 and 35/28/3 (D12 reruns) | limitations | last line of the file |
| 5 privacy-boundary refusals and 1 model error among the 6 not judged | limitations | "Failed sparring calls": R1 PrivacyBoundaryError 5, ModelUnavailable 1 |
| about 7 objections per development order | limitations | handoff note ("these orders raise about 7 objections each"); 207/30=6.9 |
| 26% to 97% (frozen D12 run 1: 58 of 216, 27%) | glossary or appendix, challenges row, abstract | table rows |
| 120,035 tokens (frozen D12 run 1) and the counts of long-report Table `tab:reserve` | long report | "Objections by outcome" and "Tokens and spend" |

Caveats are only in Limitations and Future Work. The arm with no reserve is the current code, not the frozen code; this is stated there.

Passages: Final Method "Sparring reserve (after the freeze)" (measurement sentences added); Limitations "A sparring step starved by the token budget" (the "in progress, no numbers" sentence replaced by the result and five limits); Future work (over-search added); glossary row "Sparring reserve" (numbers); abstract (one sentence).
