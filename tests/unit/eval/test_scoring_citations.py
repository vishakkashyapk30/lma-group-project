"""Scoring integration of the citation, abstention and stopping metrics: per-case values, pending reasons, the curve per system, report tables (hand-computed)."""

from __future__ import annotations

import json

import pytest

from tests.unit.eval.scoring_fixtures import gold_row, record, write_run, write_t1
from vakeel_sahayak.eval.metrics import citations as ci
from vakeel_sahayak.eval.scoring import case_metrics as cm
from vakeel_sahayak.eval.scoring import citation_scores, render
from vakeel_sahayak.eval.scoring.pipeline import score_command

PARA = "The petitioner has remained in custody for long and the trial will take time."
INDEX = ci.DictParagraphIndex({("D1", 1): {"text": PARA, "part": "reasoning", "date": "2020-01-01", "court": "Supreme Court of India"}})
CHECKER = ci.Checker("fake-checker", lambda p, h: 1.0 if "custody" in h.lower() and "custody" in p.lower() else 0.2, 0.5)
ENV = ci.ScoreEnv(paragraphs=INDEX, treatment=ci.DictTreatmentIndex({"D1": ("OVERRULED", True)}), checker=CHECKER,
                  rest_of_order=lambda doc: "The accused has spent long time in custody." if doc == "DOC-d1" else None)


def rec(case_id: str, arguments: list[str], gates: bool = True, **kw):
    r = record(case_id, ["custody_period"] * len(arguments), gates=gates, **kw)
    for g, a in zip(r["brief"]["grounds"], arguments, strict=True):
        g["argument"] = a
        g["id"] = f"G-{a[:4]}"
    return r


def test_case_values_hand_computed():
    case = gold_row("d1", ["custody_period"])
    r = rec("d1", ["He has been in custody for long [A:D1#1].", "A claim cites a missing paragraph [A:D9#3]."])
    pending: dict[str, str] = {}
    v = citation_scores.citation_values(case, r, [], ENV, pending)
    assert v["n_citations"] == 2 and v["fabricated_citation_rate"] == 0.5  # D9#3 is not in the index
    assert v["good_law_violation_rate"] == 0.5 and v["known_treatment_share"] == 0.5  # D1 overruled with no warning, D9 unknown
    assert v["citation_precision"] == 0.5  # only the D1 sentence mentions custody
    assert v["authority_reasoning_share"] == 1.0 and v["authority_sc_share"] == 1.0
    assert v["can_decline"] is True and len(v["claims"]) == 2 and not pending
    assert v["confident_wrong_rate"] is not None


def test_missing_resources_are_pending_only_when_there_is_something_to_measure():
    case = gold_row("d1", ["custody_period"])
    bare = ci.ScoreEnv(reasons={"paragraphs": "the paragraph stores are not present", "treatment": "the citation graph is not present", "rest_of_order": "no parts file"})
    pending: dict[str, str] = {}
    citation_scores.citation_values(case, record("d1", ["custody_period"]), [], bare, pending)
    assert set(pending) == {"confident_wrong_rate"}  # no citations: the store metrics have nothing to measure
    pending = {}
    v = citation_scores.citation_values(case, rec("d1", ["Claim [A:D1#1]."]), [], bare, pending)
    assert {"fabricated_citation_rate", "good_law_violation_rate", "citation_precision", "confident_wrong_rate"} <= set(pending)
    assert v["fabricated_citation_rate"] is None and pending["fabricated_citation_rate"] == "the paragraph stores are not present"
    with pytest.raises(NotImplementedError, match="paragraph stores"):
        citation_scores.citation_values(case, rec("d1", ["Claim [A:D1#1]."]), [], bare, {}, strict=True)


def test_removal_block_and_events_flow_into_the_row():
    case = gold_row("d1", ["custody_period"])
    r = record("d1", ["custody_period"])
    r["removal"] = {"claims": [{"original": "a b", "redraft": "a b"}, {"original": "a b", "redraft": "c d"}]}
    ev = [{"actor": "SUTRADHAR", "kind": "AGENT_MESSAGE", "outputs": {"type": "plan", "factor": "f", "round": 1, "steps": [1, 2]}},
          {"actor": "SUTRADHAR", "kind": "AGENT_MESSAGE", "outputs": {"type": "assess", "factor": "f", "round": 1, "assessment": {"s": "FILLED"}}}]
    v = citation_scores.citation_values(case, r, ev, ENV, {})
    assert v["citation_removal_change"] == 0.5 and v["over_search_rate"] == 0.0 and v["unfinished_factor_share"] == 0.0


@pytest.fixture()
def scored(tmp_path):
    root = tmp_path / "testsets"
    for src in ("agreed", "rule"):
        write_t1(root, src, [gold_row("d1", ["custody_period"]), gold_row("d2", ["custody_period"])], [gold_row("t1", ["custody_period"])], ["t1"], [])
    runs = tmp_path / "runs"
    write_run(runs, "full", 1, [rec("d1", ["He has been in custody for long [A:D1#1]."]), rec("d2", ["A claim cites a missing paragraph [A:D9#3]."])])
    write_run(runs, "b0", 1, [rec("d1", ["No citations here at all."], gates=False), rec("d2", ["Nothing cited either."], gates=False)])
    out = tmp_path / "out"
    cfg = cm.ScoreConfig(env=ENV)
    res = score_command(str(runs), str(out), gold_source="agreed", testsets_dir=str(root), cfg=cfg)["agreed"]
    return res, out


def test_system_summaries_curve_and_tables(scored):
    res, out = scored
    full, b0 = res["systems"]["full"], res["systems"]["b0"]
    assert full["metrics"]["fabricated_citation_rate"]["mean"] == 0.5 and full["metrics"]["fabricated_citation_rate"]["n"] == 2
    assert b0["metrics"]["fabricated_citation_rate"]["n"] == 0  # b0 cites nothing: undefined, not zero
    assert full["curve"]["can_decline"] is True and b0["curve"]["can_decline"] is False and b0["curve"]["aurc"] is None
    assert full["curve"]["n_claims"] == 2 and b0["curve"]["one_point"]["coverage"] == 1.0
    assert res["meta"]["checker"] == {"name": "fake-checker", "stand_in": False}
    render.write_report(str(out))
    md = (out / "tables" / "table_citations.md").read_text(encoding="utf-8")
    assert "Fabricated citations (M9)" in md and "0.500" in md and "fake-checker" in md
    ab = (out / "tables" / "table_abstention.md").read_text(encoding="utf-8")
    assert "one point (cannot decline)" in ab and "AURC" in ab
    assert (out / "figures" / "fig_coverage_risk.csv").is_file()
    per_case = json.loads((out / "score_agreed.json").read_text(encoding="utf-8"))["per_case"]
    assert any(r["system"] == "full" and r["fabricated_citation_rate"] == 0.0 for r in per_case)
