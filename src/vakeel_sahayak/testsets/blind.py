"""The sealed blind slice (docs/evaluation-plan.md 2.6 and 5.8): ids stored as hashes, one explicit opening, one lock file.

* `seal_blind` writes `manifest_blind.json` (hashes only, plus the hash of the sorted hashes that goes into docs/preregistration.md) and
  `blind_sealed.json` (the ids; read it only through `open_blind`).
* `open_blind(out_dir, confirm=True)` returns the ids ONCE: it refuses without the explicit flag, without the freeze tag in git, and when the lock file
  already exists; it writes the lock (date, git SHA). The lock path is `data/eval/blind.lock` (README contract C6).
* `assert_may_score_blind` is the check a scoring entry point makes before it touches a blind id.
The driver only RUNS cases (the runner stores outputs for all 200); scoring blind ids is a separate, gated step.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

FREEZE_TAG = "eval-freeze-v1"
SALT = "vakeel-sahayak-t1-blind-v1"
REPO = Path(__file__).resolve().parents[3]


class BlindSliceError(PermissionError):
    """The blind slice may not be opened or scored now."""


def blind_hash(case_id: str) -> str:
    """Salted SHA-256 (hex) of a case id: what the manifests store instead of the id."""
    return hashlib.sha256(f"{SALT}|{case_id}".encode()).hexdigest()


def set_hash(hashes: list[str]) -> str:
    """One hash over the sorted per-id hashes (for the pre-registration)."""
    return hashlib.sha256("\n".join(sorted(hashes)).encode()).hexdigest()


def lock_path() -> Path:
    """`data/eval/blind.lock` (`VS_DATA_DIR` rebases `data/`)."""
    return Path(os.environ.get("VS_DATA_DIR") or REPO / "data") / "eval" / "blind.lock"


def seal_blind(case_ids: list[str], out_dir: str) -> dict[str, object]:
    """Write the hashed manifest and the sealed id file; returns the hashed manifest."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    hashes = sorted(blind_hash(c) for c in case_ids)
    manifest = {"slice": "blind", "n": len(hashes), "hashes": hashes, "set_hash": set_hash(hashes), "salt_id": SALT}
    (out / "manifest_blind.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (out / "blind_sealed.json").write_text(json.dumps({"sealed": True, "ids": sorted(case_ids)}), encoding="utf-8")
    return manifest


def freeze_tag_exists(tag: str = FREEZE_TAG) -> bool:
    """True when the git tag exists in this repository."""
    try:
        done = subprocess.run(["git", "tag", "--list", tag], cwd=REPO, capture_output=True, text=True, timeout=10)
        return tag in done.stdout.split()
    except Exception:  # noqa: BLE001
        return False


def assert_may_score_blind(*, tag: str = FREEZE_TAG, lock: Path | None = None, check_tag: bool = True) -> None:
    """Raise BlindSliceError unless the freeze tag exists and the blind slice has not been opened yet."""
    if (lock or lock_path()).exists():
        raise BlindSliceError("the blind slice has already been opened once (lock file present); it is scored once")
    if check_tag and not freeze_tag_exists(tag):
        raise BlindSliceError(f"git tag {tag!r} does not exist: freeze the code and the pre-registration before scoring the blind slice")


def open_blind(out_dir: str, *, confirm: bool = False, tag: str = FREEZE_TAG, lock: Path | None = None, check_tag: bool = True) -> list[str]:
    """Return the blind case ids and write the lock; one opening only.

    Args:
        out_dir: the T1 directory holding `blind_sealed.json` and `manifest_blind.json`
        confirm: the explicit flag (`--open-blind` on the CLI); without it nothing is read
        tag: freeze tag that must exist
        lock: lock file path (default `data/eval/blind.lock`)
        check_tag: False only in tests

    Raises:
        BlindSliceError: no flag, no tag, already opened, or the sealed ids do not match the hashed manifest.
    """
    if not confirm:
        raise BlindSliceError("opening the blind slice needs the explicit flag (confirm=True / --open-blind)")
    lock = lock or lock_path()
    assert_may_score_blind(tag=tag, lock=lock, check_tag=check_tag)
    out = Path(out_dir)
    ids = list(json.loads((out / "blind_sealed.json").read_text(encoding="utf-8"))["ids"])
    manifest = json.loads((out / "manifest_blind.json").read_text(encoding="utf-8"))
    if set_hash([blind_hash(i) for i in ids]) != manifest["set_hash"]:
        raise BlindSliceError("the sealed ids do not match the hashed manifest")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001
        sha = "unknown"
    lock.write_text(json.dumps({"opened_at": datetime.now(timezone.utc).isoformat(), "git_sha": sha, "n": len(ids)}), encoding="utf-8")
    return ids
