### Citations and authority quality (preliminary)

*Preliminary dev result: dev slice (50 orders; the n of each system is in the table), gold source agreed.*

| System | Fabricated citations (M9) | Court reasoning (M13) | Supreme Court (M13) | Dated before order (M13) | Good-law violations (M15) | Known treatment (M15) | Citation precision (M16) | Citation recall (M16) | Claims changed by removal (M17) |
|---|---|---|---|---|---|---|---|---|---|
| full | 0.000 [0.000, 0.000] n=38 | 1.000 [1.000, 1.000] n=38 | 0.044 [0.010, 0.086] n=38 | 1.000 [1.000, 1.000] n=38 | 0.000 [0.000, 0.000] n=38 | 0.003 [0.000, 0.010] n=38 | 0.790 [0.727, 0.849] n=38 | 0.778 [0.721, 0.833] n=38 | n/a (n=0) |
| b0 | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) |
| b1 | 0.000 [0.000, 0.000] n=1 | 1.000 [1.000, 1.000] n=1 | 0.000 [0.000, 0.000] n=1 | 1.000 [1.000, 1.000] n=1 | 0.000 [0.000, 0.000] n=1 | 0.000 [0.000, 0.000] n=1 | 0.000 [0.000, 0.000] n=1 | n/a (n=0) | n/a (n=0) |
| b4 | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) |
| b6 | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) |

- Support checker: minicheck-roberta-large.
- M9: share of citations whose paragraph is not in the index or whose quotation is not in it (whitespace removed). M15: overruled precedents cited without a warning; 'known treatment' is the share of cited precedents with at least one labelled citing treatment (unknown is not good). M16 precision: cited paragraph supports the citing sentence; recall: authority-claim sentences with a supported citation. M17 needs the `m17_removal` arm (a redraft without the cited paragraph) and is a lower bound; n/a (n=0) means the arm was not run.
- A system that cites nothing has no defined value (n counts the orders with at least one citation).
