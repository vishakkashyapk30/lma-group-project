"""No-claims handling in scoring (evaluation plan 5.7): an empty brief is 'no claims', not a perfect M6, and a silent system cannot win the table."""

from __future__ import annotations

import json

import pytest

from tests.unit.eval.scoring_fixtures import gold_row, ground, record, write_run, write_t1
from vakeel_sahayak.eval.metrics.unsupported_fact import unsupported_fact_counts, unsupported_fact_rate
from vakeel_sahayak.eval.scoring import case_metrics as cm
from vakeel_sahayak.eval.scoring import engine, render
from vakeel_sahayak.eval.scoring.pipeline import score_command
from vakeel_sahayak.schemas.bail_brief import BailBrief

CASES = ["d1", "d2", "d3", "d4"]


def _score(case, rec):
    return cm.score_case(case, rec, {"models": {"llm_backend": "offline"}}, [], cm.ScoreConfig(), {})


def test_empty_brief_is_none_and_zero_counts():
    brief = BailBrief(case_id="c", grounds=[])
    assert unsupported_fact_rate(brief, "facts") is None
    assert unsupported_fact_counts(brief, "facts") == (0, 0)


def test_case_row_for_empty_brief_has_no_rate_but_a_count_and_zero_coverage():
    empty = {"case_id": "c1", "brief": {"case_id": "c1", "grounds": []}, "gate1_approved": True}
    r = _score(gold_row("c1", ["custody_period"], answerable=["custody_period", "antecedents"]), empty)
    assert r["unsupported_fact_rate"] is None
    assert r["n_claims"] == 0.0 and r["unsupported_fact_count"] == 0.0
    assert r["answerable_coverage"] == 0.0


def test_hand_computed_claims_count_and_coverage():
    """Two grounds of one sentence each: 2 claims; the rate is count / 2; coverage is 1 of 4 answerable factors (the NEEDS_REVIEW ground does not count)."""
    rec = record("c1", [])
    rec["brief"]["grounds"] = [ground("custody_period", argument="He has been in custody for 400 days."),
                               ground("antecedents", check="NEEDS_REVIEW", argument="He has 9 prior cases.")]
    r = _score(gold_row("c1", ["custody_period"], answerable=["custody_period", "antecedents", "trial_delay", "flight_risk"]), rec)
    assert r["n_claims"] == 2.0
    assert r["unsupported_fact_rate"] == pytest.approx(r["unsupported_fact_count"] / 2)
    assert r["answerable_coverage"] == pytest.approx(0.25)


def _rec(case_id, factors):
    rec = record(case_id, [])
    rec["brief"]["grounds"] = [ground(f, argument=f"The applicant has been in custody for {i + 2} months already.") for i, f in enumerate(factors)]
    return rec


@pytest.fixture()
def scored(tmp_path):
    root = tmp_path / "testsets"
    for src in ("agreed", "rule"):
        write_t1(root, src, [gold_row(c, ["custody_period"], answerable=["custody_period", "antecedents"]) for c in CASES],
                 [gold_row("t1", ["custody_period"])], ["t1"], [])
    runs = tmp_path / "runs"
    write_run(runs, "full", 1, [_rec(c, ["custody_period", "antecedents"]) for c in CASES])
    # a null system: always an empty brief; and one that is silent on half the cases
    write_run(runs, "b0", 1, [record(c, []) for c in CASES])
    write_run(runs, "b1", 1, [_rec(c, ["custody_period"] if c in ("d1", "d2") else []) for c in CASES])
    out = tmp_path / "out"
    score_command(str(runs), str(out), testsets_dir=str(root))
    render.write_report(str(out))
    return out


def test_scoring_excludes_no_claim_cases_and_reports_n(scored):
    res = json.loads((scored / "score_agreed.json").read_text())
    full, null, half = (res["systems"][s]["metrics"] for s in ("full", "b0", "b1"))
    assert full["unsupported_fact_rate"]["n"] == 4 and full["unsupported_fact_rate"]["n_claims_cases"] == 4
    assert null["unsupported_fact_rate"]["n"] == 0 and null["unsupported_fact_rate"]["n_claims_cases"] == 0 and null["unsupported_fact_rate"]["n_cases"] == 4
    assert half["unsupported_fact_rate"]["n"] == 2 and half["unsupported_fact_rate"]["n_claims_cases"] == 2
    assert null["n_claims"]["mean"] == 0.0 and full["n_claims"]["mean"] == 2.0
    assert null["answerable_coverage"]["mean"] == 0.0 and full["answerable_coverage"]["mean"] == 1.0
    paired = {(p["comparator"], p["metric"]): p for p in res["paired"]}
    nulls = paired[("b0", "unsupported_fact_rate")]
    assert nulls["n"] == 0 and nulls["status"] == "no paired cases with claims"
    assert paired[("b1", "unsupported_fact_rate")]["n"] == 2  # only the cases where both made claims


def test_null_system_does_not_rank_first_on_the_headline_columns(scored):
    res = json.loads((scored / "score_agreed.json").read_text())
    sysm = {s: v["metrics"] for s, v in res["systems"].items()}
    for col in ("factor_recall", "answerable_coverage", "n_claims"):
        assert sysm["b0"][col]["mean"] is not None and sysm["b0"][col]["mean"] < sysm["full"][col]["mean"], col
    md = (scored / "tables" / "table1_main.md").read_text()
    assert "Cases with claims (M6)" in md and "Answerable-factor coverage" in md and "Unsupported sentences/case" in md
    assert "| b0 |" in md and "0 / 4" in md and "4 / 4" in md
    assert "Cases with no claims are excluded from M6 and counted in coverage" in md
    row = next(line for line in md.splitlines() if line.startswith("| b0 |"))
    assert "n/a (n=0)" in row  # the null system's M6 is not a number


def test_summary_block_counts_claim_cases():
    rows = [{"system": "s", "run": 1, "case_id": f"c{i}", "g2_gold_n": 0, "g2_raw_n": 0, "g2_unresolved_n": 0, "g4_n": 0, "g7_n": 0, "retrieved_source": "x",
             "tokens": 1.0, "unsupported_fact_rate": (0.5 if i == 0 else None), "n_claims": (2.0 if i == 0 else 0.0)} for i in range(3)]
    out = engine.summarise_systems(rows, [], 3, cm.ScoreConfig())["s"]["metrics"]["unsupported_fact_rate"]
    assert (out["n"], out["n_claims_cases"], out["n_cases"]) == (1, 1, 3)
