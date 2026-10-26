"""Fresh-clone behaviour of the teammate scripts, offline: placeholders are not data, the hf: path (a stub `hf` command) retries, resumes
and explains 401 and 403, `make setup` explains a missing Python, and no stale repository id or owner path is left in the tree."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from .test_data_pipeline import ROOT, _bundle, run

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("tar") is None, reason="needs bash and tar"
)
REPO = "Vakeel-Sahayak/vakeel-sahayak-data"
FAKE_HF = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG"
echo "TIMEOUTS $HF_HUB_DOWNLOAD_TIMEOUT $HF_HUB_ETAG_TIMEOUT token=${HF_TOKEN:+set}" >> "$FAKE_LOG"
if [ "$1 $2" = "auth whoami" ]; then
  [ "${FAKE_WHOAMI:-ok}" = ok ] && { echo "fakeuser"; exit 0; }
  echo "Invalid user token" >&2; exit 1
fi
[ "$1" = download ] || exit 0
probe=0; for a in "$@"; do [ "$a" = SHA256SUMS ] && probe=1; done
dest=""; prev=""; for a in "$@"; do [ "$prev" = --local-dir ] && dest="$a"; prev="$a"; done
mkdir -p "$dest"
if [ "$probe" = 1 ]; then
  [ -z "${FAKE_PROBE_ERR:-}" ] || { echo "$FAKE_PROBE_ERR" >&2; exit 1; }
  cp "$FAKE_BUNDLE/SHA256SUMS" "$dest/"; exit 0
fi
n=$(cat "$FAKE_COUNT" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$FAKE_COUNT"
if [ "$n" -le "${FAKE_FAILS:-0}" ]; then echo "ReadTimeout: connection timed out" >&2; exit 1; fi
echo "Fetching files: 100%|##########| 4/4"
for f in "$FAKE_BUNDLE"/*; do case "$(basename "$f")" in .state-*) continue;; esac; cp "$f" "$dest/"; done
"""


def fresh_data(root: Path) -> Path:
    """What `git clone` leaves in data/: .gitkeep placeholders and a README."""
    data = root / "freshdata"
    for d in ("cases", "interim", "raw", "stores", "testsets", "gaps", "eval"):
        (data / d).mkdir(parents=True)
        (data / d / ".gitkeep").write_text("")
    (data / "README.md").write_text("data notes")
    return data


def hf_env(tmp_path: Path, bundle: Path, **extra) -> dict:
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    hf = bindir / "hf"
    hf.write_text(FAKE_HF)
    hf.chmod(0o755)
    return {
        "HF_BIN": str(hf),
        "FAKE_BUNDLE": str(bundle),
        "FAKE_LOG": str(tmp_path / "hf.log"),
        "FAKE_COUNT": str(tmp_path / "hf.count"),
        "HF_RETRY_SLEEP": "0",
        "HOME": str(tmp_path),
        "ENV_FILE": str(tmp_path / "none.env"),
        "TMPDIR": str(tmp_path),
        **extra,
    }


def test_install_ignores_gitkeep_and_readme_placeholders(tmp_path):
    _, out, _, _ = _bundle(tmp_path)
    data = fresh_data(tmp_path)
    q = run(["bash", "scripts/data_install.sh", str(out)], {"VS_DATA_DIR": str(data)})
    assert q.returncode == 0, q.stderr + q.stdout
    assert (data / "interim" / "orders.jsonl").is_file() and (data / "interim" / ".gitkeep").exists()
    # real data still clashes, and a hidden folder of a clone does not count
    again = run(["bash", "scripts/data_install.sh", str(out)], {"VS_DATA_DIR": str(data)})
    assert again.returncode == 1 and "refusing to overwrite" in again.stderr


def test_a_dot_directory_in_the_data_path_does_not_hide_real_data(tmp_path):
    _, out, _, _ = _bundle(tmp_path)
    data = tmp_path / ".hidden" / "data"
    for d in ("interim", "stores"):
        (data / d).mkdir(parents=True)
    (data / "stores" / "x.sqlite").write_text("data")
    q = run(["bash", "scripts/data_install.sh", str(out)], {"VS_DATA_DIR": str(data)})
    assert q.returncode == 1 and "existing stores in" in q.stderr


def test_fresh_clone_counts_as_nothing_installed(tmp_path):
    data = fresh_data(tmp_path)
    c = run([sys.executable, "scripts/_data_check.py", "--data", str(data), "--models", str(tmp_path / "m")])
    assert c.returncode == 1 and "nothing is installed yet" in c.stdout and "make data" in c.stdout
    p = run(
        ["bash", "scripts/data_ensure.sh"],
        {"VS_DATA_DIR": str(data), "HOME": str(tmp_path), "ENV_FILE": str(tmp_path / "no.env")},
    )
    assert p.returncode == 1 and "nothing to do" not in p.stdout and "HF_TOKEN" in p.stderr


def test_hf_install_retries_resumes_and_shows_progress(tmp_path):
    _, out, _, _ = _bundle(tmp_path)
    data = fresh_data(tmp_path)
    env = hf_env(tmp_path, out, FAKE_FAILS="2", HF_TOKEN="hf_secretsecret123", VS_DATA_DIR=str(data))
    q = run(["bash", "scripts/data_install.sh", f"hf:{REPO}"], env)
    assert q.returncode == 0, q.stderr + q.stdout
    assert "attempt 1 of 3 failed" in q.stderr and "attempt 2 of 3 failed" in q.stderr
    assert "Fetching files: 100%" in q.stdout + q.stderr  # progress is not sent to /dev/null
    log = (tmp_path / "hf.log").read_text()
    assert "auth whoami" in log and "--max-workers 2" in log and "TIMEOUTS 60 30 token=set" in log
    assert (data / "stores" / "law" / "statutes.sqlite").is_file()
    assert "secretsecret" not in q.stdout + q.stderr


def test_hf_install_gives_up_after_three_tries_with_advice(tmp_path):
    _, out, _, _ = _bundle(tmp_path)
    env = hf_env(tmp_path, out, FAKE_FAILS="9", HF_TOKEN="hf_x1234567890", VS_DATA_DIR=str(tmp_path / "d"))
    q = run(["bash", "scripts/data_install.sh", f"hf:{REPO}"], env)
    assert q.returncode == 1 and (tmp_path / "hf.count").read_text().strip() == "3"
    assert "failed after 3 tries" in q.stderr and "TMPDIR" in q.stderr


def test_hf_install_timeouts_can_be_overridden(tmp_path):
    _, out, _, _ = _bundle(tmp_path)
    env = hf_env(
        tmp_path, out, HF_TOKEN="hf_x1234567890", HF_HUB_DOWNLOAD_TIMEOUT="200", VS_DATA_DIR=str(tmp_path / "d")
    )
    assert run(["bash", "scripts/data_install.sh", "--no-raw", f"hf:{REPO}"], env).returncode == 0
    log = (tmp_path / "hf.log").read_text()
    assert "TIMEOUTS 200 30" in log and "--exclude raw.tar.part-*" in log


def test_hf_install_without_a_token_says_what_to_do(tmp_path):
    _, out, _, _ = _bundle(tmp_path)
    env = hf_env(tmp_path, out, VS_DATA_DIR=str(tmp_path / "d"))
    q = run(["bash", "scripts/data_install.sh", f"hf:{REPO}"], env)
    assert q.returncode == 1 and "no Hugging Face token" in q.stderr and "hf auth login" in q.stderr
    assert not (tmp_path / "hf.count").exists()  # nothing was downloaded


def test_hf_install_with_a_bad_token_stops_before_the_big_download(tmp_path):
    _, out, _, _ = _bundle(tmp_path)
    env = hf_env(tmp_path, out, FAKE_WHOAMI="bad", HF_TOKEN="hf_badbadbad123", VS_DATA_DIR=str(tmp_path / "d"))
    q = run(["bash", "scripts/data_install.sh", f"hf:{REPO}"], env)
    assert q.returncode == 1 and "whoami failed" in q.stderr and "Vakeel-Sahayak" in q.stderr
    assert "badbadbad" not in q.stdout + q.stderr and not (tmp_path / "hf.count").exists()


@pytest.mark.parametrize(
    "err", ["403 Client Error: Forbidden", "401 Client Error: Unauthorized", "404 Client Error: Not Found"]
)
def test_hf_install_explains_organisation_access_errors(tmp_path, err):
    _, out, _, _ = _bundle(tmp_path)
    env = hf_env(tmp_path, out, FAKE_PROBE_ERR=err, HF_TOKEN="hf_x1234567890", VS_DATA_DIR=str(tmp_path / "d"))
    q = run(["bash", "scripts/data_install.sh", f"hf:{REPO}"], env)
    assert q.returncode == 1 and "member of the Hugging Face organisation" in q.stderr and "Org permissions" in q.stderr
    assert not (tmp_path / "hf.count").exists()


def test_make_data_with_a_cached_login_but_no_token_goes_to_the_installer(tmp_path):
    _, out, _, _ = _bundle(tmp_path)
    (tmp_path / ".cache" / "huggingface").mkdir(parents=True)
    (tmp_path / ".cache" / "huggingface" / "token").write_text("hf_cached123456")
    env = hf_env(tmp_path, out, VS_DATA_DIR=str(fresh_data(tmp_path)), BUNDLE_REPO=REPO)
    env.pop("ENV_FILE")
    env["ENV_FILE"] = str(tmp_path / "none.env")
    p = run(["bash", "scripts/data_ensure.sh"], env)
    assert p.returncode == 0, p.stderr + p.stdout
    assert f"hf:{REPO}" in p.stdout and "installed." in p.stdout


def test_token_is_read_from_env_file_but_an_empty_line_is_ignored(tmp_path):
    _, out, _, _ = _bundle(tmp_path)
    env = hf_env(tmp_path, out, VS_DATA_DIR=str(tmp_path / "d"))
    (tmp_path / "e.env").write_text("HF_TOKEN=\n")
    env["ENV_FILE"] = str(tmp_path / "e.env")
    assert run(["bash", "scripts/data_install.sh", f"hf:{REPO}"], env).returncode == 1
    (tmp_path / "e.env").write_text("export HF_TOKEN='hf_fromfile12345'\n")
    assert run(["bash", "scripts/data_install.sh", f"hf:{REPO}"], env).returncode == 0
    assert "token=set" in (tmp_path / "hf.log").read_text()


def test_setup_explains_a_missing_or_old_python(tmp_path):
    root = tmp_path / "clone"  # a copy of the script in a folder without .venv, so the real checkout is never touched
    (root / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "setup_dev.sh", root / "scripts" / "setup_dev.sh")
    old = tmp_path / "python-old"
    old.write_text("#!/bin/sh\nexit 1\n")
    old.chmod(0o755)
    for python in ("definitely-not-python", str(old)):
        p = subprocess.run(
            ["bash", "scripts/setup_dev.sh"],
            cwd=root,
            env={**os.environ, "PYTHON": python},
            capture_output=True,
            text=True,
            check=False,
        )
        assert p.returncode == 1 and "missing or older than 3.10" in p.stderr, p.stderr
    assert not (root / ".venv").exists()
    tools = tmp_path / "tools"  # only bash and dirname: no Python at all
    tools.mkdir()
    for tool in ("bash", "dirname"):
        (tools / tool).symlink_to(shutil.which(tool))
    bare = subprocess.run(
        [str(tools / "bash"), "scripts/setup_dev.sh"],
        cwd=root,
        env={"PATH": str(tools), "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert bare.returncode == 1 and "no Python 3.10 or newer found" in bare.stderr


def test_make_targets_without_a_venv_say_make_setup(tmp_path):
    for target in ("smoke", "test-collect", "data-check", "models-dry-run"):
        p = subprocess.run(
            ["make", f"PY={tmp_path}/none/python", target], cwd=ROOT, capture_output=True, text=True, check=False
        )
        assert p.returncode != 0 and "make setup" in p.stderr and "Traceback" not in p.stderr, target
    h = subprocess.run(["make", "help"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert h.returncode == 0 and "setup-full" in h.stdout and "data-install" in h.stdout
    n = subprocess.run(["make", "-n", "setup"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert "scripts/setup_dev.sh" in n.stdout and "hooks" in n.stdout


def tracked_files() -> list[Path]:
    p = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        pytest.skip("not a git checkout")
    return [ROOT / f for f in p.stdout.splitlines() if (ROOT / f).is_file()]


def test_no_stale_dataset_repo_id_in_the_tree():
    stale = re.compile(r"vishakkashyapk/|hf:(?!Vakeel-Sahayak/vakeel-sahayak-data)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]*data")
    me = Path(__file__).resolve()
    bad = []
    for f in tracked_files():
        if (
            f.resolve() == me
            or f.suffix in {".png", ".jpg", ".pdf", ".ico", ".woff2", ".lock", ".svg"}
            or f.stat().st_size > 2_000_000
        ):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if stale.search(text):
            bad.append(str(f.relative_to(ROOT)))
    assert not bad, bad


def test_no_owner_home_paths_in_code_or_scripts():
    bad = []
    for f in tracked_files():
        rel = f.relative_to(ROOT)
        if rel.parts[0] not in {"scripts", "src", "configs", "docker", "tests"} and rel.name not in {
            "Makefile",
            "compose.yaml",
        }:
            continue
        if f.resolve() == Path(__file__).resolve() or f.suffix in {".png", ".jpg", ".pdf", ".parquet", ".sqlite"}:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if re.search(r"/home/vishak|/tmp/claude", text):
            bad.append(str(rel))
    assert not bad, bad


def test_scripts_are_executable_and_env_example_is_complete():
    for f in (ROOT / "scripts").glob("*.sh"):
        assert f.stat().st_mode & stat.S_IXUSR, f"{f.name} lacks the exec bit"
    ignored = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT, check=False).returncode
    assert ignored == 0
    names = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", (ROOT / ".env.example").read_text(), flags=re.M))
    for needed in (
        "HF_TOKEN",
        "SARVAM_API_KEY",
        "OPENAI_API_KEY",
        "VS_EXTERNAL",
        "VS_MODELS",
        "VS_LLM_BACKEND",
        "VS_DATA_DIR",
    ):
        assert needed in names, needed
    for line in (ROOT / ".env.example").read_text().splitlines():
        m = re.match(r"^([A-Z_]*(KEY|TOKEN|SECRET))=(.+)$", line)
        assert not m, f"a secret-like variable has a value in .env.example: {m.group(1)}"
