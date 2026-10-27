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


def test_recall_evaluator_scores_factor_recall_against_dev_g1(tmp_path):
    world = h.case_0007_world()
    toolbox = h.ScenarioToolbox(world)
    case = {"case_id": "case-0007", "facts": FACTS, "before": world.case_date,
            "gold": {"G1": {"labels": ["custody_period", "charge_sheet_filed"]}}, "answerable": ["custody_period", "charge_sheet_filed", "antecedents"]}
    evaluate = ws.recall_evaluator(tools=toolbox.tools, llm=h.full_pipeline_llm())
    out = evaluate(Switches(), [case])
    assert out["cases_scored"] == 1 and 0.0 <= out["score"] <= 1.0 and out["tokens"] > 0 and "M1" in out["reward"]
    assert out == ws.recall_evaluator(tools=toolbox.tools, llm=h.full_pipeline_llm())(Switches(), [case])  # deterministic
    # a case whose agreed G1 has no answerable factor is left out of the mean (recall undefined), not scored 0
    empty = {**case, "case_id": "case-0008", "gold": {"G1": {"labels": []}}}
    assert evaluate(Switches(), [empty])["cases_scored"] == 0


def test_main_runs_the_grid_offline_and_refuses_a_model_backend(tmp_path, monkeypatch, capsys):
    cases = tmp_path / "dev.jsonl"
    cases.write_text("\n".join(json.dumps({"case_id": f"t1dev-{i:03d}", "facts": "x", "before": "2024-02-16"}) for i in range(3)) + "\n", encoding="utf-8")
    monkeypatch.setattr(ws, "recall_evaluator", lambda *a, **k: fake_eval)
    monkeypatch.delenv("VS_LLM_BACKEND", raising=False)
    out = tmp_path / "rep.json"
    assert ws.main(["--cases", str(cases), "--n", "2", "--grid", "small", "--max-configs", "4", "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["evaluated"] == 4 and report["cases"] == ["t1dev-000", "t1dev-001"] and report["test"] == "pending" and "harness" in report["note"]
    assert report["winner"] == {"stopping": "rules_llm", "topology": "sequential"}
    assert "score=" in capsys.readouterr().out
    monkeypatch.setenv("VS_LLM_BACKEND", "openai")
    assert ws.main(["--cases", str(cases), "--out", str(tmp_path / "x.json")]) == 2
    assert "planned" in capsys.readouterr().err and not (tmp_path / "x.json").exists()
    with pytest.raises(NotImplementedError, match="planned"):
        ws.assert_offline()


def test_job_runs_the_smoke_offline_and_the_hosted_arm_stays_planned(tmp_path, monkeypatch):
    from vakeel_sahayak.eval.runners import jobs
    from vakeel_sahayak.testsets import gold_source

    monkeypatch.setattr(ws, "recall_evaluator", lambda *a, **k: fake_eval)
    monkeypatch.setattr(gold_source, "load_t1", lambda split, *a, **k: [{"case_id": f"t1dev-{i:03d}"} for i in range(5)])
    monkeypatch.delenv("VS_LLM_BACKEND", raising=False)
    n = jobs.run_job("s13_workflow_search", {"runner": "workflow_search"}, 0, 1, str(tmp_path), 0.0)
    report = json.loads((tmp_path / "runs" / "s13_workflow_search" / "search_report.json").read_text(encoding="utf-8"))
    assert n == 4 and len(report["cases"]) == 3 and report["test"] == "pending"
    monkeypatch.setenv("VS_LLM_BACKEND", "sarvam")
    with pytest.raises(NotImplementedError, match="planned"):
        jobs.run_job("s13_workflow_search", {"runner": "workflow_search"}, 0, 1, str(tmp_path), 0.0)


# ---- the model-backed arm (opt-in; here on the offline stand-in and a fake ledger) ---------------------------------------------------------------------------

def test_model_backed_search_is_resumable_and_writes_a_manifest(tmp_path, monkeypatch):
    monkeypatch.delenv("VS_LLM_BACKEND", raising=False)
    calls = []

    def counting(switches, cases):
        calls.append(switches.variant())
        return fake_eval(switches, cases)

    small = {"stopping": ["rules", "rules_llm"], "topology": ["orchestrated", "sequential"]}
    r1 = ws.model_backed_search(DEV, tmp_path / "s13", evaluator=counting, grid=small, max_configs=2)
    assert r1["evaluated"] == 2 and r1["stopped_by"] == "max_configs" and len(calls) == 2 and r1["resumed"] == 0 and r1["test"] == "pending"
    r2 = ws.model_backed_search(DEV, tmp_path / "s13", evaluator=counting, grid=small, max_configs=4)
    assert r2["evaluated"] == 4 and r2["resumed"] == 2 and len(calls) == 4 and r2["stopped_by"] == "exhausted"
    assert r2["winner"] == {"stopping": "rules_llm", "topology": "sequential"}
    man = json.loads((tmp_path / "s13" / "MANIFEST.json").read_text(encoding="utf-8"))
    assert man["arm"] == "S13" and man["backend"] == "offline" and man["cases"] == ["t1dev-000"] and "git_sha" in man and man["test"] == "pending"


def test_model_backed_search_stops_before_the_ledger_runs_out_and_refuses_non_dev(tmp_path, monkeypatch):
    monkeypatch.setenv("VS_LLM_BACKEND", "openai")
    spent = {"v": 0.0}

    def state(backend):
        return spent["v"], 1.0 - spent["v"], "USD"

    def costly(switches, cases):
        spent["v"] += 0.4
        return fake_eval(switches, cases)

    rep = ws.model_backed_search(DEV, tmp_path / "a", evaluator=costly, max_configs=10, min_remaining=0.1, state_fn=state)
    # each configuration costs 0.4: after two there is 0.2 left, below 1.25 x 0.4, so the third never starts
    assert rep["evaluated"] == 2 and rep["stopped_by"] == "ledger" and abs(spent["v"] - 0.8) < 1e-9
    with pytest.raises(ws.WorkflowSearchError):
        ws.model_backed_search([{"case_id": "t1test-001"}], tmp_path / "b", evaluator=costly, state_fn=state)


def test_cli_model_backed_needs_a_cap_on_a_hosted_backend_and_runs_offline_on_two_cases(tmp_path, monkeypatch, capsys):
    cases = tmp_path / "dev.jsonl"
    cases.write_text("\n".join(json.dumps({"case_id": f"t1dev-{i:03d}", "facts": "x", "before": "2024-02-16"}) for i in range(3)) + "\n", encoding="utf-8")
    monkeypatch.setattr(ws, "recall_evaluator", lambda *a, **k: fake_eval)
    monkeypatch.setenv("VS_LLM_BACKEND", "sarvam")
    monkeypatch.delenv("VS_SARVAM_CAP_INR", raising=False)
    assert ws.main(["--cases", str(cases), "--model-backed", "--out", str(tmp_path / "o1")]) == 2
    assert "VS_SARVAM_CAP_INR" in capsys.readouterr().err and not (tmp_path / "o1").exists()
    monkeypatch.setenv("VS_LLM_BACKEND", "offline")
    assert ws.main(["--cases", str(cases), "--n", "2", "--grid", "small", "--max-configs", "2", "--model-backed", "--out", str(tmp_path / "o2")]) == 0
    rep = json.loads((tmp_path / "o2" / "search_report.json").read_text(encoding="utf-8"))
    assert rep["evaluated"] == 2 and rep["cases"] == ["t1dev-000", "t1dev-001"]
    # without the flag a hosted backend is still refused as before
    monkeypatch.setenv("VS_LLM_BACKEND", "openai")
    assert ws.main(["--cases", str(cases), "--out", str(tmp_path / "x.json")]) == 2


def test_model_backed_search_on_the_production_agents_with_the_stand_in_models(tmp_path, monkeypatch):
    """Two cases through the production pipeline on the offline stand-ins (fixture toolbox), reward M1 against the gold labels; rerun resumes everything."""
    monkeypatch.delenv("VS_LLM_BACKEND", raising=False)
    world = h.case_0007_world()
    toolbox = h.ScenarioToolbox(world)
    base = {"facts": FACTS, "before": world.case_date, "gold": {"G1": {"labels": ["custody_period", "charge_sheet_filed"]}}, "answerable": ["custody_period", "charge_sheet_filed", "antecedents"]}
    cases = [{**base, "case_id": "case-0007"}, {**base, "case_id": "case-0008"}]
    evaluate = ws.recall_evaluator(tools=toolbox.tools, llm=h.full_pipeline_llm())
    grid = {"topology": ["orchestrated", "sequential"]}
    rep = ws.model_backed_search(cases, tmp_path / "s", evaluator=evaluate, grid=grid)
    assert rep["evaluated"] == 2 and rep["resumed"] == 0 and all(r["tokens"] > 0 and r["cases_scored"] == 2 for r in rep["ranking"])
    again = ws.model_backed_search(cases, tmp_path / "s", evaluator=evaluate, grid=grid)
    assert again["resumed"] == 2 and again["ranking"] == rep["ranking"]
