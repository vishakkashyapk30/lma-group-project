"""M9, M13, M15, M16, M17, M18, M33, M35 (eval/metrics/citations.py): hand-computed numbers on a tiny brief, index and event log. No model, no data directory."""

from __future__ import annotations

import pytest

from vakeel_sahayak.eval.metrics import citations as ci

TEXT_D1 = "The petitioner has remained in custody for long; trial will take time."
TEXT_D2 = "It is well settled that bail is the rule and jail is the exception."
INDEX = ci.DictParagraphIndex({
    ("D1", 1): {"text": TEXT_D1, "part": "reasoning", "date": "2020-01-01", "court": "Supreme Court of India"},
    ("D2", 5): {"text": TEXT_D2, "part": "defense_submissions", "date": "2021-02-02", "court": "Delhi High Court"},
})
BRIEF = {"grounds": [
    {"id": "G1", "argument": "Custody is long [A:D1#1]. The court held “bail is the rule and jail is the exception” [A:D2#5]. Third sentence has no cite.",
     "authorities": [{"doc_id": "D1", "para": 1}, {"doc_id": "D3", "para": 9}]},
    {"id": "G2", "argument": "The court said “totally different invented words here” [A:D1#1].", "authorities": []},
]}


def fake_checker():
    def score(premise: str, hypothesis: str) -> float:
        h, p = hypothesis.lower(), premise.lower()
        return 1.0 if ("custody" in h and "custody" in p) or ("bail" in h and "bail" in p) else 0.0

    return ci.Checker("fake-checker", score, 0.5)


def test_extract_citations_inline_quote_and_authority_only():
    cites = ci.extract_citations(BRIEF)
    assert [(c.ground_id, c.doc_id, c.para, c.quote is not None, c.sentence is not None) for c in cites] == [
        ("G1", "D1", 1, False, True), ("G1", "D2", 5, True, True), ("G1", "D3", 9, False, False), ("G2", "D1", 1, True, True)]
    assert cites[1].quote == "bail is the rule and jail is the exception"
    assert ci.strip_markers("A [A:X#3]. B") == "A . B"


def test_quote_found_ignores_whitespace_and_splits_ellipses():
    assert ci.quote_found("bail is the   rule and jail", TEXT_D2)
    assert ci.quote_found("bail is the rule ... jail is the exception", TEXT_D2)
    assert not ci.quote_found("bail is the rule ... imprisonment is the exception", TEXT_D2)
    assert not ci.quote_found("short", TEXT_D2)  # fragments under 8 characters prove nothing


def test_m9_fabricated_rate():
    r = ci.fabricated_citations(ci.extract_citations(BRIEF), INDEX)
    # D3#9 is not in the index; G2's quotation is not in D1#1; the other two are real: 2 of 4
    assert (r["n"], r["n_fabricated"], r["rate"]) == (4, 2, 0.5)
    assert sorted(i["reason"] for i in r["items"]) == ["not_in_index", "quote_not_found"]
    assert ci.fabricated_citations([], INDEX)["rate"] is None


def test_m13_authority_quality():
    r = ci.authority_quality(ci.extract_citations(BRIEF), INDEX, "2024-01-01")
    assert r["n"] == 2 and r["reasoning_share"] == 0.5 and r["sc_share"] == 0.5 and r["before_share"] == 1.0
    assert ci.authority_quality(ci.extract_citations(BRIEF), INDEX, "2020-06-01")["before_share"] == 0.5  # D2 (2021) is after the order
    assert ci.authority_quality([], INDEX, None)["reasoning_share"] is None


def test_m15_good_law_violation_and_known_share():
    treat = ci.DictTreatmentIndex({"D1": ("OVERRULED", True), "D2": ("OK", True)})
    r = ci.good_law(BRIEF, treat)
    # pairs (G1,D1) (G1,D2) (G1,D3) (G2,D1); D1 is overruled and neither ground warns: 2 violations; D1, D2, D1 known, D3 not: 3 of 4
    assert (r["n"], r["violations"], r["violation_rate"], r["known_share"]) == (4, 2, 0.5, 0.75)
    warned = {"grounds": [{**BRIEF["grounds"][0], "argument": BRIEF["grounds"][0]["argument"] + " Warning: D1 was overruled later."}, BRIEF["grounds"][1]]}
    assert ci.good_law(warned, treat)["violations"] == 1
    assert ci.good_law({"grounds": []}, treat)["violation_rate"] is None


def test_m16_precision_and_recall():
    r = ci.citation_precision_recall(BRIEF, INDEX, fake_checker())
    # citations: D1 (custody, supported), D2 (bail, supported), D3 (missing: unsupported), G2's D1 (no custody or bail word: unsupported) -> 2 of 4
    assert r["n_citations"] == 4 and r["precision"] == 0.5
    # authority-claim sentences: G1 s1, G1 s2, G2 s1 (the third sentence of G1 reports no court holding); two are backed by a supported citation
    assert r["n_claims"] == 3 and r["recall"] == pytest.approx(2 / 3)
    assert r["checker"] == "fake-checker" and r["stand_in"] is False
    assert ci.Checker("offline-lexical-nli", lambda p, h: 0.0, 0.5).stand_in is True


def test_m17_removal_change():
    block = {"claims": [
        {"ground_id": "G1", "doc_id": "D1", "para": 1, "original": "Custody is long [A:D1#1].", "redraft": "Custody is long."},  # same words once the marker is gone
        {"ground_id": "G2", "doc_id": "D2", "para": 5, "original": "Bail is the rule.", "redraft": "Liberty matters in every case."},
        {"ground_id": "G3", "doc_id": "D3", "para": 9, "original": "A claim.", "redraft": None},
    ]}
    r = ci.removal_change(block)
    assert (r["n"], r["changed"]) == (3, 2) and r["rate"] == pytest.approx(2 / 3)
    assert ci.removal_change({"claims": [block["claims"][1]]}, threshold=0.2)["changed"] == 1  # Jaccard 0 < 0.2
    assert ci.removal_change(None)["rate"] is None


def ev(kind, factor, rnd, **extra):
    return {"actor": "SUTRADHAR", "kind": "AGENT_MESSAGE", "outputs": {"type": kind, "factor": factor, "round": rnd, **extra}}


def test_m18_stopping_from_events():
    events = [
        ev("plan", "A", 1, steps=[1, 2, 3]), ev("assess", "A", 1, assessment={"s": "MISSING"}),
        ev("plan", "A", 2, steps=[1, 2]), ev("assess", "A", 2, assessment={"s": "FILLED"}),
        ev("plan", "A", 3, steps=[1, 2]), ev("assess", "A", 3, assessment={"s": "FILLED"}),
        ev("plan", "B", 1, steps=[1, 2]), ev("assess", "B", 1, assessment={"s": "WEAK (1 of 2)"}),
        {"actor": "VAKEEL", "kind": "AGENT_MESSAGE", "outputs": {"type": "plan", "factor": "Z", "round": 1, "steps": [1]}},  # not Sutradhar: ignored
    ]
    r = ci.stopping_quality(events)
    assert (r["calls"], r["over_calls"]) == (9, 2) and r["over_search_rate"] == pytest.approx(2 / 9)
    assert (r["factors"], r["unfinished"], r["unfinished_share"]) == (2, 1, 0.5)
    assert ci.stopping_quality([])["over_search_rate"] is None


CLAIMS = [{"emitted": True, "score": s, "cut": 0.5} for s in (0.9, 0.8, 0.4, 0.2)] + [{"emitted": False, "score": 0.95, "cut": 0.5}]


def test_m33_curve_and_aurc():
    r = ci.coverage_risk_curve(CLAIMS)
    assert r["n_claims"] == 5
    pts = {round(t, 3): (round(c, 4), round(k, 4)) for t, c, k in r["points"]}
    assert pts[0.0] == (0.8, 0.5) and pts[0.4] == (0.6, 0.3333) and pts[0.8] == (0.4, 0.0) and pts[0.9] == (0.2, 0.0)
    assert r["aurc"] == pytest.approx(0.2 * (1 / 3) / 2 + 0.2 * (1 / 3 + 0.5) / 2)  # 0.116667
    assert r["operating"] == {"tau": 0.5, "coverage": 0.4, "risk": 0.0}
    assert r["one_point"] == {"coverage": 0.8, "risk": 0.5}
    assert ci.coverage_risk_curve([])["aurc"] is None


def test_m35_confident_wrong_cells():
    def checker():
        return ci.Checker("fake", lambda p, h: 1.0 if "alpha" in h and "alpha" in p else 0.0, 0.5)

    sents = [{"check": "SUPPORTED", "sentence": s, "score": sc, "cut": 0.5} for s, sc in (("alpha one", 0.9), ("beta two", 0.9), ("alpha three", 0.2), ("beta four", 0.2))]
    sents.append({"check": "NEEDS_REVIEW", "sentence": "beta five", "score": 0.1, "cut": 0.5})  # declined: not an emitted claim
    r = ci.confident_wrong(sents, "alpha text of the rest of the order", checker())
    assert r["cells"] == {"FC": 1, "F_notC": 1, "notF_C": 1, "notF_notC": 1} and r["n"] == 4 and r["rate"] == 0.25
    assert ci.confident_wrong(sents, None, checker())["rate"] is None
    assert ci.confident_wrong(sents, "alpha", checker(), gate_pass=False)["n"] == 0


def test_sqlite_index_reads_keys_and_pieces(tmp_path):
    import json
    import sqlite3

    db = tmp_path / "caselaw"
    db.mkdir()
    con = sqlite3.connect(db / "reasoning.sqlite")
    con.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL)")
    for i, (k, text) in enumerate([("DOC#4", "first piece"), ("DOC#4.2", "second piece"), ("DOC#41", "other paragraph")]):
        con.execute("INSERT INTO items (id, key, payload) VALUES (?, ?, ?)", (i, k, json.dumps({"text": text, "part": "reasoning", "date": "2020-01-01", "court": "X"})))
    con.commit()
    con.close()
    idx = ci.SqliteParagraphIndex.from_config(tmp_path)
    assert idx.available()
    got = idx.get("DOC", 4)
    assert got["text"] == "first piece second piece" and got["part"] == "reasoning"  # DOC#41 is not a piece of DOC#4
    assert idx.get("DOC", 7) is None
    idx.close()
    assert not ci.SqliteParagraphIndex.from_config(tmp_path / "none").available()
