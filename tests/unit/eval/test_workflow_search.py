"""S13 workflow search harness (AFlow / ADAS style): enumeration, dev-only guard, budget caps, ranking, saved report, offline smoke."""

from __future__ import annotations

import json

import pytest

from tests.integration import _helpers as h
from vakeel_sahayak.eval.runners import workflow_search as ws
from vakeel_sahayak.orchestration.switches import Switches

FACTS = "The accused was arrested on 20.08.2024 under Section 318(4) BNS. Charge sheet filed 02.11.2024."
SMALL = {"stopping": ["rules", "rules_llm"], "topology": ["orchestrated", "sequential"], "store_prior": ["off", "order"]}


def fake_eval(switches, cases):
    """A score that depends on the switches only, so ranking is checkable."""
    score = (switches.stopping == "rules_llm") * 2 + (switches.topology == "sequential") + (switches.store_prior == "order") * 0.5
    return {"score": score, "tokens": 100 + (switches.topology == "sequential") * 10}


DEV = [{"case_id": "t1dev-000", "facts": "x", "before": "2024-02-16"}]


def test_switch_and_variant():
    assert "S13" in Switches.implemented_variants()
    assert Switches.for_variant("S13", stopping="llm", plan_cache=True).variant() == "custom"


def test_enumeration_is_deterministic_valid_and_complete():
    a, b = ws.enumerate_grid(SMALL), ws.enumerate_grid(SMALL)
    assert a == b and len(a) == 8 and a[0] == {"stopping": "rules", "topology": "orchestrated", "store_prior": "off"}
    assert all(ws.valid_point(p) is not None for p in ws.enumerate_grid())
    assert ws.enumerate_grid({"stopping": ["rules", "llm"], "fixed_router": [True]}) == [{"stopping": "rules", "fixed_router": True}]  # invalid combination left out
    with pytest.raises(ws.WorkflowSearchError):
        ws.enumerate_grid({"stopping": []})


def test_random_sample_is_seeded_and_distinct():
    a, b, c = ws.sample_grid(5, SMALL, seed=1), ws.sample_grid(5, SMALL, seed=1), ws.sample_grid(5, SMALL, seed=2)
    assert a == b and a != c and len({ws.config_key(p) for p in a}) == 5


def test_ranking_winner_and_saved_report(tmp_path):
    out = tmp_path / "report.json"
    report = ws.search(DEV, fake_eval, grid=SMALL, max_configs=8, report_path=out)
    scores = [r["score"] for r in report["ranking"]]
    assert scores == sorted(scores, reverse=True) and report["winner"] == {"stopping": "rules_llm", "topology": "sequential", "store_prior": "order"}
    assert [r["rank"] for r in report["ranking"]] == list(range(1, 9)) and report["test"] == "pending" and report["stopped_by"] == "exhausted"
    assert json.loads(out.read_text()) == json.loads(json.dumps(report))
    again = ws.search(DEV, fake_eval, grid=SMALL, max_configs=8)
    assert again == report  # deterministic


def test_budget_caps_stop_the_search():
    assert ws.search(DEV, fake_eval, grid=SMALL, max_configs=3)["stopped_by"] == "max_configs"
    capped = ws.search(DEV, fake_eval, grid=SMALL, max_configs=8, max_tokens=250)
    assert capped["stopped_by"] == "max_tokens" and capped["evaluated"] == 3 and capped["tokens"] >= 250


def test_non_dev_cases_are_refused():
    for bad in ({"case_id": "t1test-001"}, {"case_id": "x", "split": "blind"}, {"case_id": "t1blind-9"}):
        with pytest.raises(ws.WorkflowSearchError):
            ws.search([bad], fake_eval, grid=SMALL)
    with pytest.raises(ws.WorkflowSearchError):
        ws.search(DEV, fake_eval, mode="evolve")


def test_offline_smoke_through_the_driver(tmp_path):
    world = h.case_0007_world()
    toolbox = h.ScenarioToolbox(world)
    case = {"case_id": "case-0007", "facts": FACTS, "before": world.case_date}
    grid = {"topology": ["orchestrated", "sequential"]}
    runs = [ws.search([case], ws.slot_fill_evaluator(tools=toolbox.tools, llm=h.full_pipeline_llm()), grid=grid, report_path=tmp_path / f"r{i}.json") for i in range(2)]
    assert runs[0] == runs[1] and runs[0]["evaluated"] == 2
    assert all(0.0 < r["score"] <= 1.0 and r["tokens"] > 0 for r in runs[0]["ranking"])
    assert (tmp_path / "r0.json").read_bytes() == (tmp_path / "r1.json").read_bytes()
