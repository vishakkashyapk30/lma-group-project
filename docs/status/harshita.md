# Status — Harshita

Assigned (owner's day-1 message §7): **metrics & statistics, the statutes, the Rights Radar verification, and the proposal PDF + README/QA docs.**

## Metrics & statistics  ← DONE (implemented 2026-10-26)
The code with failing unit tests encoding the spec. All of `tests/unit/eval/test_metrics.py` + `test_stats.py` now pass (**52 passed**, was 52 failed). `ruff` clean.

- **Statistics** (`eval/stats/`): `holm_bonferroni` (step-down, pure Python), `paired_bootstrap_ci` (seeded percentile CI, numpy), `wilcoxon_signed_rank` (scipy exact, 1.0 when all diffs zero).
- **Metrics** (`eval/metrics/`): `recall_at_k` + `slot_fill_rate` (retrieval), `factor_recall_precision` (answerable-only), `character_error_rate` (Levenshtein) + `boundary_f1` + `field_accuracy` (ingestion), `pass_hat_k` + `stale_claim_rate` (agentic), `map_section_accuracy` + `tool_call_accuracy` (tool-calling), `rights_accuracy` (rights), `export_violations` + `injection_success_rate` + `refusal_rate` + `leak_rate` (safety), `average_over_runs` (stats_helpers).
- **Dependency:** installed `numpy` + `scipy` into `.venv` (the full `.[eval]` extra pulls minicheck→torch, too heavy for this disk; only numpy/scipy are needed for the stats).
- **Left as a stub:** `eval/metrics/unsupported_fact.py` — no test references it, so not implemented (implementing untested code risks the wrong spec).

### HA-01 completed (2026-10-27, Harshita)
- Vishak's 2026-10-27 commit `f114bca` added the unsupported-fact rate, `validate_checker` and the ingestion helpers (`by_kind`, `escalation_rate`, `questions_asked`); his versions are kept.
- **Added here:** `mean_reciprocal_rank` and `ndcg_at_k` in `eval/metrics/retrieval.py` (document-level like `recall_at_k`; tests in `tests/unit/eval/test_ranking_metrics.py`), and the **null-agent audit** of plan 5.7 as a unit test (`tests/unit/eval/test_null_agent_audit.py`: empty brief, copy-the-facts, copy-the-checklist, argue-all-twelve, random citations, export without approval).
- **Audit finding (xfail, strict):** `unsupported_fact_rate` returns 0.0 for a brief with no sentences; plan 5.7 says "no claims", not 0. For Vishak; the test flips when it is fixed.
- **McNemar:** in Vishak's `eval/scoring/stats_extra.py` (`mcnemar_exact`); not duplicated into `eval/stats/`.
- Not covered: the all-stores-removed abstention check (needs a real run).
- Tests: `test_metrics`, `test_stats`, `test_null_agent_audit`, `test_ranking_metrics`: 62 passed, 1 xfailed; `ruff check src` clean.
- **Open for Vishak:** `tool_call_accuracy.args_valid` requires an exact match to gold args (plan says "argument validity"); `false_eligible_rate` divides by all checks; empty-input conventions (recall/precision 1.0, slot fill 0.0); MiniCheck threshold to fix on dev.

## Still to do (not yet started)
- **Statutes (HA-02):** the extraction was done by Vishak on 2026-10-26 (`scripts/extract_gap_statutes.py`, from official government PDFs; rows in the team data bundle under `data/gaps/statutes/`; see `data/README.md` "Gap-filling status"). Still missing (listed there): BNS/BNSS First Schedule flags, UAPA 43D(5) / PMLA 45 / BNS 318(4) text.

### HA-02 review (2026-10-27, Harshita)
- Installed the bundle (`RAW=0 make data-install`). Fixed `scripts/data_install.sh`: `sed -i` without a suffix fails on macOS (Vishak to review). The install's sanity check reports `gaps/: 14 files, manifest says 15` (about 4.6 KB missing, not one of the statute files); asked Vishak which file.
- **Rows load:** `StatuteStore().open()` returns all 10 CrPC sections (41, 41A, 50, 57, 167, 436, 436A, 437, 438, 439) and NDPS 19, 24, 27A, 31A, 37; IPC 352/533 rows carry First Schedule flags. Spot checks right: IPC 302, 379, 420 and NDPS 37 cognisable and non-bailable.
- **Tests:** `tests/unit/stores` + `tests/unit/tools_law_case` 221 passed.
- **Text vs PDF:** every row has `source_url` and `retrieved`; 85-100% of each row's 8-word windows occur verbatim in `pdftotext` of its source PDF. The misses are the script's documented edits (footnote markers such as `1[may, and shall,` in CrPC 436, joined lines and list items), not changed wording.
- **Rights Radar verification**: re-check the rule texts against the bare acts (review, not code).
- **Proposal PDF + README/QA docs**: writing.

*Note: this work was done by Shravani's session at the user's request; Harshita should review before it goes in under her task id.*
