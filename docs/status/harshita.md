# Status — Harshita

Assigned (owner's day-1 message §7): **metrics & statistics, the statutes, the Rights Radar verification, and the proposal PDF + README/QA docs.**

## Metrics & statistics  ← DONE (implemented 2026-10-26)
The code with failing unit tests encoding the spec. All of `tests/unit/eval/test_metrics.py` + `test_stats.py` now pass (**52 passed**, was 52 failed). `ruff` clean.

- **Statistics** (`eval/stats/`): `holm_bonferroni` (step-down, pure Python), `paired_bootstrap_ci` (seeded percentile CI, numpy), `wilcoxon_signed_rank` (scipy exact, 1.0 when all diffs zero).
- **Metrics** (`eval/metrics/`): `recall_at_k` + `slot_fill_rate` (retrieval), `factor_recall_precision` (answerable-only), `character_error_rate` (Levenshtein) + `boundary_f1` + `field_accuracy` (ingestion), `pass_hat_k` + `stale_claim_rate` (agentic), `map_section_accuracy` + `tool_call_accuracy` (tool-calling), `rights_accuracy` (rights), `export_violations` + `injection_success_rate` + `refusal_rate` + `leak_rate` (safety), `average_over_runs` (stats_helpers).
- **Dependency:** installed `numpy` + `scipy` into `.venv` (the full `.[eval]` extra pulls minicheck→torch, too heavy for this disk; only numpy/scipy are needed for the stats).
- **Left as a stub:** `eval/metrics/unsupported_fact.py` — no test references it, so not implemented (implementing untested code risks the wrong spec).

## Still to do (not yet started)
- **Statutes** (CrPC 1973, NDPS s.37, First Schedule): the store-build wiring exists but the PDF text must be fetched by a person (India Code blocks scripted access) — see AGENTS.md / progress.md §0f. Data task, not code.
- **Rights Radar verification**: re-check the rule texts against the bare acts (review, not code).
- **Proposal PDF + README/QA docs**: writing.

*Note: this work was done by Shravani's session at the user's request; Harshita should review before it goes in under her task id.*
