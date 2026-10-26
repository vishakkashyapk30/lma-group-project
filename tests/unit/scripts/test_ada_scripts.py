"""scripts/ada/*.sh: no stub is left, every runner script takes SHARD N_SHARDS and hands the shard to the Python runner (bash only, nothing heavy runs)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
ADA = REPO / "scripts" / "ada"
RUNNERS = sorted(p.name for p in ADA.glob("run_*.sh") if p.name != "run_teacher_dossiers.sh")


def sh(*args, env=None, timeout=60):
    import os

    e = {**os.environ, "PY": sys.executable, "OUT": str(REPO / "results_unused"), "JOB": "t6_tool_calling", **(env or {})}
    return subprocess.run(["bash", *map(str, args)], capture_output=True, text=True, env=e, cwd=REPO, timeout=timeout)


def test_no_script_is_a_stub():
    for p in ADA.glob("*.sh"):
        assert 'echo "TODO"' not in p.read_text(encoding="utf-8"), p.name
        assert sh("-n", p).returncode == 0, p.name  # syntax


@pytest.mark.parametrize("name", RUNNERS)
def test_runner_scripts_check_their_arguments(name):
    r = sh(ADA / name)
    assert r.returncode == 2 and "SHARD N_SHARDS" in r.stderr
    r = sh(ADA / name, "3", "3")
    assert r.returncode == 2 and "outside 0..2" in r.stderr
    r = sh(ADA / name, "x", "2")
    assert r.returncode == 2


def test_run_shard_hands_the_shard_to_the_python_runner(tmp_path):
    ok = sh(ADA / "run_shard.sh", "0", "2", env={"JOB": "t6_tool_calling", "HOURS": "0", "OUT": str(tmp_path)})
    assert ok.returncode == 0 and "t6_tool_calling: 0 case(s) completed (shard 0/2)" in ok.stdout and "shard=0/2" in ok.stdout
    batch = sh(ADA / "run_shard.sh", "0", "1", env={"JOB": "qlora", "OUT": str(tmp_path)})
    assert batch.returncode == 2 and "batch job" in batch.stderr  # QLoRA is sbatch, never a shard
    nojob = sh(ADA / "run_shard.sh", "0", "1", env={"JOB": ""})
    assert nojob.returncode != 0


def test_thin_runner_scripts_use_the_runner_modules(tmp_path):
    for name, expect in (("run_t6_t7.sh", ["t6_tool_calling", "t7_safety"]), ("run_features.sh", ["f4_nocache"]), ("run_rq1.sh", ["rq1_full"])):
        r = sh(ADA / name, "1", "4", env={"HOURS": "0", "OUT": str(tmp_path)})
        assert r.returncode == 0, r.stderr
        for job in expect:
            assert f"{job}: 0 case(s) completed (shard 1/4)" in r.stdout


def test_stage_to_scratch_refuses_client_data_and_missing_models(tmp_path):
    assert sh(ADA / "stage_to_scratch.sh").returncode == 2
    r = sh(ADA / "stage_to_scratch.sh", "../etc", env={"VS_ADA_MODELS": str(tmp_path), "SCRATCH": str(tmp_path / "s")})
    assert r.returncode == 2 and "folder name" in r.stderr
    r = sh(ADA / "stage_to_scratch.sh", "nomodel", env={"VS_ADA_MODELS": str(tmp_path), "SCRATCH": str(tmp_path / "s")})
    assert r.returncode == 1 and "no " in r.stderr
    (tmp_path / "m" / "tiny").mkdir(parents=True)
    (tmp_path / "m" / "tiny" / "w.bin").write_bytes(b"x")
    ok = sh(ADA / "stage_to_scratch.sh", "tiny", env={"VS_ADA_MODELS": str(tmp_path / "m"), "SCRATCH": str(tmp_path / "s")})
    assert ok.returncode == 0 and (tmp_path / "s" / "models" / "tiny" / "w.bin").read_bytes() == b"x"


def test_tunnel_needs_a_node():
    r = sh(ADA / "tunnel_demo.sh", env={"NODE": ""})
    assert r.returncode != 0 and "NODE" in r.stderr
