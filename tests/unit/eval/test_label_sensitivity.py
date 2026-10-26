"""M5 label-source sensitivity: M1 to M4 under rules-only, one-labeler, agreed and second-labeler gold, ranking stability, per-factor kappa (hand-computed)."""

from __future__ import annotations

import json

import pytest

from tests.unit.eval.scoring_fixtures import gold_row, record, write_run, write_t1
from vakeel_sahayak.eval import label_sensitivity as ls
from vakeel_sahayak.eval.scoring import case_metrics as cm
from vakeel_sahayak.eval.scoring import render
from vakeel_sahayak.eval.scoring.loader import discover_runs
from vakeel_sahayak.eval.scoring.pipeline import score_command


def row(case_id, rule, llm, agreed, g5=(None, None, None)):
    r = gold_row(case_id, agreed)
    r["gold"]["G1"].update(rule_labels=rule, llm_labels=llm, status="agreed")
    r5 = {"rule_labels": g5[0] or [], "llm_labels": g5[1] or [], "labels": g5[2] or [], "status": "agreed"}
    r["gold"]["G5"] = r5
    return r


CASE = row("d1", ["custody_period", "charge_sheet_filed"], ["custody_period", "trial_delay", "antecedents"], ["custody_period"], g5=([], ["flight_risk"], []))
REC = record("d1", ["custody_period", "trial_delay"])


def test_values_under_each_source_hand_computed():
    cfg = cm.ScoreConfig()
    agreed = ls.case_values(CASE, REC, "agreed", cfg)
    assert agreed["factor_recall"] == 1.0 and agreed["factor_precision_strict"] == 0.5
    rule = ls.case_values(CASE, REC, "rule", cfg)  # gold {custody, charge_sheet}: 1 of 2 found
    assert rule["factor_recall"] == 0.5 and rule["factor_precision_strict"] == 0.5
    lab = ls.case_values(CASE, REC, "labeler", cfg)  # gold {custody, trial_delay, antecedents}: 2 of 3; every argued factor is gold
    assert lab["factor_recall"] == pytest.approx(2 / 3) and lab["factor_precision_strict"] == 1.0
    assert lab["factor_precision_lenient"] == 1.0 and lab["court_discussed_recall"] == 0.0  # G5 {flight_risk} never argued
    assert lab["factor_f1"] == pytest.approx(0.8)  # 2 * (2/3) * 1 / (2/3 + 1)
    assert ls.case_values(CASE, REC, "labeler2", cfg) is None  # no second labeler given


def test_missing_source_columns_and_failed_labeler_drop_the_order():
    plain = gold_row("x", ["custody_period"])  # a fixture / rule-only gold: only `labels`
    assert ls.source_labels(plain, "G1", "agreed") == ["custody_period"]
    assert ls.source_labels(plain, "G1", "rule") is None and ls.source_labels(plain, "G1", "labeler") is None
    failed = row("y", ["custody_period"], [], [])
    failed["gold"]["G1"]["status"] = "rule_only"  # the labeler failed: rules exist, nothing else does
    assert ls.source_labels(failed, "G1", "rule") == ["custody_period"] and ls.source_labels(failed, "G1", "labeler") is None


def test_second_labeler_reads_raw_files(tmp_path):
    (tmp_path / "raw_sarvam-x_g1.jsonl").write_text(
        json.dumps({"doc_id": "DOC-d1", "accepted": [["custody_period", "span"], ["custody_period", "again"], ["flight_risk", "s"]], "rejected": [], "error": None}) + "\n"
        + json.dumps({"doc_id": "DOC-bad", "accepted": [], "error": "boom"}) + "\n", encoding="utf-8")
    sec = ls.load_second_labeler(tmp_path)
    assert sec == {"DOC-d1": ["custody_period", "flight_risk"]}
    v = ls.case_values(CASE, REC, "labeler2", cm.ScoreConfig(), sec)  # gold {custody, flight_risk}: recall 1/2, precision 1/2 (trial_delay is not gold)
    assert v["factor_recall"] == 0.5 and v["factor_precision_strict"] == 0.5 and v["court_discussed_recall"] is None
    assert ls.load_second_labeler(tmp_path / "none") == {}


def test_kappa_per_label_hand_computed():
    cases = [row(f"c{i}", ["custody_period"] if r else [], ["custody_period"] if lab else [], []) for i, (r, lab) in enumerate([(1, 1), (1, 0), (0, 0), (0, 0)])]
    k = ls.labeler_kappa(cases, "G1", "rule", "labeler")
    c = k["per_label"]["custody_period"]
    # rule [T,T,F,F], labeler [T,F,F,F]: po .75, pe .5*.25 + .5*.75 = .5, kappa .5
    assert (c["n_a"], c["n_b"], c["both"]) == (2, 1, 1) and c["kappa"] == pytest.approx(0.5)
    assert k["n_orders"] == 4 and k["pooled_kappa"] == pytest.approx(0.5)
    assert ls.binary_kappa([True, True], [True, True]) == 1.0 and ls.binary_kappa([], []) is None


@pytest.fixture()
def scored(tmp_path):
    root = tmp_path / "testsets"
    dev = [row("d1", ["custody_period", "charge_sheet_filed"], ["custody_period", "trial_delay"], ["custody_period"]),
           row("d2", ["custody_period"], ["custody_period", "antecedents"], ["custody_period"])]
    for src in ("agreed", "rule"):
        write_t1(root, src, dev if src == "agreed" else [gold_row(r["case_id"], r["gold"]["G1"]["rule_labels"]) for r in dev], [gold_row("t1", ["custody_period"])], ["t1"], [])
    runs = tmp_path / "runs"
    write_run(runs, "full", 1, [record("d1", ["custody_period", "trial_delay"]), record("d2", ["custody_period"])])
    write_run(runs, "b0", 1, [record("d1", ["charge_sheet_filed"], gates=False), record("d2", ["antecedents"], gates=False)])
    return root, runs, tmp_path / "out"


def test_pipeline_writes_block_and_report_table(scored):
    root, runs, out = scored
    res = score_command(str(runs), str(out), gold_source="both", testsets_dir=str(root))
    block = res["agreed"]["label_sensitivity"]
    assert res["rule"]["label_sensitivity"] is None  # the rule-only gold has a single label set
    full = {s: block["sources"][s]["systems"]["full"]["factor_recall"]["mean"] for s in ("rule", "labeler", "agreed")}
    # full: d1 recall rule 1/2, labeler 2/2, agreed 1/1; d2 recall rule 1/1, labeler 1/2, agreed 1/1
    assert full == {"rule": pytest.approx(0.75), "labeler": pytest.approx(0.75), "agreed": 1.0}
    assert block["ranking"]["agreed"][0] == "full" and block["sources"]["rule"]["same_ranking_as_agreed"] is True
    assert "G1 rule vs labeler" in block["kappa"]
    assert ls.run(str(out))["agreed.full.factor_recall"] == 1.0
    written = render.write_report(str(out))
    names = {p.rsplit("/", 1)[1] for p in written["tables"]}
    assert {"table_label_sensitivity.md", "table_label_kappa.csv"} <= names
    md = (out / "tables" / "table_label_sensitivity.md").read_text(encoding="utf-8")
    assert "keyword rules only" in md and "second labeler only" not in md
    assert len(discover_runs(runs)) == 2


def test_run_without_scores_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        ls.run(str(tmp_path))
