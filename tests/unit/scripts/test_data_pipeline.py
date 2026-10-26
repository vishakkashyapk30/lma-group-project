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
    raw = data / "raw"
    for rel, body in {
        "open_india_law/judgments/delhi/part-0.parquet": b"PAR1",
        "open_india_law/legislation/in_central_legislation.parquet": b"PAR1",
        "open_india_law/sc_metadata.jsonl": b'{"a": 1}\n',
        "open_india_law/SHA256SUMS.json": b"{}",
        "open_india_law/fetch.log": b"log\n",
        "open_india_law/api_key.txt": b"never bundled",
        "ipc2bns_verify/README.md": b"readme",
    }.items():
        (raw / rel).parent.mkdir(parents=True, exist_ok=True)
        (raw / rel).write_bytes(body)
    (data / "cases" / "c1").mkdir(parents=True)
    (data / "cases" / "c1" / "facts.json").write_text("{}", encoding="utf-8")
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


def _bundle(tmp_path, extra=None):
    data = make_data(tmp_path)
    out = tmp_path / "bundle"
    env = {"VS_DATA_DIR": str(data), "VS_MODELS_DIR": str(tmp_path / "nomodels"), **(extra or {})}
    p = run(["bash", "scripts/data_bundle.sh", str(out)], env)
    assert p.returncode == 0, p.stderr
    return data, out, env, p


def _names(out, pattern, flags="-tf"):
    return subprocess.run(
        f"cat {out}/{pattern} | tar {flags} -", shell=True, capture_output=True, text=True, check=True
    ).stdout


def test_bundle_builds_a_raw_archive_with_sources_audio_and_exclusions(tmp_path):
    data, out, _, _ = _bundle(tmp_path)
    names = _names(out, "raw.tar.part-*")
    assert (
        "raw/open_india_law/judgments/delhi/part-0.parquet" in names and "raw/open_india_law/sc_metadata.jsonl" in names
    )
    assert "raw/ipc2bns_verify/README.md" in names and "raw/kathbath/hindi/test_known/audio/a.m4a" in names
    assert "raw/MANIFEST.json" in names and "raw/open_india_law/SHA256SUMS.json" in names
    assert "api_key" not in names and "cases" not in names and "interim" not in names and "stores" not in names
    assert "raw/open_india_law" not in _names(out, "data.tar.gz.part-*", "-tzf")
    sums = (out / "SHA256SUMS").read_text()
    assert "raw.tar.part-000" in sums and "data.tar.gz.part-000" in sums
    assert subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=out, check=False).returncode == 0
    m = json.loads((out / "bundle_manifest.json").read_text())
    assert (
        m["raw"]["files"] == 10 and m["raw"]["parts"] == 1 and m["archives"]["raw"]["parts"] == 1
    )  # api_key.txt left out
    assert (
        m["raw"]["folders"]["open_india_law"]["files"] == 5 and "interim" in m["folders"] and "raw" not in m["folders"]
    )
    assert (out / ".state-raw").is_file()


def test_bundle_is_resumable_and_rebuilds_a_changed_archive(tmp_path):
    data, out, env, _ = _bundle(tmp_path)
    before = {p.name: p.stat().st_mtime_ns for p in out.glob("*.part-*")}
    p = run(["bash", "scripts/data_bundle.sh", str(out)], env)
    assert p.returncode == 0 and p.stdout.count("sources unchanged") == 2, p.stdout
    assert before == {x.name: x.stat().st_mtime_ns for x in out.glob("*.part-*")}
    (data / "raw" / "ipc2bns_verify" / "new.csv").write_text("x", encoding="utf-8")  # only the raw source list changes
    p = run(["bash", "scripts/data_bundle.sh", str(out)], env)
    assert (
        p.returncode == 0
        and "data archive: sources unchanged" in p.stdout
        and "raw archive: sources unchanged" not in p.stdout
    )
    assert "raw/ipc2bns_verify/new.csv" in _names(out, "raw.tar.part-*")
    q = run(["bash", "scripts/data_bundle.sh", str(out)], {**env, "RAW": "0"})
    assert q.returncode == 0 and not list(out.glob("raw.tar.part-*"))


def test_install_defaults_to_both_archives_and_skips_raw_on_request(tmp_path):
    data, out, _, _ = _bundle(tmp_path)
    full = tmp_path / "full"
    q = run(["bash", "scripts/data_install.sh", str(out)], {"VS_DATA_DIR": str(full)})
    assert q.returncode == 0, q.stderr + q.stdout
    assert (full / "raw/open_india_law/judgments/delhi/part-0.parquet").is_file()
    assert (full / "raw/kathbath/hindi/test_known/audio/a.m4a").is_file() and not (
        full / "raw/open_india_law/api_key.txt"
    ).exists()
    assert json.loads((full / "bundle_manifest.json").read_text())["raw"]["parts"] == 1
    again = run(
        ["bash", "scripts/data_install.sh", str(out)], {"VS_DATA_DIR": str(full)}
    )  # idempotent: refuses, changes nothing
    assert again.returncode == 1 and "refusing to overwrite" in again.stderr
    assert run(["bash", "scripts/data_install.sh", "--force", str(out)], {"VS_DATA_DIR": str(full)}).returncode == 0
    lean = tmp_path / "lean"
    q = run(["bash", "scripts/data_install.sh", str(out)], {"VS_DATA_DIR": str(lean), "RAW": "0"})
    assert q.returncode == 0, q.stderr + q.stdout
    assert (
        (lean / "stores").is_dir()
        and not (lean / "raw" / "open_india_law").exists()
        and (lean / "raw" / "MANIFEST.json").is_file()
    )
    c = run([sys.executable, "scripts/_data_check.py", "--data", str(lean), "--models", str(tmp_path / "m")])
    assert c.returncode == 0 and "raw/open_india_law/judgments" in c.stdout and "MISSING" in c.stdout
    assert (
        run(
            [
                sys.executable,
                "scripts/_data_check.py",
                "--data",
                str(lean),
                "--models",
                str(tmp_path / "m"),
                "--require-raw",
            ]
        ).returncode
        == 1
    )
    # add the raw archive later, without touching the derived data
    q = run(["bash", "scripts/data_install.sh", "--only-raw", str(out)], {"VS_DATA_DIR": str(lean)})
    assert q.returncode == 0, q.stderr + q.stdout
    assert (
        run(
            [
                sys.executable,
                "scripts/_data_check.py",
                "--data",
                str(lean),
                "--models",
                str(tmp_path / "m"),
                "--require-raw",
            ]
        ).returncode
        == 0
    )


def test_install_verifies_checksums_of_the_raw_archive(tmp_path):
    _, out, _, _ = _bundle(tmp_path)
    part = out / "raw.tar.part-000"
    part.write_bytes(part.read_bytes() + b"x")
    target = tmp_path / "t"
    q = run(["bash", "scripts/data_install.sh", str(out)], {"VS_DATA_DIR": str(target)})
    assert q.returncode == 1 and "checksum verification FAILED" in q.stderr and not (target / "interim").exists()
    # without the raw archive the damaged raw part is not needed
    assert run(["bash", "scripts/data_install.sh", "--no-raw", str(out)], {"VS_DATA_DIR": str(target)}).returncode == 0
