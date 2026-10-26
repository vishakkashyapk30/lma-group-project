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
