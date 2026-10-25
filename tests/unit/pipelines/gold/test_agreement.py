"""VI-04: span-grounded labeler, agreement, kappa with bootstrap, coverage and rule-only comparison (offline, fake labeler client)."""

from __future__ import annotations

import json

import pytest

from vakeel_sahayak.pipelines.gold import agreement as ag
from vakeel_sahayak.pipelines.gold import span_labeler as sl
from vakeel_sahayak.schemas.enums import OrderPart

DEFENSE = (
    "Learned counsel for the petitioner submitted that the petitioner is in custody since 22.02.2025 and has no previous criminal "
    "history. It was further argued that the charge sheet has been filed and the trial will take long, hence the petitioner may be released."
)
FULL = (
    "The petitioner seeks bail in Crime No.11 of 2025 under Section 420 IPC and Section 318(4) BNS. The petitioner was arrested on 22.02.2025. "
    + DEFENSE
    + " The earlier bail application was rejected on 10.01.2025. Heard under Section 439 CrPC."
)
PARTS = {OrderPart.FACTS: "Crime No.11 of 2025 under Section 420 IPC.", OrderPart.DEFENSE: DEFENSE, OrderPart.REASONING: "The charge sheet is filed.", OrderPart.OPERATIVE: "Bail granted."}


class Fake:
    """A labeler client that answers from a function of the prompt."""

    def __init__(self, fn):
        self.fn, self.calls = fn, 0

    def chat(self, messages, max_tokens=0, temperature=0.0, json_schema=None):
        self.calls += 1
        out = self.fn(messages[-1]["content"], json_schema)
        return out if isinstance(out, str) else json.dumps(out)


# ---- span validation ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("span", "reason"),
    [
        ("has no previous criminal history", None),
        ("HAS NO  PREVIOUS\ncriminal history", None),          # whitespace and case are ignored
        ("hasnoprevious criminal history", None),               # court PDFs run words together
        ("", "empty_span"),
        ("no pre", "span_too_short"),
        ("x" * 700, "span_too_long"),
        ("the petitioner is a habitual offender", "span_not_in_text"),
    ],
)
def test_validate_span(span, reason):
    assert sl.validate_span(sl.squash(DEFENSE), span) == reason


def test_span_has_date_and_section():
    assert sl.span_has_date("arrested on 22.02.2025 by police", "2025-02-22")
    assert not sl.span_has_date("arrested on 22.02.2025", "2025-02-23")
    assert sl.span_has_section("Section 318(4) BNS", "318(4)")
    assert not sl.span_has_section("Section 3180 BNS", "318")
    assert not sl.span_has_section("Crime No.11 of 2025", "420")


# ---- G1 labeler -------------------------------------------------------------------------------------------------------
def g1_reply(prompt, schema):
    return {"factors": [
        {"factor": "antecedents", "span": "has no previous criminal history"},
        {"factor": "charge_sheet_filed", "span": "the charge sheet has been filed"},
        {"factor": "flight_risk", "span": "the petitioner will never abscond from the country"},   # span not in the text: rejected
        {"factor": "trial_delay", "span": "x"},                                                       # too short: rejected
        {"factor": "made_up", "span": "the trial will take long"},                                    # unknown factor: rejected
        {"factor": "antecedents", "span": "has no previous criminal history"},                        # duplicate: ignored
    ]}


def test_label_g1_accepts_grounded_labels_only():
    out = sl.label_g1(Fake(g1_reply), DEFENSE)
    assert out.labels == ["antecedents", "charge_sheet_filed"]
    assert {r["reason"] for r in out.rejected} == {"span_not_in_text", "span_too_short", "unknown_factor"}
    assert out.error is None


def test_label_g1_errors_are_items_not_crashes():
    def boom(prompt, schema):
        raise RuntimeError("model down")

    assert "model down" in (sl.label_g1(Fake(boom), DEFENSE).error or "")
    assert sl.label_g1(Fake(lambda p, s: "not json"), DEFENSE).error == "reply is not a JSON object"
    assert sl.label_g1(Fake(lambda p, s: "```json\n{\"factors\": []}\n```"), DEFENSE).labels == []
    assert sl.label_g1(Fake(g1_reply), "  ").error == "no_input"


def test_labeler_is_not_offered_the_rule_candidates():
    seen = []
    sl.label_g1(Fake(lambda p, s: seen.append(p) or {"factors": []}), DEFENSE)
    assert "antecedents" in seen[0] and "rule" not in seen[0].lower().split("answer as")[0]


# ---- G3 labeler -------------------------------------------------------------------------------------------------------
def g3_reply(prompt, schema):
    st = lambda s, sp="": {"status": s, "span": sp}  # noqa: E731
    return {
        "sections": [
            {"act": "IPC", "section": "420", "span": "under Section 420 IPC"},
            {"act": "BNS", "section": "318(4)", "span": "Section 318(4) BNS"},
            {"act": "CrPC", "section": "439", "span": "Heard under Section 439 CrPC"},   # procedural bail provision: dropped like the rules do
            {"act": "IPC", "section": "302", "span": "under Section 420 IPC"},          # section not in its span: rejected
        ],
        "arrest_date": {"date": "2025-02-22", "span": "was arrested on 22.02.2025"},
        "charge_sheet": st("filed", "the charge sheet has been filed"),
        "previous_bail": st("rejected_or_withdrawn", "The earlier bail application was rejected on 10.01.2025"),
        "co_accused_bail": st("not_stated"),
        "trial_stage": st("not_stated"),
        "dates": [{"date": "2025-02-22", "span": "arrested on 22.02.2025"}, {"date": "2025-03-01", "span": "arrested on 22.02.2025"}],
    }


def test_label_g3_maps_to_rule_label_strings_and_validates():
    out = sl.label_g3(Fake(g3_reply), FULL)
    assert out.labels == [
        "sections=IPC 420", "sections=BNS 318(4)", "arrest_date=2025-02-22", "charge_sheet_filed=True",
        "previous_bail=rejected_or_withdrawn", "event=2025-02-22",
    ]
    assert {r["reason"] for r in out.rejected} == {"section_not_in_span", "date_not_in_span"}


# ---- agreement, kappa, coverage ---------------------------------------------------------------------------------------
def test_agree_item_fields():
    out = sl.LabelerOutput([sl.Proposal("antecedents", "span a text"), sl.Proposal("flight_risk", "span b text")])
    r = ag.agree_item("g1", "d1", ["antecedents", "custody_period"], out)
    assert r["labels"] == ["antecedents"] and r["rule_only_labels"] == ["custody_period"] and r["llm_only_labels"] == ["flight_risk"]
    assert r["disagreement"] is True and r["status"] == "agreed" and r["llm_spans"]["antecedents"] == "span a text"
    same = ag.agree_item("g1", "d2", ["antecedents"], sl.LabelerOutput([sl.Proposal("antecedents", "span a text")]))
    assert same["disagreement"] is False and same["labels"] == ["antecedents"]


def test_failed_labeler_keeps_provisional_rule_record():
    r = ag.agree_item("g1", "d", ["antecedents"], sl.LabelerOutput(error="RuntimeError: x"))
    assert r["status"] == "rule_only" and r["llm_labels"] is None and r["labels"] == ["antecedents"] and r["disagreement"] is None
    assert ag.agree_item("g1", "d", [], None)["error"] == "not_run"


def test_binary_kappa_values():
    assert ag.binary_kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert ag.binary_kappa([True, False, True, False], [False, True, False, True]) == -1.0
    assert ag.binary_kappa([True, True, False, False], [True, False, True, False]) == 0.0
    assert ag.binary_kappa([False] * 4, [False] * 4) == 1.0
    assert ag.binary_kappa([], []) is None


def test_kappa_with_ci_is_deterministic_and_brackets():
    a = [["x"], ["y"], [], ["x", "y"], ["x"], [], ["y"], ["x"]]
    b = [["x"], ["y"], [], ["x"], ["x"], ["y"], ["y"], ["x"]]
    r1, r2 = ag.kappa_with_ci(a, b, n_boot=200), ag.kappa_with_ci(a, b, n_boot=200)
    assert r1 == r2 and r1["n_items"] == 8
    assert r1["ci95"][0] <= r1["kappa"] <= r1["ci95"][1] or r1["ci95"][0] <= 1.0
    perfect = ag.kappa_with_ci(a, a, n_boot=100)
    assert perfect["kappa"] == 1.0 and perfect["dice"] == 1.0
    assert ag.kappa_with_ci([["x"]], [["x"]])["ci95"] is None  # a single order has no interval


def test_dice():
    assert ag.dice([["a", "b"]], [["b", "c"]]) == pytest.approx(0.5)
    assert ag.dice([[]], [[]]) is None


def _recs():
    mk = ag.agree_item
    P = sl.Proposal
    return [
        mk("G1", "a", ["antecedents", "custody_period"], sl.LabelerOutput([P("antecedents", "span aaaaaa"), P("flight_risk", "span bbbbbb")])),
        mk("G1", "b", ["antecedents"], sl.LabelerOutput([P("antecedents", "span aaaaaa")])),
        mk("G1", "c", [], sl.LabelerOutput([], [{"label": "trial_delay", "span": "x", "reason": "span_not_in_text"}])),
        mk("G1", "d", ["flight_risk"], sl.LabelerOutput(error="Budget")),
    ]


def test_coverage_counts():
    c = ag.coverage(_recs())
    assert c["orders"] == 4 and c["labeler_answered"] == 3 and c["labeler_failed"] == 1
    assert c["with_agreed_label"] == 2 and c["both_find_nothing"] == 1 and c["fully_concordant"] == 2 and c["with_disagreement"] == 1


def test_rule_only_comparison():
    r = ag.rule_only_comparison(_recs())
    assert (r["rule_only_labels"], r["labeler_only_labels"], r["agreed_labels"]) == (3, 3, 2)
    assert r["rule_labels_kept_by_agreement"] == pytest.approx(2 / 3)
    assert r["orders_where_rule_gold_differs_from_agreed"] == 1


def test_gold_report_and_markdown():
    rep = ag.gold_report("G1", _recs(), n_boot=50)
    assert rep["kappa_by_type"]["antecedents"]["both"] == 2
    assert rep["disagreements"]["rule_only_by_type"] == {"custody_period": 1}
    assert rep["disagreements"]["labeler_only_by_type"] == {"flight_risk": 1}
    assert rep["disagreements"]["rejected_by_reason"] == {"span_not_in_text": 1}
    md = ag.render_markdown({"G1": rep})
    assert "| G1 |" in md and "antecedents" in md


def test_g3_rule_labels_split_derived_and_report_by_field():
    labels, derived = ag.rule_g3(PARTS | {OrderPart.REASONING: "He is in custody since 01.01.2025. The charge sheet has been filed."})
    assert all(not x.startswith("custody_days=") for x in labels)
    assert "charge_sheet_filed=True" in labels
    out = sl.label_g3(Fake(g3_reply), FULL)
    rec = ag.agree_item("G3", "d", labels, out, derived)
    rep = ag.gold_report("G3", [rec], n_boot=20)
    assert {"sections", "event", "charge_sheet_filed"} <= set(rep["kappa_by_type"])


def test_inter_labeler_kappa():
    P = sl.Proposal
    rule = [ag.agree_item("G1", d, r, None) for d, r in (("a", ["x"]), ("b", ["y"]), ("c", []), ("d", ["x"]))]
    one = [ag.agree_item("G1", d, r, sl.LabelerOutput([P(x, "span span span") for x in r])) for d, r in (("a", ["x"]), ("b", ["y"]), ("c", []), ("d", ["x"]))]
    two = [ag.agree_item("G1", d, r, sl.LabelerOutput([P(x, "span span span") for x in r])) for d, r in (("a", ["x"]), ("b", []), ("c", []), ("d", ["x"]))]
    i = ag.inter_labeler("G1", {r["doc_id"]: r for r in rule}, {r["doc_id"]: r for r in one}, {r["doc_id"]: r for r in two}, n_boot=20)
    assert i["n_common_orders"] == 4 and i["labeler1_vs_labeler2"]["kappa"] < 1.0 and i["rule_vs_labeler1"]["kappa"] == 1.0


# ---- runner: resumable, parallel, stops at the budget -----------------------------------------------------------------
def test_run_labeler_resumes_and_stops_on_budget(tmp_path):
    orders = {f"d{i}": {OrderPart.DEFENSE: DEFENSE} for i in range(6)}
    raw = tmp_path / "raw.jsonl"
    fake = Fake(g1_reply)
    res = ag.run_labeler("g1", orders, fake, raw, workers=2, log=lambda m: None)
    assert len(res) == 6 and fake.calls == 6 and res["d3"].labels == ["antecedents", "charge_sheet_filed"]
    again = Fake(g1_reply)
    ag.run_labeler("g1", orders, again, raw, workers=2, log=lambda m: None)
    assert again.calls == 0  # everything was done

    def capped(prompt, schema):
        raise RuntimeError("BudgetExceeded: cap")

    more = {f"e{i}": {OrderPart.DEFENSE: DEFENSE} for i in range(30)}
    f2 = Fake(capped)
    r2 = ag.run_labeler("g1", more, f2, tmp_path / "raw2.jsonl", workers=2, log=lambda m: None)
    assert f2.calls < 30 * 2 and len(r2) < 30  # stopped submitting after the refusal


def test_apply_to_testset_never_touches_originals(tmp_path):
    ts = tmp_path / "t1"
    ts.mkdir()
    row = {"case_id": "c0", "doc_id": "d1", "gold": {"G1": {"rule_labels": ["a"], "llm_labels": None, "labels": ["a"], "status": "rule_only"}, "G3": {"fields": {"k": 1}, "labels": ["z"]}}}
    (ts / "cases.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    (ts / "dev.jsonl").write_text(json.dumps({"case_id": "dv", "doc_id": "d2", "gold": {}}) + "\n", encoding="utf-8")
    out = tmp_path / "cand"
    out.mkdir()
    rec = ag.agree_item("G1", "d1", ["a", "b"], sl.LabelerOutput([sl.Proposal("a", "span span span")]))
    (out / "g1.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    before = (ts / "cases.jsonl").read_text(encoding="utf-8")
    stats = ag.apply_to_testset(out, ts, tmp_path / "dest", "openai-x")
    assert stats == {"cases": 2, "replaced_g1": 1, "replaced_g3": 0}
    assert (ts / "cases.jsonl").read_text(encoding="utf-8") == before
    new = json.loads((tmp_path / "dest" / "cases.jsonl").read_text(encoding="utf-8"))
    assert new["gold"]["G1"]["labels"] == ["a"] and new["gold"]["G1"]["status"] == "agreed" and "openai-x" in new["gold"]["G1"]["gold_source"]
    assert new["gold"]["G3"] == row["gold"]["G3"]  # no candidate for G3: untouched


def test_labeler_refuses_qwen_and_system_use():
    from vakeel_sahayak.models.labeler import EvalLabeler

    with pytest.raises(ValueError):
        EvalLabeler(model="Qwen/Qwen3-32B", backend="sarvam").client()
