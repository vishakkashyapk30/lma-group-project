"""scripts/sweep_dev.py and configs/eval/sweep_dev.yaml: every arm is dispatchable or a declared study, studies become one job each, shard selection (offline, nothing is run)."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("sweep_dev", REPO / "scripts" / "sweep_dev.py")
sweep = importlib.util.module_from_spec(spec)
sys.modules["sweep_dev"] = sweep
spec.loader.exec_module(sweep)

CFG = yaml.safe_load((REPO / "configs" / "eval" / "sweep_dev.yaml").read_text(encoding="utf-8"))


def expanded_systems(arm):
    return sweep.EXPAND.get(arm["id"], [arm["id"]])


def test_every_arm_is_dispatchable_or_a_declared_study():
    from vakeel_sahayak.eval import studies
    from vakeel_sahayak.eval.runners.systems import BASELINE_IDS, system_switches

    for arm in CFG["arms"]:
        if arm.get("kind") == "study":
            assert arm["study"] in {*studies.STUDIES, *studies.OTHER}, f"{arm['id']}: unknown study {arm['study']!r}"
            continue
        for system in expanded_systems(arm):
            if system.lower() not in BASELINE_IDS:
                system_switches(system)  # raises for an unbuilt or unknown id


def test_arms_that_are_not_driver_runs_are_studies_and_the_inert_variants_have_one():
    from vakeel_sahayak.eval import studies

    covered = {arm["id"] for arm in CFG["arms"] if arm.get("kind") == "study"}
    assert {"S14b", "S14c", "S16", "S16b"} <= covered  # the variants whose per-case run equals Full are measured by a study, not run through the driver
    assert set(studies.ARMS) >= {"S14b", "S14c", "S16", "S16b", "S4", "S5"}
    for arm in CFG["arms"]:
        if arm.get("kind") != "study":
            assert arm["id"] not in {"S14b", "S14c", "S16", "S16b"}


def test_not_run_ids_are_declared_for_a_reason():
    from vakeel_sahayak.orchestration.switches import IMPLEMENTED_VARIANTS

    for ident, why in CFG["not_run"].items():
        assert why and ident == "S13"  # S15b was built; S13 has the harness, only its model-backed arm is planned
    assert "S13" in IMPLEMENTED_VARIANTS  # the harness exists; its model-backed arm is the part that is planned


def args(**kw):
    base = {"phase": 1, "arms": None, "backend": None, "shards": 4, "shard_index": None, "parallel": 1, "dry_run": True}
    return argparse.Namespace(**{**base, **kw})


def test_phase_1_has_one_job_per_study_and_none_for_inert_driver_runs():
    jobs = sweep.jobs_for(CFG, args())
    studies = [j["study"] for j in jobs if "study" in j]
    assert sorted(studies) == ["m17", "s14", "s16", "s4s5"]  # S14b and S14c share a study, S16 and S16b, S4 and S5 retrieval
    systems = {j["system"] for j in jobs if "study" not in j}
    assert not systems & {"S14b", "S14c", "S16", "S16b"} and "S4" in systems and "S5" in systems
    only = sweep.jobs_for(CFG, args(arms="s14"))
    assert [j["study"] for j in only] == ["s14"]


def test_study_commands(tmp_path):
    cfg = {**CFG, "out_roots": {k: str(tmp_path / k) for k in CFG["out_roots"]}}
    jobs = {j["study"]: j for j in sweep.jobs_for(cfg, args()) if "study" in j}
    root = tmp_path / "offline"
    cmd, out = sweep.study_command(jobs["s14"], cfg, root)
    assert cmd[1:4] == ["-m", "vakeel_sahayak.eval.studies", "s14"] and "--n" not in cmd and out == root / "studies" / "s14"
    cmd, out = sweep.study_command(jobs["s4s5"], cfg, root)
    assert cmd[-2:] == ["--n", "150"]
    cmd, out = sweep.study_command(jobs["m17"], cfg, root, shard=2, n_shards=4)
    assert cmd[3] == "m17" and "--shard" in cmd and cmd[cmd.index("--shard") + 1] == "2" and out == root / "outputs" / "m17"
    assert Path(cmd[cmd.index("--cases") + 1]).read_text(encoding="utf-8").count("\n") == 20  # the first 20 dev cases


def test_shard_index_selects_one_shard(tmp_path, capsys):
    cfg = {**CFG, "out_roots": {k: str(tmp_path / k) for k in CFG["out_roots"]}}
    jobs = [j for j in sweep.jobs_for(cfg, args(phase=4, backend="ada", arms="S2")) if j["system"] == "S2"]
    assert len(jobs) == 1
    assert sweep.launch(jobs[0], cfg, args(phase=4, shard_index=2)) == []
    out = capsys.readouterr().out
    assert out.count("--run-index") == 1 and "--shard 2 --n-shards 4" in out
    assert sweep.launch(jobs[0], cfg, args(phase=4)) == [] and capsys.readouterr().out.count("--run-index") == 4


def test_shard_index_outside_the_range_is_a_usage_error(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sweep_dev.py", "run", "--phase", "1", "--shards", "2", "--shard-index", "2", "--dry-run"])
    with pytest.raises(SystemExit) as e:
        sweep.main()
    assert e.value.code == 2
