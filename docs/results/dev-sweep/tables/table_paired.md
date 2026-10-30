### Paired comparisons with the reference (preliminary)

*Preliminary dev result: dev slice (50 orders; the n of each system is in the table), gold source agreed.*

| Comparison | Metric | n | Difference [95% CI] | p (test) | d_z / odds ratio | Family (Holm) |
|---|---|---|---|---|---|---|
| full minus b0 | factor_f1 | 8 | -0.225 [-0.625, +0.250] | 0.6250 (wilcoxon) | -0.33 | F-RQ1-guard: not rejected |
| full minus b0 | factor_hits_pooled (McNemar, cluster bootstrap) | 8 | -0.250 [-0.750, +0.250] | 0.6250 (mcnemar exact (items)) | 0.33 | exploratory (uncorrected) |
| full minus b0 | factor_precision_lenient | 6 | -0.306 [-0.639, -0.028] | 0.2500 (wilcoxon) | -0.72 | F-RQ1-guard: not rejected |
| full minus b0 | factor_recall | 8 | -0.250 [-0.750, +0.250] | 0.6250 (wilcoxon) | -0.35 | F-RQ1-recall: not rejected |
| full minus b0 | objection_recall | 20 | +0.688 [+0.500, +0.863] | 0.0003 (wilcoxon) | 1.58 | exploratory (uncorrected) |
| full minus b0 | pass_per_case (McNemar) | 8 | -0.250 | 0.6250 (mcnemar exact) | 0.33 | exploratory (uncorrected) |
| full minus b0 | recall_at_10 | 0 | too few cases |  |  |  |
| full minus b0 | store_calls | 50 | +103.970 [+100.890, +106.780] | 0.0000 (wilcoxon) | 9.66 | exploratory (uncorrected) |
| full minus b0 | tokens | 50 | +97998.450 [+93099.750, +102962.125] | 0.0000 (wilcoxon) | 5.39 | exploratory (uncorrected) |
| full minus b0 | unsupported_fact_rate | 43 | +0.017 [-0.052, +0.086] | 0.6593 (wilcoxon) | 0.07 | F-RQ1-halluc: not rejected |
| full minus b1 | factor_f1 | 8 | -0.350 [-0.700, -0.100] | 0.2500 (wilcoxon) | -0.72 | F-RQ1-guard: not rejected |
| full minus b1 | factor_hits_pooled (McNemar, cluster bootstrap) | 8 | -0.375 [-0.750, -0.125] | 0.2500 (mcnemar exact (items)) | 0.00 | exploratory (uncorrected) |
| full minus b1 | factor_precision_lenient | 7 | -0.262 [-0.571, -0.024] | 0.2500 (wilcoxon) | -0.64 | F-RQ1-guard: not rejected |
| full minus b1 | factor_recall | 8 | -0.375 [-0.750, -0.125] | 0.2500 (wilcoxon) | -0.72 | F-RQ1-recall: not rejected |
| full minus b1 | objection_recall | 20 | +0.688 [+0.500, +0.863] | 0.0003 (wilcoxon) | 1.58 | exploratory (uncorrected) |
| full minus b1 | pass_per_case (McNemar) | 8 | -0.375 | 0.2500 (mcnemar exact) | 0.00 | exploratory (uncorrected) |
| full minus b1 | recall_at_10 | 0 | too few cases |  |  |  |
| full minus b1 | store_calls | 50 | +102.970 [+99.890, +105.780] | 0.0000 (wilcoxon) | 9.56 | exploratory (uncorrected) |
| full minus b1 | tokens | 50 | +94388.090 [+89546.867, +99290.061] | 0.0000 (wilcoxon) | 5.26 | exploratory (uncorrected) |
| full minus b1 | unsupported_fact_rate | 45 | +0.095 [+0.026, +0.162] | 0.0166 (wilcoxon) | 0.40 | F-RQ1-halluc: not rejected |
| full minus b4 | factor_f1 | 8 | -0.312 [-0.646, -0.021] | 0.2500 (wilcoxon) | -0.64 | F-RQ1-guard: not rejected |
| full minus b4 | factor_hits_pooled (McNemar, cluster bootstrap) | 8 | -0.375 [-0.750, -0.125] | 0.2500 (mcnemar exact (items)) | 0.00 | exploratory (uncorrected) |
| full minus b4 | factor_precision_lenient | 12 | -0.069 [-0.194, +0.028] | 0.5000 (wilcoxon) | -0.34 | F-RQ1-guard: not rejected |
| full minus b4 | factor_recall | 8 | -0.375 [-0.750, -0.125] | 0.2500 (wilcoxon) | -0.72 | F-RQ1-recall: not rejected |
| full minus b4 | objection_recall | 20 | -0.237 [-0.450, -0.037] | 0.0371 (wilcoxon) | -0.49 | exploratory (uncorrected) |
| full minus b4 | pass_per_case (McNemar) | 8 | -0.375 | 0.2500 (mcnemar exact) | 0.00 | exploratory (uncorrected) |
| full minus b4 | recall_at_10 | 0 | too few cases |  |  |  |
| full minus b4 | store_calls | 50 | -90.970 [-94.900, -86.080] | 0.0000 (wilcoxon) | -5.67 | exploratory (uncorrected) |
| full minus b4 | tokens | 50 | -29379.190 [-33256.092, -25355.336] | 0.0000 (wilcoxon) | -2.07 | exploratory (uncorrected) |
| full minus b4 | unsupported_fact_rate | 50 | +0.052 [-0.004, +0.114] | 0.1549 (wilcoxon) | 0.25 | F-RQ1-halluc: not rejected |
| full minus b6 | factor_f1 | 8 | -0.562 [-0.958, -0.021] | 0.1250 (wilcoxon) | -0.75 | F-RQ1-guard: not rejected |
| full minus b6 | factor_hits_pooled (McNemar, cluster bootstrap) | 8 | -0.625 [-1.000, -0.125] | 0.1250 (mcnemar exact (items)) | 0.17 | exploratory (uncorrected) |
| full minus b6 | factor_precision_lenient | 6 | -0.222 [-0.583, +0.056] | 0.5000 (wilcoxon) | -0.50 | F-RQ1-guard: not rejected |
| full minus b6 | factor_recall | 8 | -0.625 [-1.000, -0.125] | 0.1250 (wilcoxon) | -0.84 | exploratory (uncorrected) |
| full minus b6 | objection_recall | 20 | +0.688 [+0.500, +0.863] | 0.0003 (wilcoxon) | 1.58 | exploratory (uncorrected) |
| full minus b6 | pass_per_case (McNemar) | 8 | -0.625 | 0.1250 (mcnemar exact) | 0.17 | exploratory (uncorrected) |
| full minus b6 | recall_at_10 | 0 | too few cases |  |  |  |
| full minus b6 | store_calls | 50 | +101.830 [+98.800, +104.580] | 0.0000 (wilcoxon) | 9.73 | exploratory (uncorrected) |
| full minus b6 | tokens | 50 | +101860.030 [+96914.999, +106871.670] | 0.0000 (wilcoxon) | 5.55 | exploratory (uncorrected) |
| full minus b6 | unsupported_fact_rate | 50 | -0.120 [-0.171, -0.072] | 0.0000 (wilcoxon) | -0.66 | exploratory (uncorrected) |

- Difference is full minus the comparator; for the unsupported-fact rate, tokens and store calls lower is better. Binary rows: exact McNemar on discordant pairs; pooled factor hits: cluster bootstrap over cases. n is the number of paired cases; for the unsupported-fact rate only cases where both systems made claims are paired. Holm only inside the registered primary families (plan 5.3), on this gold; everything else is exploratory.
