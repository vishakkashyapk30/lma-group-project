"""scripts/ada/stage_qlora_inputs.sh and fetch_qlora_outputs.sh (laptop side): refusals and the local round trip; no ssh, nothing is sent."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
STAGE, FETCH = REPO / "scripts/ada/stage_qlora_inputs.sh", REPO / "scripts/ada/fetch_qlora_outputs.sh"
GIT = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
ROW = json.dumps({"messages": [{"role": "user", "content": "f"}, {"role": "assistant", "content": "{}"}]}) + "\n"


def git(repo, *a):
    return subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True, env=GIT).stdout


@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "repo"
    for rel, text in {
        "configs/finetune/qlora.yaml": "base_model: x\n",
        "scripts/ada/sbatch_qlora.sbatch": "#!/bin/bash\n",
        "data/cases/.gitkeep": "",
        ".env.example": "KEY=\n",
        "src/a.py": "x=1\n",
    }.items():
        (r / rel).parent.mkdir(parents=True, exist_ok=True)
        (r / rel).write_text(text)
    git(r, "init", "-q")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "c")
    git(r, "tag", "qlora-v1")
    d = tmp_path / "ft"
    d.mkdir()
    (d / "train.jsonl").write_text(ROW * 3)
    (d / "dev.jsonl").write_text(ROW)
    return r


def run(script, *args, **env):
    return subprocess.run(["bash", str(script), *map(str, args)], capture_output=True, text=True, timeout=60, env={**os.environ, **env})


def stage(repo, tmp_path, tag="qlora-v1", data=None, **env):
    return run(STAGE, tag, data or tmp_path / "ft", REPO=repo, NO_SEND="1", STAGE_DIR=tmp_path / "stage", **env)


def test_scripts_are_valid_bash():
    for s in (STAGE, FETCH):
        assert subprocess.run(["bash", "-n", str(s)]).returncode == 0


def test_stage_needs_a_tag_that_exists(repo, tmp_path):
    assert run(STAGE, REPO=repo).returncode == 2
    r = stage(repo, tmp_path, tag="nope")
    assert r.returncode == 2 and "no such git tag" in r.stderr


def test_stage_builds_the_folder_with_checksums_and_the_tag_sha(repo, tmp_path):
    r = stage(repo, tmp_path)
    assert r.returncode == 0, r.stderr
    st = tmp_path / "stage"
    assert {p.name for p in st.iterdir()} == {"code-qlora-v1.tar.gz", "train.jsonl", "dev.jsonl", "qlora.yaml", "sbatch_qlora.sbatch", "stage.env", "SHA256SUMS"}
    assert git(repo, "rev-parse", "qlora-v1^{commit}").strip() in (st / "stage.env").read_text()
    assert subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=st, capture_output=True).returncode == 0


def test_stage_refuses_when_ada_home_has_no_room(repo, tmp_path):
    r = stage(repo, tmp_path, ADA_FREE_KB="300")
    assert r.returncode == 4 and "REFUSED" in r.stderr
    assert stage(repo, tmp_path, ADA_FREE_KB="2000000").returncode == 0


@pytest.mark.parametrize("bad", ["data/raw/x.txt", "data/cases/case-1/file.pdf", ".env", "keys/id_rsa", "deploy.pem"])
def test_stage_refuses_a_tag_whose_archive_holds_client_data_or_secrets(repo, tmp_path, bad):
    f = repo / bad
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("secret")
    git(repo, "add", "-f", "-A")
    git(repo, "commit", "-qm", "bad")
    git(repo, "tag", "bad")
    r = stage(repo, tmp_path, tag="bad")
    assert r.returncode == 3 and "REFUSED" in r.stderr and bad.split("/")[-1] in r.stderr


def test_stage_refuses_data_files_from_client_folders_and_non_chat_rows(repo, tmp_path):
    cases = tmp_path / "data" / "cases"
    cases.mkdir(parents=True)
    for f in ("train.jsonl", "dev.jsonl"):
        (cases / f).write_text(ROW)
    r = stage(repo, tmp_path, data=cases)
    assert r.returncode == 3 and "client data" in r.stderr
    (tmp_path / "ft" / "dev.jsonl").write_text('{"facts": "raw client text"}\n')
    r = stage(repo, tmp_path)
    assert r.returncode == 3 and "not a chat dataset" in r.stderr
    (tmp_path / "ft" / "dev.jsonl").unlink()
    assert stage(repo, tmp_path).returncode == 2


def test_fetch_verifies_checksums_archives_and_frees_home(tmp_path):
    import hashlib

    home = tmp_path / "adahome"
    run_dir = home / "vakeel_qlora/out/run1"
    (run_dir / "adapter").mkdir(parents=True)
    w = b"weights"
    (run_dir / "adapter/adapter_model.safetensors").write_bytes(w)
    (run_dir / "adapter/adapter_config.json").write_text("{}")
    sums = {"adapter_model.safetensors": hashlib.sha256(w).hexdigest(), "adapter_config.json": hashlib.sha256(b"{}").hexdigest()}
    (run_dir / "epoch.json").write_text(json.dumps({"epoch": 2, "final": True, "sha256": sums}))
    env = dict(LOCAL_ADA=home, SHARE1_DIR=tmp_path / "share1", DEST=tmp_path / "models/adapters", REPO=tmp_path)
    r = run(FETCH, "1", **env)
    assert r.returncode == 0, r.stderr + r.stdout
    assert (tmp_path / "models/adapters/run1/adapter/adapter_model.safetensors").read_bytes() == w
    assert (tmp_path / "share1/run1/adapter/adapter_model.safetensors").read_bytes() == w
    assert not run_dir.exists(), "the NFS copy is freed after both copies verified"


def test_fetch_detects_a_corrupt_adapter_and_skips_missing_runs(tmp_path):
    home = tmp_path / "adahome"
    run_dir = home / "vakeel_qlora/out/run0"
    (run_dir / "adapter").mkdir(parents=True)
    (run_dir / "adapter/adapter_model.safetensors").write_bytes(b"bad")
    (run_dir / "epoch.json").write_text(json.dumps({"epoch": 1, "final": False, "sha256": {"adapter_model.safetensors": "0" * 64}}))
    env = dict(LOCAL_ADA=home, SHARE1_DIR=tmp_path / "share1", DEST=tmp_path / "m", REPO=tmp_path)
    assert run(FETCH, "0", **env).returncode != 0
    assert run_dir.exists() and not (tmp_path / "m/run0").exists()
    r = run(FETCH, "2", **env)
    assert r.returncode == 1 and "no adapter on Ada yet" in r.stderr
