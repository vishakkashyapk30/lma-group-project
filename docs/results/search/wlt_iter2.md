| arm | wins | ties | losses | too few | losses (metric: baselines) |
|---|---|---|---|---|---|
| full | 14 | 35 | 12 | 49 | unsupported_fact_rate: b0,b3,b4; unsupported_fact_count: b5; coverage: b6; over_search_rate: b5; unfinished_factor_share: b4,b5; confident_wrong_rate: b0,b3,b4,b6 |
| a7 | 4 | 51 | 3 | 44 | coverage: b1,b3,b6 |
| c14567 | 26 | 31 | 4 | 49 | unfinished_factor_share: b4,b5; confident_wrong_rate: b0,b4 |
| c1457 | 28 | 29 | 4 | 49 | unfinished_factor_share: b4,b5; confident_wrong_rate: b0,b4 |
| c457 | 27 | 25 | 9 | 49 | unsupported_fact_rate: b0,b4; over_search_rate: b5; unfinished_factor_share: b4,b5; confident_wrong_rate: b0,b3,b4,b6 |
| x1 | 14 | 41 | 6 | 49 | unsupported_fact_count: b2,b5; coverage: b6; unfinished_factor_share: b4,b5; confident_wrong_rate: b4 |
| x2 | 10 | 16 | 3 | 64 | coverage: b6; unfinished_factor_share: b4,b5 |
| x3 | 14 | 35 | 12 | 49 | unsupported_fact_rate: b0,b3,b4; unsupported_fact_count: b5; coverage: b6; over_search_rate: b5; unfinished_factor_share: b4,b5; confident_wrong_rate: b0,b3,b4,b6 |
| x4 | 21 | 31 | 9 | 49 | unsupported_fact_rate: b0,b4; over_search_rate: b5; unfinished_factor_share: b4,b5; confident_wrong_rate: b0,b3,b4,b6 |
| x5 | 13 | 44 | 4 | 49 | coverage: b6; unfinished_factor_share: b4,b5; confident_wrong_rate: b4 |
| x6 | 20 | 29 | 12 | 49 | unsupported_fact_rate: b0,b3,b4; unsupported_fact_count: b5; coverage: b6; over_search_rate: b5; unfinished_factor_share: b4,b5; confident_wrong_rate: b0,b3,b4,b6 |
| x7 | 22 | 27 | 12 | 49 | unsupported_fact_rate: b0,b3,b4; unsupported_fact_count: b5; coverage: b6; over_search_rate: b5; unfinished_factor_share: b4,b5; confident_wrong_rate: b0,b3,b4,b6 |

Outcome against each baseline (W win, T tie, L loss, f fewer than 5 paired cases, - undefined); Satvik's `docs/report/tools/win_loss_tie.py`: seeded paired bootstrap (10,000), Holm at 0.05 per (arm, metric) over the baselines, search cases t1dev-000..029.

#### full

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | 0.333 | f | f | f | f | f | f | f |
| factor_precision_strict | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_precision_lenient | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_f1 | 0.333 | f | f | f | f | f | f | f |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 1.000 | L +0.051 | T +0.057 | f | L +0.067 | L +0.042 | T +0.033 | T +0.030 |
| unsupported_case_fact_rate | 0.844 | - | - | - | - | T +0.038 | T +0.111 | - |
| unsupported_fact_count | 6.200 | T +2.240 | T -2.400 | T +3.200 | T -0.200 | W -9.033 | L +2.033 | T -0.700 |
| answerable_coverage | 0.389 | T +0.389 | T +0.071 | T +0.389 | T +0.357 | T +0.136 | T +0.212 | W +0.379 |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 0.300 | T +0.300 | T +0.333 | T +0.300 | T +0.333 | T +0.091 | T +0.000 | T +0.364 |
| objection_precision | 0.225 | - | - | - | - | T +0.172 | T -0.167 | - |
| coverage | 0.669 | W +0.429 | W +0.269 | W +0.509 | W +0.269 | W +0.568 | W +0.569 | L -0.357 |
| fabricated_citation_rate | 0.000 | - | f | f | f | W -0.933 | W -0.643 | - |
| authority_reasoning_share | 1.000 | - | f | - | f | f | f | - |
| authority_sc_share | 0.000 | - | f | - | f | f | f | - |
| authority_before_share | 1.000 | - | f | - | f | f | f | - |
| good_law_violation_rate | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| known_treatment_share | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| citation_precision | 0.867 | - | f | f | f | W +0.812 | W +0.766 | - |
| citation_recall | 0.818 | - | - | - | - | W +0.801 | W +0.748 | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.000 | - | - | - | - | f | L +0.056 | - |
| unfinished_factor_share | 0.174 | - | - | - | - | L +0.156 | L +0.168 | - |
| confident_wrong_rate | 1.000 | L +0.138 | T +0.066 | f | L +0.091 | L +0.709 | T +0.460 | L +0.094 |

#### a7

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | 0.333 | f | f | f | f | f | f | f |
| factor_precision_strict | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_precision_lenient | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_f1 | 0.333 | f | f | f | f | f | f | f |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 0.958 | T +0.010 | T +0.018 | f | T +0.028 | T +0.005 | T -0.004 | T -0.007 |
| unsupported_case_fact_rate | 0.583 | - | - | - | - | T -0.113 | T -0.042 | - |
| unsupported_fact_count | 4.720 | T +0.760 | T -4.300 | T +1.720 | T -2.100 | W -11.067 | T +0.000 | W -2.733 |
| answerable_coverage | 0.056 | T +0.056 | T -0.214 | T +0.056 | T +0.071 | T -0.076 | T +0.000 | T +0.167 |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 0.300 | T +0.300 | T +0.222 | T +0.300 | T +0.222 | T +0.091 | T +0.000 | T +0.364 |
| objection_precision | 0.361 | - | - | - | - | W +0.303 | T +0.000 | - |
| coverage | 0.041 | T -0.199 | L -0.365 | T -0.119 | L -0.365 | T -0.007 | T -0.007 | L -0.932 |
| fabricated_citation_rate | 0.500 | - | f | - | f | T -0.357 | T +0.000 | - |
| authority_reasoning_share | 1.000 | - | f | - | f | - | f | - |
| authority_sc_share | 0.000 | - | f | - | f | - | f | - |
| authority_before_share | 1.000 | - | f | - | f | - | f | - |
| good_law_violation_rate | 0.000 | - | f | - | f | T +0.000 | T +0.000 | - |
| known_treatment_share | 0.000 | - | f | - | f | T +0.000 | T +0.000 | - |
| citation_precision | 0.000 | - | f | - | f | T +0.143 | T +0.143 | - |
| citation_recall | 0.143 | - | - | - | - | T +0.143 | T +0.143 | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.000 | - | - | - | - | f | T +0.000 | - |
| unfinished_factor_share | 0.000 | - | - | - | - | T -0.050 | T +0.000 | - |
| confident_wrong_rate | 0.000 | - | f | f | f | T +0.018 | T -0.143 | W -0.465 |

#### c14567

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | 0.000 | f | f | f | f | f | f | f |
| factor_precision_strict | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_precision_lenient | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_f1 | 0.000 | f | f | f | f | f | f | f |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 0.976 | T +0.028 | T +0.021 | f | T +0.016 | T -0.044 | T -0.053 | T -0.056 |
| unsupported_case_fact_rate | 0.500 | - | - | - | - | W -0.280 | T -0.071 | - |
| unsupported_fact_count | 5.840 | T +1.880 | T -2.850 | T +2.840 | T -0.650 | W -9.767 | T +1.300 | T -1.433 |
| answerable_coverage | 0.444 | W +0.444 | T +0.143 | W +0.444 | T +0.429 | T +0.273 | W +0.348 | W +0.515 |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 1.000 | W +1.000 | W +1.000 | W +1.000 | W +1.000 | W +0.727 | W +0.636 | W +1.000 |
| objection_precision | 0.195 | - | - | - | - | W +0.148 | T -0.167 | - |
| coverage | 0.980 | W +0.740 | W +0.575 | W +0.820 | W +0.575 | W +0.881 | W +0.881 | T -0.044 |
| fabricated_citation_rate | 0.000 | - | f | f | f | W -0.931 | W -0.643 | - |
| authority_reasoning_share | 1.000 | - | f | - | f | f | f | - |
| authority_sc_share | 0.000 | - | f | - | f | f | f | - |
| authority_before_share | 1.000 | - | f | - | f | f | f | - |
| good_law_violation_rate | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| known_treatment_share | 0.000 | - | f | f | f | T +0.029 | T +0.024 | - |
| citation_precision | 0.844 | - | f | f | f | W +0.686 | W +0.685 | - |
| citation_recall | 0.704 | - | - | - | - | W +0.687 | W +0.697 | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.000 | - | - | - | - | f | T +0.011 | - |
| unfinished_factor_share | 0.446 | - | - | - | - | L +0.429 | L +0.438 | - |
| confident_wrong_rate | 0.976 | L +0.114 | T +0.050 | f | T +0.068 | L +0.585 | T +0.238 | T +0.011 |

#### c1457

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | 0.333 | f | f | f | f | f | f | f |
| factor_precision_strict | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_precision_lenient | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_f1 | 0.333 | f | f | f | f | f | f | f |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 0.976 | T +0.028 | T +0.021 | f | T +0.016 | T -0.052 | T -0.061 | T -0.064 |
| unsupported_case_fact_rate | 0.472 | - | - | - | - | W -0.292 | T -0.125 | - |
| unsupported_fact_count | 5.880 | T +1.920 | T -2.800 | T +2.880 | T -0.600 | W -9.733 | T +1.333 | T -1.400 |
| answerable_coverage | 0.556 | W +0.556 | T +0.286 | W +0.556 | W +0.571 | W +0.364 | W +0.439 | W +0.606 |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 1.000 | W +1.000 | W +1.000 | W +1.000 | W +1.000 | W +0.727 | W +0.636 | W +1.000 |
| objection_precision | 0.192 | - | - | - | - | W +0.145 | T -0.170 | - |
| coverage | 1.000 | W +0.760 | W +0.600 | W +0.840 | W +0.600 | W +0.897 | W +0.898 | T -0.028 |
| fabricated_citation_rate | 0.000 | - | f | f | f | W -0.931 | W -0.643 | - |
| authority_reasoning_share | 1.000 | - | f | - | f | f | f | - |
| authority_sc_share | 0.000 | - | f | - | f | f | f | - |
| authority_before_share | 1.000 | - | f | - | f | f | f | - |
| good_law_violation_rate | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| known_treatment_share | 0.000 | - | f | f | f | T +0.029 | T +0.024 | - |
| citation_precision | 0.844 | - | f | f | f | W +0.669 | W +0.613 | - |
| citation_recall | 0.704 | - | - | - | - | W +0.687 | W +0.697 | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.000 | - | - | - | - | f | T +0.024 | - |
| unfinished_factor_share | 0.381 | - | - | - | - | L +0.363 | L +0.375 | - |
| confident_wrong_rate | 0.976 | L +0.114 | T +0.050 | f | T +0.068 | L +0.567 | T +0.203 | T +0.003 |

#### c457

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | 0.333 | f | f | f | f | f | f | f |
| factor_precision_strict | 0.000 | - | f | f | f | T +0.071 | T +0.071 | f |
| factor_precision_lenient | 0.000 | - | f | f | f | T +0.071 | T +0.071 | f |
| factor_f1 | 0.333 | f | f | f | f | f | f | f |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 1.000 | L +0.051 | T +0.029 | f | T +0.039 | L +0.034 | T +0.025 | T +0.022 |
| unsupported_case_fact_rate | 0.400 | - | - | - | - | T -0.124 | T -0.100 | - |
| unsupported_fact_count | 3.960 | T +0.000 | T -4.700 | T +0.960 | T -2.500 | W -11.233 | T -0.167 | W -2.900 |
| answerable_coverage | 0.500 | W +0.500 | T +0.214 | W +0.500 | W +0.500 | T +0.288 | W +0.364 | W +0.530 |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 0.900 | W +0.900 | W +0.889 | W +0.900 | W +0.889 | W +0.636 | W +0.545 | W +0.909 |
| objection_precision | 0.182 | - | - | - | - | W +0.134 | T -0.183 | - |
| coverage | 1.000 | W +0.760 | W +0.600 | W +0.840 | W +0.600 | W +0.925 | W +0.926 | T +0.000 |
| fabricated_citation_rate | 0.000 | - | f | f | f | W -0.933 | W -0.643 | - |
| authority_reasoning_share | 1.000 | - | f | - | f | f | f | - |
| authority_sc_share | 0.000 | - | f | - | f | f | f | - |
| authority_before_share | 1.000 | - | f | - | f | f | f | - |
| good_law_violation_rate | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| known_treatment_share | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| citation_precision | 0.884 | - | f | f | f | W +0.869 | W +0.826 | - |
| citation_recall | 0.875 | - | - | - | - | W +0.859 | W +0.822 | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.000 | - | - | - | - | f | L +0.052 | - |
| unfinished_factor_share | 0.311 | - | - | - | - | L +0.294 | L +0.301 | - |
| confident_wrong_rate | 1.000 | L +0.138 | T +0.066 | f | L +0.091 | L +0.659 | T +0.396 | L +0.091 |

#### x1

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | 0.333 | f | f | f | f | f | f | f |
| factor_precision_strict | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_precision_lenient | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_f1 | 0.333 | f | f | f | f | f | f | f |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 0.935 | T -0.013 | T -0.013 | f | T -0.018 | T -0.047 | T -0.056 | T -0.059 |
| unsupported_case_fact_rate | 0.623 | - | - | - | - | T -0.199 | T +0.056 | - |
| unsupported_fact_count | 8.400 | T +4.440 | T -0.450 | L +5.400 | T +1.750 | W -7.467 | L +3.600 | T +0.867 |
| answerable_coverage | 0.444 | T +0.444 | T +0.143 | T +0.444 | T +0.429 | T +0.182 | T +0.258 | W +0.424 |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 0.000 | T +0.000 | T +0.000 | T +0.000 | T +0.000 | T -0.182 | T -0.273 | T +0.091 |
| objection_precision | 0.029 | - | - | - | - | T +0.011 | T -0.175 | - |
| coverage | 0.739 | W +0.499 | W +0.337 | W +0.579 | W +0.337 | W +0.649 | W +0.649 | L -0.276 |
| fabricated_citation_rate | 0.000 | - | f | f | f | W -0.926 | W -0.643 | - |
| authority_reasoning_share | 1.000 | - | f | - | f | f | f | - |
| authority_sc_share | 0.000 | - | f | - | f | f | f | - |
| authority_before_share | 1.000 | - | f | - | f | f | f | - |
| good_law_violation_rate | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| known_treatment_share | 0.000 | - | f | f | f | T +0.028 | T +0.020 | - |
| citation_precision | 0.762 | - | f | f | f | W +0.572 | W +0.504 | - |
| citation_recall | 0.603 | - | - | - | - | W +0.587 | W +0.524 | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.083 | - | - | - | - | f | T +0.025 | - |
| unfinished_factor_share | 0.336 | - | - | - | - | L +0.319 | L +0.332 | - |
| confident_wrong_rate | 0.889 | T +0.027 | T -0.014 | f | T +0.006 | L +0.593 | T +0.266 | T +0.016 |

#### x2

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | - | - | - | - | - | - | - | - |
| factor_precision_strict | 0.000 | - | f | f | f | f | f | f |
| factor_precision_lenient | 0.000 | - | f | f | f | f | f | f |
| factor_f1 | - | - | - | - | - | - | - | - |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 0.804 | f | T -0.147 | f | f | W -0.228 | W -0.247 | W -0.225 |
| unsupported_case_fact_rate | 0.445 | - | - | - | - | W -0.370 | f | - |
| unsupported_fact_count | 6.833 | T +2.333 | T -6.300 | T +3.583 | T +0.400 | W -9.267 | T +1.867 | T -1.200 |
| answerable_coverage | 0.167 | f | f | f | f | f | f | f |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 0.000 | f | f | f | f | f | f | f |
| objection_precision | 0.000 | - | - | - | - | f | f | - |
| coverage | 0.338 | T +0.004 | T -0.262 | T +0.171 | T -0.062 | W +0.320 | W +0.299 | L -0.602 |
| fabricated_citation_rate | 0.000 | - | f | f | f | W -1.000 | f | - |
| authority_reasoning_share | 1.000 | - | f | - | f | - | f | - |
| authority_sc_share | 0.000 | - | f | - | f | - | f | - |
| authority_before_share | 1.000 | - | f | - | f | - | f | - |
| good_law_violation_rate | 0.000 | - | f | f | f | T +0.000 | f | - |
| known_treatment_share | 0.000 | - | f | f | f | T +0.000 | f | - |
| citation_precision | 0.770 | - | f | f | f | W +0.795 | f | - |
| citation_recall | 0.791 | - | - | - | - | W +0.791 | f | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.000 | - | - | - | - | f | T +0.000 | - |
| unfinished_factor_share | 0.185 | - | - | - | - | L +0.149 | L +0.172 | - |
| confident_wrong_rate | 0.750 | f | f | f | f | T +0.303 | f | T -0.198 |

#### x3

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | 0.333 | f | f | f | f | f | f | f |
| factor_precision_strict | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_precision_lenient | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_f1 | 0.333 | f | f | f | f | f | f | f |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 1.000 | L +0.051 | T +0.057 | f | L +0.067 | L +0.042 | T +0.033 | T +0.030 |
| unsupported_case_fact_rate | 0.844 | - | - | - | - | T +0.038 | T +0.111 | - |
| unsupported_fact_count | 6.200 | T +2.240 | T -2.400 | T +3.200 | T -0.200 | W -9.033 | L +2.033 | T -0.700 |
| answerable_coverage | 0.389 | T +0.389 | T +0.071 | T +0.389 | T +0.357 | T +0.136 | T +0.212 | W +0.379 |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 0.300 | T +0.300 | T +0.333 | T +0.300 | T +0.333 | T +0.091 | T +0.000 | T +0.364 |
| objection_precision | 0.183 | - | - | - | - | T +0.131 | T -0.176 | - |
| coverage | 0.669 | W +0.429 | W +0.269 | W +0.509 | W +0.269 | W +0.568 | W +0.569 | L -0.357 |
| fabricated_citation_rate | 0.000 | - | f | f | f | W -0.933 | W -0.643 | - |
| authority_reasoning_share | 1.000 | - | f | - | f | f | f | - |
| authority_sc_share | 0.000 | - | f | - | f | f | f | - |
| authority_before_share | 1.000 | - | f | - | f | f | f | - |
| good_law_violation_rate | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| known_treatment_share | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| citation_precision | 0.867 | - | f | f | f | W +0.812 | W +0.766 | - |
| citation_recall | 0.818 | - | - | - | - | W +0.801 | W +0.748 | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.000 | - | - | - | - | f | L +0.056 | - |
| unfinished_factor_share | 0.174 | - | - | - | - | L +0.156 | L +0.168 | - |
| confident_wrong_rate | 1.000 | L +0.138 | T +0.066 | f | L +0.091 | L +0.709 | T +0.460 | L +0.094 |

#### x4

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | 0.333 | f | f | f | f | f | f | f |
| factor_precision_strict | 0.000 | - | f | f | f | T +0.071 | T +0.071 | f |
| factor_precision_lenient | 0.000 | - | f | f | f | T +0.071 | T +0.071 | f |
| factor_f1 | 0.333 | f | f | f | f | f | f | f |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 1.000 | L +0.051 | T +0.029 | f | T +0.039 | L +0.034 | T +0.025 | T +0.022 |
| unsupported_case_fact_rate | 0.400 | - | - | - | - | T -0.124 | T -0.100 | - |
| unsupported_fact_count | 3.960 | T +0.000 | T -4.700 | T +0.960 | T -2.500 | W -11.233 | T -0.167 | W -2.900 |
| answerable_coverage | 0.500 | W +0.500 | T +0.214 | W +0.500 | W +0.500 | T +0.288 | W +0.364 | W +0.530 |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 0.400 | T +0.400 | T +0.333 | T +0.400 | T +0.333 | T +0.182 | T +0.091 | W +0.455 |
| objection_precision | 0.476 | - | - | - | - | W +0.419 | T -0.069 | - |
| coverage | 1.000 | W +0.760 | W +0.600 | W +0.840 | W +0.600 | W +0.925 | W +0.926 | T +0.000 |
| fabricated_citation_rate | 0.000 | - | f | f | f | W -0.933 | W -0.643 | - |
| authority_reasoning_share | 1.000 | - | f | - | f | f | f | - |
| authority_sc_share | 0.000 | - | f | - | f | f | f | - |
| authority_before_share | 1.000 | - | f | - | f | f | f | - |
| good_law_violation_rate | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| known_treatment_share | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| citation_precision | 0.884 | - | f | f | f | W +0.869 | W +0.826 | - |
| citation_recall | 0.875 | - | - | - | - | W +0.859 | W +0.822 | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.000 | - | - | - | - | f | L +0.056 | - |
| unfinished_factor_share | 0.314 | - | - | - | - | L +0.297 | L +0.304 | - |
| confident_wrong_rate | 1.000 | L +0.138 | T +0.066 | f | L +0.091 | L +0.659 | T +0.396 | L +0.091 |

#### x5

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | 0.333 | f | f | f | f | f | f | f |
| factor_precision_strict | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_precision_lenient | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_f1 | 0.333 | f | f | f | f | f | f | f |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 0.827 | T -0.121 | T +0.001 | f | T -0.055 | T -0.058 | T -0.067 | W -0.070 |
| unsupported_case_fact_rate | 0.556 | - | - | - | - | W -0.251 | T +0.030 | - |
| unsupported_fact_count | 5.880 | T +1.920 | T -2.900 | T +2.880 | T -0.700 | W -9.667 | T +1.400 | T -1.333 |
| answerable_coverage | 0.333 | T +0.333 | T +0.000 | T +0.333 | T +0.286 | T +0.091 | T +0.167 | T +0.333 |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 0.200 | T +0.200 | T +0.111 | T +0.200 | T +0.111 | T +0.000 | T -0.091 | T +0.273 |
| objection_precision | 0.104 | - | - | - | - | T +0.054 | T -0.202 | - |
| coverage | 0.689 | W +0.449 | T +0.244 | W +0.529 | T +0.244 | W +0.602 | W +0.602 | L -0.323 |
| fabricated_citation_rate | 0.000 | - | f | f | f | W -0.933 | W -0.643 | - |
| authority_reasoning_share | 1.000 | - | f | - | f | f | f | - |
| authority_sc_share | 0.000 | - | f | - | f | f | f | - |
| authority_before_share | 1.000 | - | f | - | f | f | f | - |
| good_law_violation_rate | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| known_treatment_share | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| citation_precision | 0.606 | - | f | f | f | W +0.621 | W +0.603 | - |
| citation_recall | 0.645 | - | - | - | - | W +0.628 | W +0.601 | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.000 | - | - | - | - | f | T +0.017 | - |
| unfinished_factor_share | 0.248 | - | - | - | - | L +0.231 | L +0.248 | - |
| confident_wrong_rate | 0.764 | T -0.098 | T +0.032 | f | T -0.006 | L +0.502 | T +0.372 | T -0.004 |

#### x6

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | 0.333 | f | f | f | f | f | f | f |
| factor_precision_strict | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_precision_lenient | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_f1 | 0.333 | f | f | f | f | f | f | f |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 1.000 | L +0.051 | T +0.057 | f | L +0.067 | L +0.042 | T +0.033 | T +0.030 |
| unsupported_case_fact_rate | 0.844 | - | - | - | - | T +0.038 | T +0.111 | - |
| unsupported_fact_count | 6.200 | T +2.240 | T -2.400 | T +3.200 | T -0.200 | W -9.033 | L +2.033 | T -0.700 |
| answerable_coverage | 0.389 | T +0.389 | T +0.071 | T +0.389 | T +0.357 | T +0.136 | T +0.212 | W +0.379 |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 0.500 | W +0.500 | W +0.556 | W +0.500 | W +0.556 | T +0.273 | T +0.182 | W +0.545 |
| objection_precision | 0.315 | - | - | - | - | W +0.256 | T -0.115 | - |
| coverage | 0.669 | W +0.429 | W +0.269 | W +0.509 | W +0.269 | W +0.568 | W +0.569 | L -0.357 |
| fabricated_citation_rate | 0.000 | - | f | f | f | W -0.933 | W -0.643 | - |
| authority_reasoning_share | 1.000 | - | f | - | f | f | f | - |
| authority_sc_share | 0.000 | - | f | - | f | f | f | - |
| authority_before_share | 1.000 | - | f | - | f | f | f | - |
| good_law_violation_rate | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| known_treatment_share | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| citation_precision | 0.867 | - | f | f | f | W +0.812 | W +0.766 | - |
| citation_recall | 0.818 | - | - | - | - | W +0.801 | W +0.748 | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.000 | - | - | - | - | f | L +0.052 | - |
| unfinished_factor_share | 0.185 | - | - | - | - | L +0.168 | L +0.179 | - |
| confident_wrong_rate | 1.000 | L +0.138 | T +0.066 | f | L +0.091 | L +0.709 | T +0.460 | L +0.094 |

#### x7

| metric | arm mean | b0 | b1 | b2 | b3 | b4 | b5 | b6 |
|---|---|---|---|---|---|---|---|---|
| factor_recall | 0.333 | f | f | f | f | f | f | f |
| factor_precision_strict | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_precision_lenient | 0.000 | - | f | f | f | T +0.000 | T +0.000 | f |
| factor_f1 | 0.333 | f | f | f | f | f | f | f |
| court_discussed_recall | - | - | - | - | - | - | - | - |
| unsupported_fact_rate | 1.000 | L +0.051 | T +0.057 | f | L +0.067 | L +0.042 | T +0.033 | T +0.030 |
| unsupported_case_fact_rate | 0.844 | - | - | - | - | T +0.038 | T +0.111 | - |
| unsupported_fact_count | 6.200 | T +2.240 | T -2.400 | T +3.200 | T -0.200 | W -9.033 | L +2.033 | T -0.700 |
| answerable_coverage | 0.389 | T +0.389 | T +0.071 | T +0.389 | T +0.357 | T +0.136 | T +0.212 | W +0.379 |
| recall_at_10 | - | - | - | - | - | - | - | - |
| objection_recall | 1.000 | W +1.000 | W +1.000 | W +1.000 | W +1.000 | W +0.727 | W +0.636 | W +1.000 |
| objection_precision | 0.203 | - | - | - | - | W +0.155 | T -0.157 | - |
| coverage | 0.669 | W +0.429 | W +0.269 | W +0.509 | W +0.269 | W +0.568 | W +0.569 | L -0.357 |
| fabricated_citation_rate | 0.000 | - | f | f | f | W -0.933 | W -0.643 | - |
| authority_reasoning_share | 1.000 | - | f | - | f | f | f | - |
| authority_sc_share | 0.000 | - | f | - | f | f | f | - |
| authority_before_share | 1.000 | - | f | - | f | f | f | - |
| good_law_violation_rate | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| known_treatment_share | 0.000 | - | f | f | f | T +0.000 | T +0.000 | - |
| citation_precision | 0.867 | - | f | f | f | W +0.812 | W +0.766 | - |
| citation_recall | 0.818 | - | - | - | - | W +0.801 | W +0.748 | - |
| citation_removal_change | - | - | - | - | - | - | - | - |
| over_search_rate | 0.000 | - | - | - | - | f | L +0.056 | - |
| unfinished_factor_share | 0.109 | - | - | - | - | L +0.092 | L +0.106 | - |
| confident_wrong_rate | 1.000 | L +0.138 | T +0.066 | f | L +0.091 | L +0.709 | T +0.460 | L +0.094 |

