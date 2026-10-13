# data/

Everything here except this README and the `.gitkeep` files is gitignored.

| Dir | Contents | Plan |
|---|---|---|
| `raw/` | Open India Law dumps, IPC2BNS-Verify, HLDC, Kathbath, e-SCR Hindi, public form layouts. Public data only. | §2 |
| `interim/` | Selected bail orders, split orders (facts / defense / prosecution / reasoning / operative), gold labels G1-G7, teacher dossiers, SFT data. | §5.2, §12, §15.1 |
| `stores/` | The seven shared stores (SQLite, LanceDB, networkx files). | §5 |
| `testsets/` | Constructed test sets T1-T9. | §15.2 |
| `cases/` | Per-case private data (laptop only): uploaded files, `case.docs`, `case.timeline`, `case.facts`, event log. | §3.3, §16 |

Rule: raw client files never leave the laptop. Only pseudonymised text may be copied to Ada. No manual annotation: every label comes from court text, official tables, existing datasets, construction or non-Qwen labeler consensus.
