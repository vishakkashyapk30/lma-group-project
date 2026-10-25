"""Feature evaluation F5: Court-ready application vs one-call application. Test set: T1, G3 dates, format rules. Metrics: section compliance; List of Dates precision/recall vs G3; dates without source; annexure index matches uploads (plan §15.6).

NOT RUN in VI-07 (the task covers F1 to F4, F7 and F8): the application builder is `export/application` and the export modules are stubs, so `run` raises NotImplementedError. `score` is implemented: it reads one arm's directory,
one JSON file per case with `required_sections_present`, `required_sections_total`, `lod_dates`, `gold_dates` (G3 dates), `dates_without_source`, `dates_total` and `annexure_matches_uploads`.
"""

from __future__ import annotations

import sys

from vakeel_sahayak.eval import feature_common as fc

ARMS = ("application", "one_call")


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F5 (system and comparison arms), resumable.

    Args:
        out_dir: results directory
        shard: this shard's index
        n_shards: the number of shards

    Raises:
        NotImplementedError: the export modules (the court-ready application and its List of Dates) are not built; F5 is outside VI-07's first scope.
    """
    raise NotImplementedError("F5 needs the export modules (the court-ready application with its List of Dates and annexure index); they are stubs, so no arm can run yet")


def score(run_dir: str) -> dict[str, float]:
    """Compute F5 metrics for one arm directory.

    Args:
        run_dir: an arm's directory (see the module docstring for the keys)

    Returns:
        `section_compliance` (required sections present over required, micro), `lod_precision` and `lod_recall` (List of Dates against the G3 dates, macro over cases with dates),
        `dates_without_source_rate` (micro), `annexure_match_rate` (share of cases whose annexure index matches the uploaded files).

    Raises:
        ValueError: the directory has no cases.
    """
    rows = fc.load_cases(run_dir)
    prf = [fc.set_prf(r.get("lod_dates", []), r.get("gold_dates", [])) for r in rows]
    out = {
        "section_compliance": fc.rate(sum(r["required_sections_present"] for r in rows), sum(r["required_sections_total"] for r in rows)),
        "lod_precision": fc.mean(p[1] for p in prf if p[1] is not None),
        "lod_recall": fc.mean(p[0] for p in prf if p[0] is not None),
        "dates_without_source_rate": fc.rate(sum(r["dates_without_source"] for r in rows), sum(r["dates_total"] for r in rows)),
        "annexure_match_rate": fc.mean(float(bool(r["annexure_matches_uploads"])) for r in rows if "annexure_matches_uploads" in r),
    }
    return fc.present(out)


if __name__ == "__main__":
    raise SystemExit(fc.cli(sys.modules[__name__]))
