# Editing log, 15 November 2026

Rule applied (owner): caveats only in `limitations.tex`; every other section states what the project does and achieves. No result, table cell, W/T/L count, hypothesis outcome, D-number or failure fact was deleted; results stayed in place and only the sentences that qualified them moved.

## Caveats moved into `sections/limitations.tex` (now "Limitations, Risks and Future Work", label unchanged)
- abstract.tex: rewritten; "first full system did not beat every baseline" became a neutral result; "No export happened" became "all 320 early export attempts were refused"; pointer to limitations added.
- blind.tex "What the numbers mean in absolute terms" (0.89 and 0.71 readings, 55% legal principles) to limitations "What M6 measures" and "Citation precision"; replaced by a positive paragraph (0.47 against 0.84 on case facts).
- blind.tex T6 "not measured" sentence to limitations (RQ2, T6, T7). The worked case stays; "Failure examples" became "Failure cases we diagnosed" with the fix stated; "we did not rerun the blind slice" moved to limitations.
- blind.tex 68% never-judged story: counts stay in blind.tex (they are results); the reading (starved sparring step, what the metrics describe) moved to limitations "Frozen runs".
- limitations.tex old bullets reorganised into subsections: measurements, sparring token budget, statute data and radar, runs not made, privacy and cost, future work.
- evaluation.tex: labeler-not-independent sentence, dev has no resolved citation, kappa weak factors and G7 1 of 250, B0L "no larger Sarvam model priced" (to limitations "Gold labels are not human").
- data.tex: 37.3% resolution parenthetical and "facts part is short" (to limitations "Thin facts", "Gold").
- system.tex: 37.3%, "32B failed", budget figures (INR 225, 4.15 USD), 5 refused orders (to limitations "Privacy boundary", "Stand-in arms", "Budgets").
- results.tex: "small", "S13 not run", "first look only", A10 "plumbing" reading, S7/S17 "not scored", T4 "readings not right in law / no model run on T4", S4 AUROC overlap, S5 proxy bias, S14 simulation, S16 target, S6/B5 "no effect until prior trained" (to limitations "Offline studies", "Stand-in arms", "RQ2 and fine-tuning", "Rights Radar scope").
- challenges.tex: spend numbers, "dropped for now", disk 97%, "no local fallback", "none has resolved citation" (to limitations "Budgets and compute", "Privacy boundary"); rows rewritten as problem and fix; split into two tables (float too large).
- threats.tex: the caveat list moved to limitations ("One model, one slice", "Gold labels", "Thin facts and transfer"); section kept as the controls applied, with one pointer clause.
- conclusion.tex: six future-work items replaced by one paragraph pointing to limitations; the full list is limitations "Future work" (eight items).
- ethics.tex: "We do not claim zero leakage... Hindi coverage thin" to limitations "Privacy boundary".
- literature.tex "Measured on a model, and not yet" reworded to "Where each variant ran"; appendix.tex "not yet scored" cells now "scoring is future work".
- introduction.tex: "RQ2 not scored / extractor not trained" to limitations; capabilities-table fine-tuning row "Not done" reworded to "built, training is future work".

## New caveat text in limitations.tex (from the handoff notes)
Sparring token budget (frozen 68%; the reserve; 27%, 17%, 120,000 and 200,000 measurements); empty statutory position; statute-store bail flags (43 of 398); maximum-punishment lookup fixes of 15 Nov (BNS 109 with 3(5), NDPS clauses; conspiracy and Part II still open; bare NDPS section stays CHECK); Rights Radar scope (7 of 7, acts only, Companies Act s.212 copy of March 2016, hash-bound verification, T4 conformance, case 01 half threshold); D13 and D14; Hindi interface (machine-translated, not reviewed, partly English); no authentication; privacy boundary; paid lock; no outcome predictions.

## New passages (body)
- abstract.tex: Hindi interface, six demo cases, 24 wins and no loss against B0 to B3, 0.52 to 0.73 and 0.36 to 0.61, 110 against 188, 320 refused exports.
- introduction.tex: sixth contribution (evaluator demo, Hindi interface).
- system.tex: paragraphs "Sparring reserve", "Evaluator demo", "Hindi interface".
- challenges.tex: four rows (statute-store bail flags, empty statutory position, maximum-punishment lookup, sparring token budget) as found and fixed.
- status.tex: rewritten (built, since first draft, state table, timeline); now included in main.tex after threats (it was not in the build before).
- conclusion.tex: demo, Hindi, reserve in "What was built"; H-A1 stated as a result.
- appendix.tex: paragraph on demo cases, reserve and D13/D14 files; models table rows for demo recordings and Hindi translation.
- threats.tex: reframed as controls.

## Numbers added and sources
- 24 wins, 0 losses against B0 to B3 (4+6+7+7 wins, 0 losses): `docs/results/search/final_report/summary.md`, blind table. The task brief said "46 wins and no loss against B0 to B3"; 46 is the total against B0 to B6, so the report says 24.
- 27% judged with no reserve (216 objections, 158 not judged), 17% at 60,000 (7 of 41), 8 of 67 at 120,000, 53 of 68 at 200,000, 15 left, case 01 11 of 16 (22,000 left against an estimated 26,000): `docs/handoff/sparring-reserve-measurement.md`, `objections-unanswered-2026-11-15.md`, `evaluator-demo.md`. The task brief gave "98% on the 8 orders at 120000"; the notes give 8 judged of 67 objections at 120,000 (59 never judged), and 98% is the share refused before judging in the first recording (40 of 41), so the report uses the notes. `reserve_dev.md` does not exist; the 30-order measurement has no complete result and none is reported.
- 58, 26, 109, 406 of 599 (10, 4, 18, 68%), the 394/11/1 split, 79 restate, 26 no-reply text, 36 NDPS s.37: `objections-unanswered-2026-11-15.md`.
- INR 36.67, 85 to 139 calls, 1,010 strings, 131 unchanged, nine-step tours, models gemma-4-31b-it and gemini-3.5-flash-lite: `evaluator-demo.md`.
- Radar fixes (21(a) 1 year, 21(b) 10, 21(c) 20; case 01 half threshold 1,278 against 852 days): `first-schedule.md` 15 Nov section, `evaluator-demo.md`.
- D13 (70 cells set to 0) and D14 (12 rows, six arms, two orders): `docs/preregistration.md`.
- All other numbers already stood in the report.

## Kept in place because they are results
H-A1 "Falsified" and its row; W/T/L tables; D10, D11, D12 paragraphs; 86% unanswered and 10% answered; the loss cells (unfinished-factor share, confident-wrong, coverage against B6, unsupported count against B5); development results where Full trails baselines; the ablation rows against the winner; the failure cases' facts; "On these runs Full does not beat every baseline".

## Build and checks
`bash docs/report/build.sh`: 48 pages (45 before). Warnings: only the two "Text page contains only floats" notes that existed before. `scripts/check_consistency.py`: 0 failed.


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

Passages: `sections/system.tex` paragraph "What the reserve changes on development orders" and Table `tab:reserve`; `sections/limitations.tex` "The reserve added after the freeze" (six limits) and Future work (second item); `sections/challenges.tex` (reserve row); `sections/appendix.tex` (demo, reserve paragraph); `sections/abstract.tex` (one sentence).

## Status table (`sections/status.tex`), owners and dates from the git log and `docs/status/*.md`
Hindi interface: Harshita (commit by Harshita-K, 14 Nov; `docs/status/harshita.md`); Hindi tour captions, demo cases, sparring reserve and its measurement, Rights Radar fixes, D13, D14, the 13 Nov label-source and rerun checks, the final report: Vishak (committer in the git log). A4/A5 block and A10: Shravani as before (`docs/status/shravani.md`), with the 15 Nov rerun (D14) and D13 repair by Vishak. The timeline row 13 Nov no longer lists the Hindi interface, which moved to its own 14 Nov row. New row: sparring reserve measured on 30 development orders, Vishak. Rows that still say "all" were not touched.
