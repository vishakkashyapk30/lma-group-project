"""The thin evaluation driver: scripted counsel, GateGuard stays in force, manifests, shards, and the jobs that wait for unbuilt code."""

from __future__ import annotations

import json

import pytest

from tests.integration._helpers import full_pipeline_llm
from vakeel_sahayak.eval.runners import driver, jobs
from vakeel_sahayak.eval.runners.driver import build_context, run_agents
from vakeel_sahayak.schemas.enums import EventKind

FACTS = "The accused was arrested on 20.08.2024 under Section 318(4) BNS. Charge sheet filed 02.11.2024."


def case(world, **kw):
    return {"case_id": "case-0007", "facts": FACTS, "before": world.case_date, **kw}


def ctx_for(toolbox, **kw):
    return build_context(case(toolbox.world), tools=toolbox.tools, llm=full_pipeline_llm(), **kw)


def test_without_a_scenario_gate_1_is_approved_and_export_stays_blocked(toolbox):
    res = run_agents(case(toolbox.world), ctx_for(toolbox))
    assert res["gate1_approved"] and not res["gate2_approved"]
    assert res["export"]["blocked"] is True and toolbox.exports == []


def test_counsel_that_does_not_approve_gate_1_stops_the_run(toolbox):
    res = run_agents(case(toolbox.world, scenario={"approve_gate1": False}), ctx_for(toolbox))
    assert not res["gate1_approved"] and res["packs"] == 0 and res["brief"]["grounds"] == []


def test_approving_gate_2_only_when_the_scenario_says_so(toolbox):
    ctx = ctx_for(toolbox)
    res = run_agents(case(toolbox.world, scenario={"approve_gate2": True}), ctx)
    assert res["gate2_approved"] and res["export"].get("blocked") is not True
    approvals = [e for e in ctx.log.read("case-0007") if e.kind == EventKind.GATE_APPROVED]
    assert {e.actor for e in approvals} == {"counsel"}


def test_the_driver_never_writes_an_approval_itself():
    import inspect

    src = inspect.getsource(driver)
    assert "EventKind.GATE_APPROVED" not in src and "approve_gate(" not in src


def test_a_shard_saves_cases_manifest_and_event_logs(tmp_path, toolbox):
    cases = tmp_path / "cases.jsonl"
    cases.write_text("\n".join(json.dumps({"case_id": f"c-{i}", "facts": FACTS, "before": "2025-02-03"}) for i in range(3)) + "\n")
    from vakeel_sahayak.orchestration.switches import Switches

    out = tmp_path / "out"
    runner = lambda c, ctx: __import__("vakeel_sahayak.schemas.bail_brief", fromlist=["BailBrief"]).BailBrief(case_id=c["case_id"])  # noqa: E731
    assert driver.run_cases(str(cases), str(out), "full", runner, Switches(), seed=5) == 3
    assert driver.load_progress(str(out)) == {"c-0", "c-1", "c-2"}
    manifest = json.loads((out / "MANIFEST.json").read_text())
    assert manifest["seed"] == 5 and manifest["variant"] == "full" and manifest["cases_hash"] and "models" in manifest and manifest["config_hash"]
    saved = json.loads((out / "c-1.json").read_text())
    assert saved["meta"]["seed"] == 6 and "tokens" in saved["meta"] and saved["brief"]["case_id"] == "c-1"
    assert driver.run_cases(str(cases), str(out), "full", runner, Switches()) == 0  # resumed: nothing left


def test_a_crashing_case_is_saved_as_an_error_record(tmp_path):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps({"case_id": "c-0", "facts": FACTS, "before": "2025-02-03"}) + "\n")

    def boom(c, ctx):
        raise RuntimeError("model fell over")

    from vakeel_sahayak.orchestration.switches import Switches

    driver.run_cases(str(cases), str(tmp_path / "o"), "b0", boom, Switches())
    saved = json.loads((tmp_path / "o" / "c-0.json").read_text())
    assert "RuntimeError" in saved["error"] and saved["brief"]["grounds"] == []


def test_the_output_layout_follows_contract_c6(tmp_path):
    out = driver.outputs_dir("rq1_full", "full", 1, root=str(tmp_path))
    assert out == tmp_path / "runs" / "rq1_full" / "outputs" / "full"
    assert driver.outputs_dir("rq1_full", "full", 2, root=str(tmp_path)).name == "full__run2"


# RECONCILED: VI-07 built the RQ2 pipelines and the feature evaluations, so these jobs are dispatched to `eval/ingestion/rq2.py` and `eval/features/*`; only a job whose code is
# still missing (the teacher dossiers) names its dependency. The routing of the built jobs is checked below with the runners replaced (nothing is run here).
@pytest.mark.parametrize("job", ["teacher_dossiers"])
def test_jobs_waiting_for_unbuilt_code_name_their_dependency(job):
    with pytest.raises(NotImplementedError, match="needs"):
        jobs.run_job(job, {}, 0, 1, "unused", 0.0)


@pytest.mark.parametrize("job", sorted({*jobs.RQ2_JOBS, *jobs.FEATURE_JOBS}))
def test_vi07_jobs_are_dispatched_to_their_runners(job, monkeypatch, tmp_path):
    called = []
    if job in jobs.RQ2_JOBS:
        from vakeel_sahayak.eval.ingestion import rq2

        monkeypatch.setattr(rq2, "run", lambda arm, *a, **k: called.append(arm) or {"done": 0})
        jobs.run_job(job, {}, 0, 1, str(tmp_path), 0.0)
        assert called == jobs.RQ2_JOBS[job]
    else:
        import importlib

        for name in jobs.FEATURE_JOBS[job]:
            mod = importlib.import_module("vakeel_sahayak.eval.features." + name)
            monkeypatch.setattr(mod, "run", lambda out, shard, n, _n=name: called.append(_n))
        jobs.run_job(job, {}, 0, 1, str(tmp_path), 0.0)
        assert called == jobs.FEATURE_JOBS[job]


def test_a_case_that_hits_a_free_tier_daily_quota_is_not_saved_and_the_run_stops(tmp_path):
    from vakeel_sahayak.models.hosted.quota import note_quota_stop
    from vakeel_sahayak.orchestration.switches import Switches
    from vakeel_sahayak.schemas.bail_brief import BailBrief

    cases = tmp_path / "cases.jsonl"
    cases.write_text("\n".join(json.dumps({"case_id": f"c-{i}", "facts": FACTS, "before": "2025-02-03"}) for i in range(3)) + "\n")
    out = tmp_path / "out"
    seen: list[str] = []

    def runner(c, ctx):
        seen.append(c["case_id"])
        if c["case_id"] == "c-1":
            note_quota_stop()  # a call of this case was refused for the daily quota (the local fallback answered)
        return BailBrief(case_id=c["case_id"])

    assert driver.run_cases(str(cases), str(out), "full", runner, Switches()) == 1
    assert driver.load_progress(str(out)) == {"c-0"} and seen == ["c-0", "c-1"]  # c-1 is not saved; c-2 was not started
    plain = lambda c, ctx: BailBrief(case_id=c["case_id"])  # noqa: E731 - after the reset
    assert driver.run_cases(str(cases), str(out), "full", plain, Switches()) == 2
    assert driver.load_progress(str(out)) == {"c-0", "c-1", "c-2"}


def test_hosted_quota_left_is_none_off_a_configured_provider(monkeypatch):
    monkeypatch.delenv("VS_LLM_BACKEND", raising=False)
    assert driver.hosted_quota_left() is None
    monkeypatch.setenv("VS_LLM_BACKEND", "gemini")
    monkeypatch.setenv("VS_MODELS", "auto")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert driver.hosted_quota_left() is None  # no key: the factory answers locally, the driver does not stop
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaFAKE-driver-test")
    monkeypatch.setenv("VS_GEMINI_RPD", "4")
    assert driver.hosted_quota_left() == 4
