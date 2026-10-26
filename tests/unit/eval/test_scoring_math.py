"""Scoring math on hand-computed examples (eval/scoring/case_metrics.py, stats_extra.py)."""

from __future__ import annotations

import math

import pytest

from tests.unit.eval.scoring_fixtures import ALL, gold_row, ground, record
from vakeel_sahayak.eval.scoring import case_metrics as cm
from vakeel_sahayak.eval.scoring import stats_extra as sx


def score(case, rec, cfg=None):
    pending: dict[str, str] = {}
    return cm.score_case(case, rec, {"models": {"llm_backend": "offline"}}, [], cfg or cm.ScoreConfig(), pending), pending


def test_recall_and_precision_hand_computed():
    case = gold_row("c1", g1=["custody_period", "charge_sheet_filed"], g5=["trial_delay"])
    # P = {custody_period, antecedents}: recall 1/2; strict precision 1/2; lenient (G1 u G5) precision 1/2; F1 = 0.5
    r, _ = score(case, record("c1", ["custody_period", "antecedents"]))
    assert r["factor_recall"] == pytest.approx(0.5)
    assert r["factor_precision_strict"] == pytest.approx(0.5)
    assert r["factor_precision_lenient"] == pytest.approx(0.5)
    assert r["factor_f1"] == pytest.approx(0.5)
    # P = {custody_period, trial_delay}: strict 1/2, lenient 2/2, recall 1/2, F1 = 2*0.5*1/1.5
    r, _ = score(case, record("c1", ["custody_period", "trial_delay"]))
    assert r["factor_precision_strict"] == pytest.approx(0.5)
    assert r["factor_precision_lenient"] == pytest.approx(1.0)
    assert r["factor_f1"] == pytest.approx(2 / 3)
    assert r["court_discussed_recall"] == pytest.approx(1.0)  # G5 = {trial_delay}, argued
    assert r["factor_items"] == [("custody_period", 1), ("charge_sheet_filed", 0)]


def test_unanswerable_factors_neither_help_nor_hurt():
    # antecedents is not answerable: arguing it does not lower precision, and a gold antecedents does not count as missed
    case = gold_row("c1", g1=["custody_period", "antecedents"], answerable=["custody_period", "charge_sheet_filed"])
    r, _ = score(case, record("c1", ["custody_period", "antecedents"]))
    assert r["factor_recall"] == 1.0 and r["factor_precision_strict"] == 1.0


def test_placeholder_and_not_applicable_grounds_are_not_argued():
    case = gold_row("c1", g1=["custody_period"])
    rec = record("c1", ["custody_period"])
    rec["brief"]["grounds"] = [ground("custody_period", argument="No supported argument could be drafted from the evidence for this factor: counsel to draft it."),
                               ground("antecedents", stance="not_applicable")]
    r, _ = score(case, rec)
    assert r["factor_recall"] == 0.0  # empty brief: recall 0 (null agent, plan 5.7), not undefined
    assert r["factor_precision_strict"] is None and r["factor_f1"] == 0.0
    assert cm.argued_factors(rec["brief"], ("favourable",)) == []


def test_undefined_is_none_not_zero():
    case = gold_row("c1", g1=[])  # no agreed factor: M1 undefined
    r, _ = score(case, record("c1", ["custody_period"]))
    assert r["factor_recall"] is None and r["factor_f1"] is None and r["passed"] is None
    assert r["recall_at_10"] is None and r["objection_recall"] is None


def test_recall_at_10_document_level_and_coverage_counts():
    case = gold_row("c1", g1=["custody_period"], g2=["D1", "D2"])
    r, _ = score(case, record("c1", ["custody_period"], retrieved=["D1#3", "D1#4", "X#1"]))
    assert r["recall_at_10"] == pytest.approx(0.5)  # D1 found once, D2 missed
    assert r["g2_gold_n"] == 2 and r["retrieved_source"] == "record"
    far = [f"X{i}" for i in range(10)] + ["D1", "D2"]
    r, _ = score(case, record("c1", ["custody_period"], retrieved=far))
    assert r["recall_at_10"] == 0.0  # gold beyond rank 10


def test_objection_recall_and_precision():
    case = gold_row("c1", g1=["custody_period"], g4=["gravity_and_punishment", "flight_risk"])
    r, _ = score(case, record("c1", ["custody_period"], objections=["gravity_and_punishment", "antecedents"]))
    assert r["objection_recall"] == pytest.approx(0.5) and r["objection_precision"] == pytest.approx(0.5)
    r, _ = score(case, record("c1", ["custody_period"]))  # did not spar
    assert r["objection_recall"] == 0.0 and r["objection_precision"] is None


def test_pass_flag_and_errors():
    case = gold_row("c1", g1=["custody_period"])
    ok, _ = score(case, record("c1", ["custody_period"]))
    bad, _ = score(case, record("c1", ["custody_period"], error="boom"))
    low, _ = score(case, record("c1", ["antecedents"]))
    assert ok["passed"] is True and bad["passed"] is False and low["passed"] is False


def test_coverage_baseline_cannot_decline():
    full = record("c1", ["custody_period"])
    full["brief"]["grounds"][0]["check"] = "NEEDS_REVIEW"
    assert cm.coverage_of(full) == 0.0
    base = record("c1", ["custody_period"], gates=False)
    base["brief"]["grounds"][0]["check"] = "NEEDS_REVIEW"
    assert cm.coverage_of(base) == 1.0  # no way to decline: one point on the curve
    assert cm.coverage_of({"brief": {"grounds": []}}) == 0.0


def test_unsupported_fact_stub_is_pending_and_strict_names_function(monkeypatch):
    import vakeel_sahayak.eval.metrics.unsupported_fact as uf

    def stub(brief, text):
        raise NotImplementedError

    monkeypatch.setattr(uf, "unsupported_fact_rate", stub)
    case = gold_row("c1", g1=["custody_period"])
    r, pending = score(case, record("c1", ["custody_period"]))
    assert r["unsupported_fact_rate"] is None and pending["unsupported_fact_rate"].endswith("unsupported_fact_rate")
    with pytest.raises(NotImplementedError, match="unsupported_fact_rate"):
        score(case, record("c1", ["custody_period"]), cm.ScoreConfig(strict=True))


def test_cost_only_priced_on_openai():
    cfg = cm.ScoreConfig(cost_per_token_usd=1e-5)
    assert cm.case_cost(1000, {"models": {"llm_backend": "offline"}}, cfg) == 0.0
    assert cm.case_cost(1000, {"models": {"llm_backend": "openai"}}, cfg) == pytest.approx(0.01)
    assert cm.case_cost(1000, {"models": {"llm_backend": "vllm"}}, cfg) is None


# ------------------------------------------------------------------------------------------------------------ stats_extra
def test_mcnemar_exact_hand_computed():
    m = sx.mcnemar_exact([True, True, False, False, True], [False, False, False, True, True])
    assert (m["b10"], m["b01"]) == (2, 1)
    assert m["p"] == pytest.approx(1.0)  # n=3, k=1: 2 * (1+3)/8 -> capped at 1
    m = sx.mcnemar_exact([True] * 5, [False] * 5)
    assert m["b10"] == 5 and m["b01"] == 0 and m["p"] == pytest.approx(2 / 32) and m["odds_ratio"] is None
    assert sx.mcnemar_exact([True, False], [True, False])["p"] == 1.0
    with pytest.raises(ValueError):
        sx.mcnemar_exact([True], [True, False])


def test_wilson_and_dz():
    p, lo, hi = sx.wilson_interval(0, 10)
    assert p == 0 and lo == 0 and 0.25 < hi < 0.31  # rule-of-three territory
    assert math.isnan(sx.wilson_interval(0, 0)[0])
    assert sx.cohens_dz([1.0, 1.0, 1.0]) is None
    assert sx.cohens_dz([1.0, 3.0]) == pytest.approx(2 / math.sqrt(2))


def test_cluster_bootstrap_keeps_items_together_and_is_seeded():
    a = [[1, 1], [1, 1], [0, 0], [1]]
    b = [[0, 0], [0, 0], [0, 0], [0]]
    d, lo, hi = sx.cluster_bootstrap_diff(a, b, n_boot=2000)
    assert d == pytest.approx(5 / 7) and lo <= d <= hi
    assert sx.cluster_bootstrap_diff(a, b, n_boot=2000) == (d, lo, hi)
    same, slo, shi = sx.cluster_bootstrap_diff([[1, 0]] * 4, [[1, 0]] * 4, n_boot=500)
    assert same == 0 and slo == 0 and shi == 0
    assert sx.cluster_bootstrap_diff([], [], n_boot=10) == (0.0, 0.0, 0.0)


def test_bootstrap_p_value_extremes():
    assert sx.bootstrap_p_value([0.0, 0.0, 0.0]) == 1.0
    assert sx.bootstrap_p_value([1.0] * 12, n_boot=1000) == pytest.approx(1 / 1000)


def test_all_factor_list_is_the_enum():
    from vakeel_sahayak.schemas.enums import Factor

    assert set(ALL) <= {f.value for f in Factor}
