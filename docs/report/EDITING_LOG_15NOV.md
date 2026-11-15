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
