"""VI-03: every implemented variant is dispatchable by one id, described as a job in configs/eval/runs.yaml, plannable without running, and stamped in the run manifest."""

from __future__ import annotations

import json

import pytest
import yaml

from vakeel_sahayak.eval.runners import driver, plan
from vakeel_sahayak.eval.runners.systems import (
    BASELINE_IDS,
    canonical_system,
    dispatchable_ids,
    system_runner,
    system_switches,
)
from vakeel_sahayak.orchestration.switches import IMPLEMENTED_VARIANTS, Switches, _variant_table

REPO = driver.REPO
CFG = yaml.safe_load((REPO / "configs" / "eval" / "runs.yaml").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ dispatch
def test_every_implemented_variant_and_baseline_is_dispatchable():
    ids = dispatchable_ids()
    assert set(BASELINE_IDS) <= set(ids)
    bases = {i.split(":")[0] for i in ids}
    assert (IMPLEMENTED_VARIANTS - {"full"}) <= bases
    for ident in ids:
        runner, switches = system_runner(ident)
        assert callable(runner) and isinstance(switches, Switches)


def test_a_variant_runs_the_switches_it_names():
    for ident in dispatchable_ids():
        base = ident.split(":")[0]
        if base in BASELINE_IDS or base in {"A5", "A10", "S13"}:
            continue
        assert system_switches(ident).variant() == base


def test_arguments_of_a5_a10_and_s13():
    assert system_switches("A5:base_4b").extractor == "base_4b"
    assert system_switches("A10:caselaw.reasoning").knockout_store == "caselaw.reasoning"
    assert system_switches("S13:stopping=llm").stopping == "llm"
    for bad in ("A5", "A10", "S13", "A5:finetuned_4b", "A10:nope", "full:x", "S1:x"):
        with pytest.raises(ValueError):
            system_switches(bad)


def test_plan_aliases_and_case():
    assert canonical_system("a12") == "S6" and canonical_system("A11b") == "S3" and canonical_system("B0L") == "b0l"
    assert canonical_system("b5") == "B5"


def test_a_declared_but_unbuilt_variant_fails_loudly_and_an_unknown_id_is_a_value_error():
    with pytest.raises(NotImplementedError, match="S15b"):
        system_runner("S15b")
    with pytest.raises(ValueError, match="unknown system"):
        system_runner("zz9")


def test_a10_runner_stops_after_retrieval(monkeypatch):
    seen = {}
    monkeypatch.setattr(driver, "run_agents", lambda case, ctx, **kw: seen.update(kw) or {"brief": {}})
    runner, _ = system_runner("A10:law.statutes")
    runner({}, None)
    assert seen == {"stop_after": "retrieval"}


# ------------------------------------------------------------------ runs.yaml validator
def _covered() -> set[str]:
    out: set[str] = set()
    meta = CFG.get("job_meta") or {}
    for name, job in CFG["jobs"].items():
        out |= plan.covered_variants(name, job, meta.get(name))
    return out


def test_every_implemented_id_has_a_job_or_an_exclusion():
    covered = _covered()
    excluded = {canonical_system(k) for k in CFG["exclusions"]}
    missing = [i for i in IMPLEMENTED_VARIANTS if i != "full" and i not in covered and i not in excluded]
    assert not missing, f"no job and no documented exclusion: {missing}"
    assert "full" in covered and set(BASELINE_IDS) - {"b0l", "b0s"} <= covered | {"b0l", "b0s"}


def test_every_declared_but_unimplemented_id_is_a_documented_exclusion():
    declared_unbuilt = {k for k in _variant_table() if k not in IMPLEMENTED_VARIANTS}
    assert declared_unbuilt <= {canonical_system(k) for k in CFG["exclusions"]}
    for ident in CFG["exclusions"]:  # an exclusion is never also a job
        assert canonical_system(ident) not in _covered()


def test_every_job_system_is_dispatchable():
    for name, job in CFG["jobs"].items():
        for system in plan.job_systems(job):
            runner, _ = system_runner(system)
            assert callable(runner), (name, system)


def test_jobs_are_complete_and_ordered():
    jobs, meta = CFG["jobs"], CFG["job_meta"]
    assert set(meta) == set(jobs), set(meta) ^ set(jobs)
    assert set(CFG["priority"]) <= set(jobs)
    assert all(meta[j]["tier"] in {"A", "B", "C", "X"} and meta[j]["backend"] in {"openai", "sarvam", "ada", "laptop"} for j in jobs)
    assert all(jobs[j]["where"] in {meta[j]["backend"], "ada-batch", "laptop+ada"} for j in jobs), "`where` and job_meta backend disagree"


def test_hosted_blocks_fit_their_caps_at_the_default_settings():
    rows = plan.jobs_plan([j for j, m in CFG["job_meta"].items() if m["backend"] in {"openai", "sarvam"}])
    spend, warnings = plan.spend_summary(rows)
    assert not warnings, warnings
    assert spend["openai_usd"] <= CFG["budgets"]["openai_usd_code_default"] and spend["sarvam_inr"] <= CFG["budgets"]["sarvam_cap_inr"]


def test_existing_jobs_are_unchanged():
    jobs = CFG["jobs"]
    assert jobs["rq1_full"]["systems"] == ["full", "b0", "b1", "b4"] and jobs["rq1_full"]["runs"] == 3 and "runs" not in jobs["ablations"]
    assert jobs["teacher_dossiers"] == {"where": "ada", "model": "teacher", "node_hours": 60}


# ------------------------------------------------------------------ plan command
def test_plan_prints_cases_systems_runs_and_cost_without_running(capsys, monkeypatch):
    monkeypatch.setattr(driver, "run_cases", lambda *a, **k: pytest.fail("plan must not run anything"))
    assert driver.main(["plan", "--job", "s3_stopping"]) == 0
    out = capsys.readouterr().out
    assert "S3" in out and "S3b" in out and "cases=100" in out and "runs=1" in out and "USD" in out and "nothing was run" in out


def test_plan_arithmetic_uses_the_measured_numbers():
    p = plan.estimate_job("rq1_secondary_sarvam")
    est = CFG["estimate"]
    full = next(r for r in p["per_system"] if r["system"] == "full")
    assert full["case_runs"] == 6 and full["usd"] == pytest.approx(6 * est["usd_per_case"], abs=1e-4)
    assert full["tokens_in"] == 6 * est["tokens_in_per_case"]
    assert plan.estimate_job("rq1_b0l_b0s_b6")["per_system"][-1]["usd"] == 0  # B6 needs no model


def test_sarvam_inr_per_case_matches_the_dashboard_price():
    assert plan.sarvam_inr_per_case(CFG) == pytest.approx(1.15, abs=0.01)


def test_plan_warns_when_the_sarvam_cap_is_exceeded_and_the_cap_comes_from_the_env(monkeypatch, capsys):
    monkeypatch.setenv("VS_SARVAM_CAP_INR", "5")
    assert plan.sarvam_cap_inr(CFG) == 5.0
    assert driver.main(["plan", "--job", "rq1_secondary_sarvam"]) == 0
    assert "WARNING" in capsys.readouterr().out
    monkeypatch.setenv("VS_SARVAM_CAP_INR", "100")
    assert driver.main(["plan", "--job", "rq1_secondary_sarvam"]) == 0
    assert "WARNING" not in capsys.readouterr().out


def test_plan_all_and_sarvam_full_and_unknown_job(capsys):
    assert driver.main(["plan", "--all"]) == 0 and "openai_sparring_block" in capsys.readouterr().out
    assert driver.main(["plan", "--sarvam-full"]) == 0 and "total INR" in capsys.readouterr().out
    assert driver.main(["plan", "--job", "nope"]) == 2


def test_run_refuses_an_unbuilt_id_with_exit_2(capsys):
    assert driver.main(["run", "--system", "S15b"]) == 2
    assert "S15b" in capsys.readouterr().err


# ------------------------------------------------------------------ manifest
def test_manifest_records_switches_describe_and_prompt_hash(tmp_path):
    sw = Switches.for_variant("S8")
    m = driver.write_run_manifest(tmp_path, system="S8", switches=sw, seed=1)
    saved = json.loads((tmp_path / "MANIFEST.json").read_text())
    assert saved["variant"] == "S8" and saved["describe"] == sw.describe() and saved["switches"]["repair_mode"] == "self_critique"
    assert saved["prompt_hash"] == driver.prompt_hash() and len(saved["prompt_hash"]) == 16 and m["scope"]


def test_prompt_hash_changes_with_a_template(monkeypatch, tmp_path):
    h = driver.prompt_hash()
    driver.prompt_hash.cache_clear()
    monkeypatch.setattr(driver, "PROMPT_FILES", ())
    assert driver.prompt_hash() != h
    driver.prompt_hash.cache_clear()


def test_output_directories_of_argument_systems_are_path_safe(tmp_path):
    assert ":" not in str(driver.outputs_dir("job", "A10:caselaw.reasoning", 2, root=str(tmp_path)))


def test_batch_variants_share_one_cache_and_the_default_has_none():
    assert driver.shared_cache_for(Switches()) is None
    assert driver.shared_cache_for(Switches.for_variant("S14")) is not None
    assert driver.shared_cache_for(Switches.for_variant("S14d")) is not None
