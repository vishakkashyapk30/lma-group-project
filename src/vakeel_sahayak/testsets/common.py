"""Shared test-set utilities and manifest format (plan §15.2)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TestSetManifest(BaseModel):
    """Description of a constructed test set."""

    __test__ = False  # not a pytest class

    set_id: str  # T1..T9
    size: int
    answers_from: str
    used_for: list[str] = Field(default_factory=list)
    path: str
    details: dict[str, Any] = Field(default_factory=dict)  # per-court, per-script and coverage statistics, split sizes, notes


def write_manifest(manifest: TestSetManifest, out_dir: str) -> None:
    """Write manifest.json next to the data (the directory is created when missing).

    Args:
        manifest: see behaviour
        out_dir: see behaviour
    """
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.json").write_text(manifest.model_dump_json(indent=1), encoding="utf-8")


def faker_names(seed: int, n: int, locale: str = "en_IN") -> list[str]:
    """Synthetic Indian names (Faker) for companion documents and leak tests.

    Args:
        seed: sequence seed; the same seed always gives the same sequence, and a longer request extends a shorter one
        n: how many distinct names
        locale: Faker locale ("en_IN" Latin names, "hi_IN" Devanagari names)

    Returns:
        Names.
    """
    from faker import Faker

    fake = Faker(locale)
    fake.seed_instance(seed)
    names: list[str] = []
    seen: set[str] = set()
    while len(names) < n:
        name = fake.name().strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def sha256_file(path: str | Path) -> str:
    """SHA-256 (hex) of a file's bytes; used for the source hashes in manifests."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rows_to_file(path: str | Path, rows: list[dict[str, Any]]) -> None:
    """Write rows as UTF-8 JSON lines with sorted keys and no trailing spaces (byte-identical for identical rows)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def rows_from_file(path: str | Path) -> list[dict[str, Any]]:
    """Read UTF-8 JSON lines (blank lines skipped); a missing file is a FileNotFoundError."""
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def load_t1_cases(t1_dir: str | Path, *, open_only: bool = True) -> list[dict[str, Any]]:
    """The T1 cases a derived set may be built from: `cases.jsonl`, restricted to the open part when `manifest_open.json` exists.

    The blind slice stays sealed (docs/evaluation-plan.md 2.6): its ids are not in `manifest_open.json`, so sets built on T1 never touch them.
    With no `manifest_open.json` (a fixture directory, a partial build) every case is returned.

    Args:
        t1_dir: the T1 output directory
        open_only: False returns all cases (only for code that is itself part of the T1 build)

    Returns:
        Case rows in file order.
    """
    base = Path(t1_dir)
    cases = rows_from_file(base / "cases.jsonl")
    open_manifest = base / "manifest_open.json"
    if open_only and open_manifest.exists():
        keep = set(json.loads(open_manifest.read_text(encoding="utf-8")).get("case_ids") or [])
        if keep:
            cases = [c for c in cases if c["case_id"] in keep]
    return cases


def g3_fields(case: dict[str, Any]) -> dict[str, Any]:
    """The G3 field values of a T1 case, for both shapes: flat (`gold.G3.arrest_date`) and the builder's (`gold.G3.fields.sections`)."""
    g3 = (case.get("gold") or {}).get("G3") or {}
    nested = g3.get("fields")
    return dict(nested) if isinstance(nested, dict) else dict(g3)
