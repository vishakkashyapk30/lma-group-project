"""Teammate data pipeline scripts, offline, on a tiny synthetic data folder: `data_bundle.sh` -> `data_install.sh` -> `make data-check` / `make data`."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import _data_check  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("tar") is None, reason="needs bash and tar"
)


def make_data(root: Path, with_stores: bool = True) -> Path:
    data = root / "data"
    rows = {"interim/orders.jsonl": 3, "interim/statutes.jsonl": 2, "interim/concordance_edges.jsonl": 2, "interim/oil_metadata.jsonl": 3, "interim/hindi_native.jsonl": 2,
            "testsets/t1/cases.jsonl": 2, "testsets/t2/truth.jsonl": 2, "testsets/t3/updates.jsonl": 1, "testsets/t4/scenarios.jsonl": 1, "testsets/t5/cases.jsonl": 1,
            "testsets/t6/questions.jsonl": 1, "testsets/t8/utterances.jsonl": 1, "testsets/t9/strings.jsonl": 1, "gaps/statutes/crpc.jsonl": 1, "gaps/statutes/ndps.jsonl": 1,
            "gaps/statutes/first_schedule_ipc.jsonl": 1, "raw/kathbath/hindi/test_known/manifest.jsonl": 2, "raw/kathbath/hindi/test_known/transcription_n2w.txt": 2}  # fmt: skip
    for rel, n in rows.items():
        f = data / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("".join(json.dumps({"i": i}) + "\n" for i in range(n)), encoding="utf-8")
    (data / "interim" / "splits.json").write_text("{}", encoding="utf-8")
    (data / "raw" / "MANIFEST.json").write_text('{"datasets": {"x": {}}}', encoding="utf-8")
    (data / "raw" / "kathbath" / "hindi" / "test_known" / "audio").mkdir()
    (data / "raw" / "kathbath" / "hindi" / "test_known" / "audio" / "a.m4a").write_bytes(b"audio")
    if with_stores:
        for rel in _data_check.STORES:
            (data / "stores" / rel).parent.mkdir(parents=True, exist_ok=True)
            (data / "stores" / rel).write_bytes(b"sqlite")
    return data


def run(cmd, env_extra=None, cwd=ROOT):
    env = {k: v for k, v in os.environ.items() if k not in ("HF_TOKEN",)}
    env.update({"PY": sys.executable, **(env_extra or {})})
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def test_check_passes_on_a_complete_folder_and_lists_items(tmp_path):
    data = make_data(tmp_path)
    p = run([sys.executable, "scripts/_data_check.py", "--data", str(data), "--models", str(tmp_path / "m")])
    assert p.returncode == 0, p.stdout
    assert (
        "stores/law/statutes.sqlite" in p.stdout
        and "present" in p.stdout
        and "hindi_native" in p.stdout
        and "required missing: 0" in p.stdout
    )
    assert "models (T1)" in p.stdout  # listed, optional


def test_check_fails_when_a_required_item_is_missing_and_models_can_be_required(tmp_path):
    data = make_data(tmp_path)
    (data / "stores" / "law" / "statutes.sqlite").unlink()
    p = run([sys.executable, "scripts/_data_check.py", "--data", str(data), "--models", str(tmp_path / "m")])
    assert p.returncode == 1 and "MISSING" in p.stdout and "required missing: 1" in p.stdout
    (data / "stores" / "law" / "statutes.sqlite").write_bytes(b"x")
    assert (
        run([sys.executable, "scripts/_data_check.py", "--data", str(data), "--models", str(tmp_path / "m")]).returncode
        == 0
    )
    assert (
        run(
            [
                sys.executable,
                "scripts/_data_check.py",
                "--data",
                str(data),
                "--models",
                str(tmp_path / "m"),
                "--require-models",
            ]
        ).returncode
        == 1
    )


def test_bundle_install_roundtrip_with_counts(tmp_path):
    data = make_data(tmp_path)
    out = tmp_path / "bundle"
    p = run(
        ["bash", "scripts/data_bundle.sh", str(out)],
        {"VS_DATA_DIR": str(data), "VS_MODELS_DIR": str(tmp_path / "nomodels")},
    )
    assert p.returncode == 0, p.stderr
    manifest = json.loads((out / "bundle_manifest.json").read_text())
    assert (
        manifest["rows"]["interim/hindi_native.jsonl"] == 2
        and manifest["rows"]["raw/kathbath/hindi/test_known/manifest.jsonl"] == 2
    )
    names = subprocess.run(
        f"cat {out}/data.tar.gz.part-* | tar -tzf -", shell=True, capture_output=True, text=True, check=True
    ).stdout
    assert (
        "raw/kathbath/hindi/test_known/manifest.jsonl" in names
        and "audio/a.m4a" not in names
        and "bundle_manifest.json" in names
    )
    target = tmp_path / "target"
    q = run(["bash", "scripts/data_install.sh", str(out)], {"VS_DATA_DIR": str(target)})
    assert q.returncode == 0, q.stderr + q.stdout
    assert (target / "bundle_manifest.json").is_file() and (target / "interim" / "hindi_native.jsonl").is_file()
    c = run([sys.executable, "scripts/_data_check.py", "--data", str(target), "--models", str(tmp_path / "m")])
    assert c.returncode == 0 and "no data/bundle_manifest.json" not in c.stdout, c.stdout
    # a file lost after the install is caught against the bundle manifest
    (target / "testsets" / "t3" / "manifest.json").write_text("{}")  # extra file only prints a note
    (target / "interim" / "hindi_native.jsonl").write_text('{"i": 0}\n')
    c = run([sys.executable, "scripts/_data_check.py", "--data", str(target), "--models", str(tmp_path / "m")])
    assert c.returncode == 1 and "bundle manifest says 2" in c.stdout


def test_data_does_nothing_when_the_data_is_in_place(tmp_path):
    data = make_data(tmp_path)
    p = run(["bash", "scripts/data_ensure.sh"], {"VS_DATA_DIR": str(data)})
    assert p.returncode == 0 and "nothing to do" in p.stdout


def test_data_without_token_explains_both_options_and_fails(tmp_path):
    p = run(
        ["bash", "scripts/data_ensure.sh"],
        {"VS_DATA_DIR": str(tmp_path / "empty"), "HOME": str(tmp_path), "ENV_FILE": str(tmp_path / "no.env")},
    )
    assert p.returncode == 1
    assert "ask the owner" in p.stderr.lower() and "make datasets interim stores" in p.stderr and "HF_TOKEN" in p.stderr


def test_makefile_has_the_targets():
    p = subprocess.run(["make", "-n", "data", "data-check"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert p.returncode == 0 and "data_ensure.sh" in p.stdout and "_data_check.py" in p.stdout
