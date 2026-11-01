# Preregistration draft, 1 November 2026 (branch `prereg-v1-draft`)

## Done
- `docs/preregistration.md` filled from the dev slice only: thresholds (delta, epsilon, C2, C4), registration status per claim, primary analysis, Holm families, exclusion rules, failure rules (sections 1 to 1.4), metric definitions (section 3), statistics seeds (section 6). The blind slice and `data/testsets/t1/blind_sealed.json` were not opened.
- `scripts/prereg_dev_stats.py` (reads only `docs/results/midsub/*/per_case_agreed.csv`) writes `docs/results/prereg/dev_stats.json`: every Full-minus-comparator difference with interval, Wilcoxon p, SD of differences and the minimum detectable effect at n = 80. Run: `PYTHONPATH=src .venv/bin/python scripts/prereg_dev_stats.py > docs/results/prereg/dev_stats.json`.
- `scripts/freeze_tags.sh`: `check`, `create prereg-v1`, `create eval-freeze-v1`. It needs a clean tree, refuses an existing tag, refuses `prereg-v1` while placeholders remain (unless `ALLOW_PLACEHOLDERS=1`), needs `prereg-v1` before `eval-freeze-v1`, and never pushes. No tag has been created.
- `configs/eval/hypotheses.yaml`: H1d, H1e added, `margin_vs_p4` set to 5 (provisional). Nothing reads this file in code.

## What the dev data force (read before tagging)
Full does not beat every baseline: B4 matches or beats it on objection recall and answerable coverage (OpenAI, v1; Sarvam reverses the sign on 11 orders), no baseline is worse on the unsupported-fact rate (it is near ceiling, 0.86 to 1.00, for every system), factor recall is defined on 8 of 50 dev orders. C1, C2, C3, C11, the quality half of C4 are registered as confirmatory and dev-contradicted (expected to fail). Supported on dev: C4 cost half (tokens ratio 0.77 to 0.82, store calls 0.52 to 0.54), C16, and the by-construction design checks against B0 to B3.

## The owner must confirm before tagging
1. **Thresholds.** delta and epsilon = 5 points (unsupported rate), 10 (lenient precision, F1), 15 (objection recall, coverage), 25 (factor recall); C2 reduction 5 points (plan said 3); C4 ratios 0.90 and 0.60. Rule: MDE at the blind effective n, rounded to 5 points (section 1.2). Say if you prefer to keep the plan's 3 points and accept that those tests cannot be decided at n = 80.
2. **Scorer code (needs a change before `eval-freeze-v1`, Harshita's modules).** `answerable_coverage` is not in `engine.PAIRED_METRICS`, and the family F-RQ1-coverage (objection recall and answerable coverage against B0, B0L, B1, B2, B3, B4; m = 12) is not in `engine.FAMILIES`. Without it the dev-supported H1d is not scored by the harness. Also missing: the pre-declared complete-case sensitivity (drop orders where either system errored) and the decision rule of section 1.4 that combines Holm rejection, sign and delta; today the scorer reports the Holm decision and the interval separately. Decide: add them (a code tag change) or register H1d and the sensitivity as exploratory.
3. **Headline backend.** Section 1.4 says one family per backend and names the headline backend as the one running Full, B0 to B4 and the ablations on every blind order. Name it in section 0 (dev: OpenAI is locked, Sarvam is open with cap INR 5000, Gemini has no B4). Note the sign against B4 flips between OpenAI and Sarvam on dev.
4. **Which checker produced the unsupported-fact numbers** (MiniCheck, DeBERTa NLI or the offline stand-in; manifests carry it). The registered threshold is 0.5 for MiniCheck; the dev rate is near ceiling, so the metric has low power whichever checker it was.
5. **Items I could not derive from the T1 dev scores** (plan defaults stand and are marked in the claim rows): C5, C6, C9, C14, C15, C17, C18 (no dev run or 0 resolved citations), C19 to C27 and C29 to C35 (T2 to T9 not among the inputs; `margin_vs_p4 = 5` is provisional), C36 to C39 (bounded). Fill "claims that will not be run" (section 1.1).
6. **Freeze-time values still placeholders** in `docs/preregistration.md`: date, the two SHAs, re-pasted switch set, prompt and config hash (check `driver.prompt_hash()` and `config_hash()` still match `dev-sweep-v3`), blind size / BNS-era / post-release counts (`manifest.json`, counts only), generation seeds, budgets, system manifest table, runs per system and case counts, backend caps, T2 to T9 hashes, the order of jobs and the blind opening date. `scripts/freeze_tags.sh check` lists how many placeholder lines remain.
7. **Gold hashes after the G2 merge**: agreed `5583690e...05be`, rule-only `4cde3451...8ab0` are abbreviated in section 3; paste the full values from the manifests.
8. **Dev errors**: errors sit in B0 to B3 (and 3 in Full on v1). The primary analysis counts them as scored (no drop, no retry beyond the driver's); check that is what you want.

## How to tag (only on request)
```bash
scripts/freeze_tags.sh check
scripts/freeze_tags.sh create prereg-v1        # after the placeholders are filled and committed on main
scripts/freeze_tags.sh create eval-freeze-v1   # at the clean code commit the runs come from
git push origin prereg-v1 eval-freeze-v1       # the script never pushes
```
The blind scoring entry point (`testsets/blind.py`) needs `eval-freeze-v1`; the preregistration commit must come first in time.
