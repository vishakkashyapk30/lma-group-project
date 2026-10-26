"""S4/S5 retrieval studies: the AUROC helper (M19), masking, the summary numbers by hand, and the study with a fake retriever (no store, no model)."""

from __future__ import annotations

import json

import pytest

from vakeel_sahayak.eval.metrics.retrieval import auroc
from vakeel_sahayak.eval.studies import run_study, s4s5


def test_auroc_hand_computed():
    assert auroc([0.9, 0.8, 0.3, 0.1], [True, True, False, False]) == 1.0
    assert auroc([0.1, 0.2, 0.8, 0.9], [True, True, False, False]) == 0.0
    # positives 0.8, 0.4; negatives 0.6, 0.2: pairs (0.8>0.6)(0.8>0.2)(0.4<0.6)(0.4>0.2) -> 3 of 4
    assert auroc([0.8, 0.4, 0.6, 0.2], [True, True, False, False]) == 0.75
    assert auroc([0.5, 0.5], [True, False]) == 0.5  # a tie counts one half
    assert auroc([0.5, 0.6], [True, True]) is None and auroc([], []) is None
    with pytest.raises(ValueError):
        auroc([1.0], [True, False])


def test_mask_citations_removes_case_names_and_reporters():
    t = "As held in Satender Kumar Antil v. CBI (2022) 10 SCC 51 and in AIR 1978 SC 597 the bail is the rule."
    m = s4s5.mask_citations(t)
    assert "Antil" not in m and "SCC" not in m and "AIR" not in m and "bail is the rule" in m


def result(gold, docs, edocs, gini, gap, weak=False):
    return {"gold": gold, "docs": docs, "edocs": edocs, "skew": {"gini": gini, "top_gap": gap, "weak": weak, "n": 10}}


RESULTS = [
    result(["G1"], ["a", "G1"], ["a", "G1"], 0.30, 0.20),                      # found plain and expanded
    result(["G2"], ["b", "c"], ["2010_INSC_1", "G2"], 0.10, 0.05, True),       # found only with expansion
    result(["G3", "G4"], ["G3", "d"], ["G3", "G4"], 0.25, 0.10),               # recall 0.5 plain, 1.0 expanded
    result(["G5"], ["e"], ["e"], 0.05, 0.01, True),                            # found in neither
]


def test_summarise_s5_and_s4_by_hand():
    s = s4s5.summarise(RESULTS, n_boot=200)
    s5, s4 = s["s5"], s["s4"]
    assert s5["recall_at_10_plain"] == pytest.approx((1 + 0 + 0.5 + 0) / 4) and s5["recall_at_10_expanded"] == pytest.approx((1 + 1 + 1 + 0) / 4)
    assert s5["diff"] == pytest.approx(0.375) and s5["hit_plain"] == 2 and s5["hit_expanded"] == 3
    assert (s5["discordant_expanded_only"], s5["discordant_plain_only"]) == (1, 0) and s5["mcnemar_p"] == 1.0
    assert s5["sc_share_plain"] == 0.0 and s5["sc_share_expanded"] == pytest.approx(0.125)  # one of the eight expanded top-10 docs (in case 2) is a Supreme Court judgment: 0.5 / 4
    # hits (top-10 has a gold doc): [T, F, T, F]; gini [.30, .10, .25, .05] -> positives .30, .25 above negatives .10, .05: AUROC 1.0
    assert s4["gini"]["auroc"] == 1.0 and s4["gini"]["n_positive"] == 2 and s4["gini"]["n_negative"] == 2
    assert s4["weak_flag"]["flagged"] == 2 and s4["weak_flag"]["precision_for_no_gold"] == 1.0 and s4["weak_flag"]["recall_for_no_gold"] == 1.0
    assert s4s5.summarise([])["n"] == 0


def test_run_with_a_fake_retriever_writes_both_sets(tmp_path):
    cases = {"g2": [{"id": f"c{i}", "query": "q", "gold": ["G"], "before": "2025-01-01"} for i in range(4)], "proxy": []}

    def fake(case):
        return {"docs": ["x", "G"], "edocs": ["G", "y"], "skew": {"gini": 0.2, "top_gap": 0.1, "weak": False, "n": 10}}

    res = run_study("s4s5", str(tmp_path / "o"), cases=cases, retrieve_fn=fake)
    assert res["sets"]["g2"]["n"] == 4 and res["sets"]["proxy"] == {"n": 0}
    s4 = res["sets"]["g2"]["s4"]["gini"]
    assert s4["auroc"] is None and s4["n_negative"] == 0  # every query has a hit: no negative, AUROC undefined, not 0.5
    md = (tmp_path / "o" / "s4s5.md").read_text(encoding="utf-8")
    assert "undefined" in md and "NOT G2" in md and "thin" in md
    json.loads((tmp_path / "o" / "s4s5.json").read_text(encoding="utf-8"))
