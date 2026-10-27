"""scripts/sweep_collect.sh: safe unpacking of a Sarvam sweep tarball."""

from __future__ import annotations

import io
import json
import subprocess
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
REF = {"prompt_hash": "p1", "git_sha": "abc", "nli": {"backend": "x"}}


def manifest(**kw):
    return {"system": "s3", "gold_source": "agreed", "prompt_hash": "p1", "git_sha": "abc", "nli": {"backend": "x"}, "models": {"llm_backend": "sarvam"}, **kw}


def make_tar(path: Path, members: dict[str, bytes], links: dict[str, str] | None = None):
    with tarfile.open(path, "w:gz") as tf:
        for name, data in members.items():
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
        for name, target in (links or {}).items():
            ti = tarfile.TarInfo(name)
            ti.type = tarfile.SYMTYPE
            ti.linkname = target
            tf.addfile(ti)


def collect(tmp_path, tar, extra_env=None):
    ref = tmp_path / "ref.json"
    ref.write_text(json.dumps(REF))
    env = {"PATH": "/usr/bin:/bin", "SWEEP_TARGET": str(tmp_path / "target"), "SWEEP_REF_MANIFEST": str(ref), **(extra_env or {})}
    return subprocess.run(["bash", str(REPO / "scripts/sweep_collect.sh"), str(tar)], cwd=REPO, env=env, capture_output=True, text=True)


def good(tmp_path, **mkw):
    tar = tmp_path / "p.tar.gz"
    make_tar(tar, {"sarvam_block/outputs/s3/MANIFEST.json": json.dumps(manifest(**mkw)).encode(), "sarvam_block/outputs/s3/t1dev-000.json": b'{"case_id": "t1dev-000"}'})
    return tar


def test_good_package_is_unpacked(tmp_path):
    r = collect(tmp_path, good(tmp_path))
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "target/outputs/s3/t1dev-000.json").is_file()


def test_path_traversal_and_links_are_refused(tmp_path):
    tar = tmp_path / "bad.tar.gz"
    make_tar(tar, {"sarvam_block/../../evil.json": b"{}"})
    r = collect(tmp_path, tar)
    assert r.returncode != 0 and "REFUSED" in r.stderr and not (tmp_path / "target").exists()
    tar2 = tmp_path / "bad2.tar.gz"
    make_tar(tar2, {}, links={"sarvam_block/outputs/s3/t1dev-000.json": "/etc/passwd"})
    assert collect(tmp_path, tar2).returncode != 0


def test_unknown_names_and_keys_are_refused(tmp_path):
    tar = tmp_path / "n.tar.gz"
    make_tar(tar, {"sarvam_block/.env": b"SARVAM_API_KEY=x"})
    assert collect(tmp_path, tar).returncode != 0
    tar2 = tmp_path / "k.tar.gz"
    make_tar(tar2, {"sarvam_block/outputs/s3/MANIFEST.json": b'{"k": "sk-abcdefghijklmnopqrstuv"}'})
    assert "key-like" in collect(tmp_path, tar2).stderr


def test_manifest_checks(tmp_path):
    assert "gold_source" in collect(tmp_path, good(tmp_path, gold_source="rule")).stderr
    assert "prompt_hash" in collect(tmp_path, good(tmp_path, prompt_hash="zzz")).stderr
    assert "git_sha" in collect(tmp_path, good(tmp_path, git_sha="other")).stderr
    assert collect(tmp_path, good(tmp_path, git_sha="other"), {"ALLOW_CODE_MISMATCH": "1"}).returncode == 0


# ---- the OpenAI block (scripts/sweep_openai_block.sh) -------------------------------------------------------------------------------------------------------

def openai_tar(tmp_path, backend="openai", top="openai_block", **mkw):
    tar = tmp_path / "o.tar.gz"
    m = manifest(**mkw)
    m["models"] = {"llm_backend": backend}
    make_tar(tar, {f"{top}/outputs/a2/MANIFEST.json": json.dumps(m).encode(), f"{top}/outputs/a2/t1dev-000.json": b'{"case_id": "t1dev-000"}', f"{top}/PACK_INFO.json": b"{}"})
    return tar


def test_openai_package_is_unpacked_with_the_same_checks(tmp_path):
    r = collect(tmp_path, openai_tar(tmp_path))
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "target/outputs/a2/t1dev-000.json").is_file()
    assert "prompt_hash" in collect(tmp_path, openai_tar(tmp_path, prompt_hash="zzz")).stderr
    assert "git_sha" in collect(tmp_path, openai_tar(tmp_path, git_sha="other")).stderr
    assert "gold_source" in collect(tmp_path, openai_tar(tmp_path, gold_source="rule")).stderr


def test_openai_package_with_a_sarvam_manifest_is_refused(tmp_path):
    r = collect(tmp_path, openai_tar(tmp_path, backend="sarvam"))
    assert r.returncode != 0 and "expected 'openai'" in r.stderr


def test_mixed_or_unknown_top_directories_are_refused(tmp_path):
    tar = tmp_path / "m.tar.gz"
    make_tar(tar, {"sarvam_block/outputs/s3/MANIFEST.json": b"{}", "openai_block/outputs/a2/MANIFEST.json": b"{}"})
    assert "exactly one" in collect(tmp_path, tar).stderr
    tar2 = tmp_path / "u.tar.gz"
    make_tar(tar2, {"other_block/outputs/a2/MANIFEST.json": b"{}"})
    assert "REFUSED" in collect(tmp_path, tar2).stderr


def run_block(args, env_extra=None, cwd=REPO):
    import os

    env = {**os.environ, **(env_extra or {})}
    env.pop("OPENAI_API_KEY", None)
    return subprocess.run(["bash", str(REPO / "scripts/sweep_openai_block.sh"), *args], cwd=cwd, env=env, capture_output=True, text=True)


def test_openai_block_plan_lists_only_phase_two_openai_arms():
    r = run_block(["plan"], {"VS_MODELS": "offline"})
    assert r.returncode == 0, r.stderr
    rows = [ln.split()[:3] for ln in r.stdout.splitlines()[2:] if ln[:1].isdigit()]
    assert rows and all(x[0] == "2" and x[1] == "openai" for x in rows)
    assert any(x[2] == "A2" for x in rows)


def test_openai_block_run_refuses_without_key_cap_or_pinned_tag(tmp_path):
    # a scratch copy of the script in a directory with no .env, no git and no key: nothing can reach a model
    import os
    import shutil

    (tmp_path / "scripts").mkdir()
    shutil.copy(REPO / "scripts/sweep_openai_block.sh", tmp_path / "scripts")
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "VS_OPENAI_CAP_USD")}
    run = lambda extra: subprocess.run(["bash", str(tmp_path / "scripts/sweep_openai_block.sh"), "run"], cwd=tmp_path, env={**env, **extra}, capture_output=True, text=True)  # noqa: E731
    assert "OPENAI_API_KEY is not set" in run({}).stderr
    assert "spend cap" in run({"OPENAI_API_KEY": "x"}).stderr
    assert "pinned tag" in run({"OPENAI_API_KEY": "x", "VS_OPENAI_CAP_USD": "1"}).stderr
    assert run_block(["bogus"]).returncode == 2


def test_openai_block_pack_keeps_only_small_files_and_refuses_keys(tmp_path):
    root = tmp_path / "dev_runs"
    arm = root / "outputs" / "a2"
    (arm / "_events").mkdir(parents=True)
    (arm / "MANIFEST.json").write_text(json.dumps(manifest()))
    (arm / "t1dev-000.json").write_text('{"case_id": "t1dev-000"}')
    (arm / "_events" / "t1dev-000.jsonl").write_text("prompt text")
    (root / "outputs" / "unrelated").mkdir()
    (root / "outputs" / "unrelated" / "t1dev-000.json").write_text("{}")
    r = run_block(["pack"], {"SWEEP_ROOT": str(root)})
    assert r.returncode == 0, r.stderr
    assert "hf upload Vakeel-Sahayak/vakeel-sahayak-data" in r.stdout and "sweep-runs/sweep-openai-" in r.stdout
    tars = list(root.glob("sweep-openai-*.tar.gz"))
    assert len(tars) == 1
    with tarfile.open(tars[0]) as tf:
        names = tf.getnames()
    assert "openai_block/outputs/a2/MANIFEST.json" in names and "openai_block/outputs/a2/t1dev-000.json" in names
    assert not any("_events" in n or "unrelated" in n for n in names)
    # the package it makes is accepted by the collector
    r2 = collect(tmp_path, tars[0], {"HOME": str(tmp_path)})
    assert "llm_backend" in r2.stderr  # the synthetic manifest says sarvam: the backend check, not the format check, refuses it
    (arm / "t1dev-001.json").write_text('{"k": "sk-abcdefghijklmnopqrstuv"}')
    assert "key-like" in run_block(["pack"], {"SWEEP_ROOT": str(root)}).stderr
