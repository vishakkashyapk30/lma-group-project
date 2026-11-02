"""docs/report/tools/win_loss_tie.py: the table that decides "beats every baseline on every metric" (team to-do, 2 Nov 2026)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from vakeel_sahayak.eval.scoring import engine

_TOOLS = Path(__file__).resolve().parents[3] / "docs" / "report" / "tools"
sys.path.insert(0, str(_TOOLS))
_spec = importlib.util.spec_from_file_location("win_loss_tie", _TOOLS / "win_loss_tie.py")
assert _spec and _spec.loader
wlt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wlt)


def _rows(system: str, values: list[float | None], metric: str = "coverage", errors: int = 0) -> list[dict]:
    return [{"system": system, "case_id": f"t1dev-{i:03d}", metric: "" if v is None else str(v), "n_errors": str(errors)} for i, v in enumerate(values)]


def test_directions_are_the_scorers_and_every_scorer_metric_is_placed():
    for key, (_, higher) in wlt.DECIDING.items():
        if key in engine.METRICS:
            assert engine.METRICS[key][1] == higher, key
    assert set(engine.METRICS) <= set(wlt.DECIDING) | wlt.DESCRIPTIVE
    assert not wlt.DESCRIPTIVE & set(wlt.DECIDING)


def test_m6a_decides_beside_m6_when_present():
    assert wlt.DECIDING["unsupported_case_fact_rate"][1] is False and "unsupported_fact_rate" in wlt.DECIDING


def test_holm_steps_down_and_stops_at_the_first_failure():
    out = wlt.holm({"a": 0.001, "b": 0.03, "c": 0.04})  # b > 0.05/2 stops the step-down, so c is kept although c <= 0.05
    assert out["a"] == (True, pytest.approx(0.05 / 3)) and out["b"][0] is False and out["c"][0] is False
    assert wlt.holm({"a": 0.01, "b": 0.02})["b"] == (True, 0.05)


def test_win_loss_tie_too_few_and_undefined():
    n = 30
    by = wlt.answered(
        _rows("full", [1.0] * n) + _rows("b0", [0.0] * n) + _rows("b1", [1.0] * n) + _rows("b2", [1.0] * 3 + [None] * (n - 3))
        + [{"system": "b3", "case_id": f"t1dev-{i:03d}", "coverage": "", "n_errors": "0"} for i in range(n)]
    )
    cells = {c["baseline"]: c for c in wlt.compare(by, ["full"], ["b0", "b1", "b2", "b3"], ["coverage"])}
    assert cells["b0"]["outcome"] == "win" and cells["b0"]["lo"] > 0
    assert cells["b1"]["outcome"] == "tie" and cells["b1"]["p"] == 1.0
    assert cells["b2"]["outcome"] == "too_few" and cells["b2"]["n"] == 3
    assert cells["b3"]["outcome"] == "undefined"
    lower = {c["baseline"]: c for c in wlt.compare(by, ["full"], ["b0"], ["fabricated_citation_rate"])}
    assert lower["b0"]["outcome"] == "undefined"


def test_lower_is_better_flips_the_sign_and_errored_cases_are_left_out():
    n = 20
    rows = _rows("full", [0.1] * n, "unsupported_fact_rate") + _rows("b0", [0.9] * n, "unsupported_fact_rate")
    rows += _rows("full", [0.9] * 5, "unsupported_fact_rate", errors=1)  # same case ids, but setdefault keeps the first answered row
    cell = wlt.compare(wlt.answered(rows), ["full"], ["b0"], ["unsupported_fact_rate"])[0]
    assert cell["outcome"] == "win" and cell["diff"] == pytest.approx(-0.8)
    loss = wlt.compare(wlt.answered(_rows("full", [0.9] * n, "unsupported_fact_rate") + _rows("b0", [0.1] * n, "unsupported_fact_rate")),
                       ["full"], ["b0"], ["unsupported_fact_rate"])[0]
    assert loss["outcome"] == "loss"


def test_interval_at_the_holm_level_excludes_zero_exactly_when_holm_rejects():
    import random

    rnd = random.Random(3)
    n = 25
    by = wlt.answered(_rows("full", [rnd.random() for _ in range(n)]) + _rows("b0", [rnd.random() for _ in range(n)])
                      + _rows("b1", [rnd.random() * 0.2 for _ in range(n)]))
    for c in wlt.compare(by, ["full"], ["b0", "b1"], ["coverage"]):
        assert (c["outcome"] != "tie") == (c["lo"] > 0 or c["hi"] < 0), c


def test_beats_all_needs_every_counted_cell_to_be_a_win():
    cells = [{"arm": "x", "baseline": "b0", "outcome": "win"}, {"arm": "x", "baseline": "b1", "outcome": "win"},
             {"arm": "x", "baseline": "b1", "outcome": "undefined"}, {"arm": "y", "baseline": "b0", "outcome": "win"},
             {"arm": "y", "baseline": "b1", "outcome": "too_few"}]
    v = wlt.verdicts(cells, ["x", "y"], ["b0", "b1"])
    assert v["x"]["beats_all"] is True and v["y"]["beats_all"] is False
    assert wlt.verdicts([{"arm": "z", "baseline": "b0", "outcome": "undefined"}], ["z"], ["b0"])["z"]["beats_all"] is False


def test_main_writes_the_table_and_the_csv(tmp_path):
    import csv

    src = tmp_path / "per_case.csv"
    rows = _rows("full", [1.0] * 10) + _rows("b0", [0.0] * 10)
    with src.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["system", "case_id", "coverage", "n_errors"])
        w.writeheader()
        w.writerows(rows)
    wlt.main([str(tmp_path / "gen"), str(tmp_path / "wlt"), f"fam={src}", "--cases", "t1dev-000..009"])
    tex = (tmp_path / "gen" / "wlt_fam.tex").read_text()
    assert "FULL & 1/0/0 & yes" in tex and r"\label{tab:wlt_fam}" in tex
    assert [r["outcome"] for r in csv.DictReader((tmp_path / "wlt" / "fam.csv").open())] == ["win"]


def test_parse_cases():
    assert wlt.parse_cases("t1dev-000..002") == {"t1dev-000", "t1dev-001", "t1dev-002"}
    assert wlt.parse_cases("t1dev-028..t1dev-029") == {"t1dev-028", "t1dev-029"}
    assert wlt.parse_cases(None) is None
