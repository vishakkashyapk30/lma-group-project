"""M6a (unsupported case-fact rate) is reported BESIDE the original unsupported-fact rate (M6) for every arm and baseline, never instead
of it (team to-do, 2 Nov 2026; docs/handoff/architecture-search-2026-11-01.md, X2).

The rule, per scorer output (one per_case CSV): the columns `unsupported_fact_rate`, `unsupported_case_fact_rate` and its count
`n_case_fact` are all present; every system (arm or baseline) has rows; a row with a case-fact sentence (`n_case_fact` > 0) has an M6a
value, and a row with a factual sentence (`n_claims` > 0) has an M6 value. A baseline that writes no `[F:]` markers has `n_case_fact` 0
and a blank M6a: that is M6a reported as undefined, with its count, which the rule allows; a missing column or a missing count is not.
The committed outputs are checked once the scorer emits M6a (`scoring.pipeline.CSV_COLUMNS`); until then that test is skipped with the
reason, and the rule itself is tested below on synthetic rows.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from vakeel_sahayak.eval.scoring.pipeline import CSV_COLUMNS

M6, M6A, COUNT = "unsupported_fact_rate", "unsupported_case_fact_rate", "n_case_fact"
RESULTS = Path(__file__).resolve().parents[3] / "docs" / "results"


def problems(rows: list[dict[str, str]], columns: list[str]) -> list[str]:
    """Every way the rows break the rule (empty when M6a is reported beside M6 for every system)."""
    missing = [c for c in (M6, M6A, COUNT) if c not in columns]
    if missing:
        return [f"column {c} missing" for c in missing]
    out = []
    systems = sorted({r["system"] for r in rows})
    if not systems:
        return ["no rows"]
    for s in systems:
        mine = [r for r in rows if r["system"] == s]
        for r in mine:
            if r.get(COUNT, "") == "":
                out.append(f"{s} {r['case_id']}: no {COUNT} beside M6a")
            elif float(r[COUNT]) > 0 and r.get(M6A, "") == "":
                out.append(f"{s} {r['case_id']}: case-fact sentences but no M6a")
            if float(r.get("n_claims") or 0) > 0 and r.get(M6, "") == "":
                out.append(f"{s} {r['case_id']}: factual sentences but no M6")
    return out


def _row(system, n_claims="3", m6="0.5", n_fact="1", m6a="0.0"):
    return {"system": system, "case_id": "t1dev-000", "n_claims": n_claims, M6: m6, COUNT: n_fact, M6A: m6a}


COLS = ["system", "case_id", "n_claims", M6, COUNT, M6A]


def test_both_metrics_for_every_system_pass():
    assert problems([_row("full"), _row("b0", n_fact="0", m6a="")], COLS) == []  # b0 writes no markers: M6a undefined, count 0


@pytest.mark.parametrize("drop", [M6, M6A, COUNT])
def test_a_missing_column_fails(drop):
    assert problems([_row("full")], [c for c in COLS if c != drop]) == [f"column {drop} missing"]


def test_a_row_without_its_value_fails():
    assert problems([_row("full", m6a="")], COLS) == ["full t1dev-000: case-fact sentences but no M6a"]
    assert problems([_row("b0", m6="")], COLS) == ["b0 t1dev-000: factual sentences but no M6"]
    assert problems([_row("b1", n_fact="")], COLS) == ["b1 t1dev-000: no n_case_fact beside M6a"]
    assert problems([], COLS) == ["no rows"]


def _outputs() -> list[Path]:
    return sorted(RESULTS.glob("**/per_case_*.csv"))


@pytest.mark.skipif(M6A not in CSV_COLUMNS, reason="the scorer does not emit M6a yet (eval/scoring/split_metric.py is on arch-search; "
                    "add unsupported_case_fact_rate and n_case_fact to engine.METRICS and rescore the stored outputs)")
@pytest.mark.parametrize("path", _outputs(), ids=lambda p: str(p.relative_to(RESULTS)))
def test_every_committed_scorer_output_reports_m6a_beside_m6(path):
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        columns = list(reader.fieldnames or [])
    assert problems(rows, columns) == []


def test_there_are_scorer_outputs_to_check():
    assert _outputs(), "no per_case CSV under docs/results"
