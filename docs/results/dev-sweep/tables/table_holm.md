### Holm decisions by registered family (preliminary)

*Preliminary dev result: dev slice (50 orders; the n of each system is in the table), gold source agreed.*

| Family | Claims | Registered tests (m) | Comparator | Metric | Difference | p | Holm decision |
|---|---|---|---|---|---|---|---|
| F-RQ1-recall | C1 | 6 | b0 | factor_recall | -0.250 | 0.6250 | not rejected (sign against reference) |
| F-RQ1-recall | C1 | 6 | b0l | factor_recall |  |  | not run |
| F-RQ1-recall | C1 | 6 | b1 | factor_recall | -0.375 | 0.2500 | not rejected (sign against reference) |
| F-RQ1-recall | C1 | 6 | b2 | factor_recall |  |  | not run |
| F-RQ1-recall | C1 | 6 | b3 | factor_recall |  |  | not run |
| F-RQ1-recall | C1 | 6 | b4 | factor_recall | -0.375 | 0.2500 | not rejected (sign against reference) |
| F-RQ1-halluc | C2 | 6 | b0 | unsupported_fact_rate | +0.017 | 0.6593 | not rejected (sign against reference) |
| F-RQ1-halluc | C2 | 6 | b0l | unsupported_fact_rate |  |  | not run |
| F-RQ1-halluc | C2 | 6 | b1 | unsupported_fact_rate | +0.095 | 0.0166 | not rejected (sign against reference) |
| F-RQ1-halluc | C2 | 6 | b2 | unsupported_fact_rate |  |  | not run |
| F-RQ1-halluc | C2 | 6 | b3 | unsupported_fact_rate |  |  | not run |
| F-RQ1-halluc | C2 | 6 | b4 | unsupported_fact_rate | +0.052 | 0.1549 | not rejected (sign against reference) |
| F-RQ1-guard | C3 | 8 | b0 | factor_precision_lenient | -0.306 | 0.2500 | not rejected (sign against reference) |
| F-RQ1-guard | C3 | 8 | b1 | factor_precision_lenient | -0.262 | 0.2500 | not rejected (sign against reference) |
| F-RQ1-guard | C3 | 8 | b4 | factor_precision_lenient | -0.069 | 0.5000 | not rejected (sign against reference) |
| F-RQ1-guard | C3 | 8 | b6 | factor_precision_lenient | -0.222 | 0.5000 | not rejected (sign against reference) |
| F-RQ1-guard | C3 | 8 | b0 | factor_f1 | -0.225 | 0.6250 | not rejected (sign against reference) |
| F-RQ1-guard | C3 | 8 | b1 | factor_f1 | -0.350 | 0.2500 | not rejected (sign against reference) |
| F-RQ1-guard | C3 | 8 | b4 | factor_f1 | -0.312 | 0.2500 | not rejected (sign against reference) |
| F-RQ1-guard | C3 | 8 | b6 | factor_f1 | -0.562 | 0.1250 | not rejected (sign against reference) |
| F-ablate-recall | C10-C12 | 6 | a1 | factor_recall |  |  | not run |
| F-ablate-recall | C10-C12 | 6 | a3 | factor_recall |  |  | not run |
| F-ablate-recall | C10-C12 | 6 | a4 | factor_recall |  |  | not run |
| F-ablate-recall | C10-C12 | 6 | a6 | factor_recall |  |  | not run |
| F-ablate-recall | C10-C12 | 6 | a7 | factor_recall |  |  | not run |
| F-ablate-recall | C10-C12 | 6 | a1 | unsupported_fact_rate |  |  | not run |
| F-sparring | C7, C8, C13, C28 | 6 | s9 | objection_recall |  |  | not run |
| F-sparring | C7, C8, C13, C28 | 6 | s10 | objection_recall |  |  | not run |
| F-sparring | C7, C8, C13, C28 | 6 | a2 | objection_recall |  |  | not run |
| F-sparring | C7, C8, C13, C28 | 6 | a8 | objection_recall |  |  | not run |
| F-sparring | C7, C8, C13, C28 | 6 | a9 | objection_recall |  |  | not run |
| F-sparring | C7, C8, C13, C28 | 6 | s8 | unsupported_fact_rate |  |  | not run |
| F-retrieval | C5, C14 | 4 | a4 | recall_at_10 |  |  | not run |
| F-retrieval | C5, C14 | 4 | s4 | recall_at_10 |  |  | not run |
| F-retrieval | C5, C14 | 4 | s5 | recall_at_10 |  |  | not run |
| F-retrieval | C5, C14 | 4 | s16 | recall_at_10 |  |  | not run |

- Holm-Bonferroni with alpha 0.05 and the registered family size m (a test not run counts as p = 1). Families: F-RQ1-recall = b0,b0l,b1,b2,b3,b4 on factor_recall; F-RQ1-halluc = b0,b0l,b1,b2,b3,b4 on unsupported_fact_rate; F-RQ1-guard = b0,b1,b4,b6 on factor_precision_lenient,factor_f1; F-ablate-recall = a1,a3,a4,a6,a7 on factor_recall, a1 on unsupported_fact_rate; F-sparring = s9,s10,a2,a8,a9 on objection_recall, s8 on unsupported_fact_rate; F-retrieval = a4,s4,s5,s16 on recall_at_10
- C1 (F-RQ1-recall) is an intersection-union claim: it holds only if every registered comparison is significant at alpha 0.05 without Holm and in the reference's favour; a comparator not run leaves it incomplete. Verdict: not supported.
