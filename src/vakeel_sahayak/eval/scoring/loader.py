"""Load driver run directories and the T1 gold of the requested source and slice; refuse the sealed blind slice unless the rules of 5.8 are met.

Run directory layouts understood (any depth): a directory holding `MANIFEST.json` and one `<case_id>.json` per case is one run of `manifest["system"]`; a
sibling or parent name `<system>__run<k>` marks repeat k (no suffix means run 1). `_events/` is read only for the retrieved documents. Directories of
Rights Radar scenario records (`{rule, predicted, designed}`, `eval/features/f3_rights_radar.py`) are collected as T4 arms.

Slices: `dev` (the 50 dev orders, `dev.jsonl`, no lock needed), `open` (the 120 open test orders, `manifest_open.json`), `blind` (the 80 sealed orders):
the blind slice goes through `testsets.blind.open_blind`, which refuses without the explicit flag, without the freeze git tag, and when the lock file exists,
and writes the lock when it opens (one opening only).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vakeel_sahayak.testsets import gold_source as gs

SLICES = ("dev", "open", "blind")
_RUN_SUFFIX = re.compile(r"^(?P<system>.+?)__run(?P<k>\d+)$")
MANIFEST_NAMES = ("MANIFEST.json", "manifest.json")


@dataclass
class RunSet:
    """One run (one directory) of one system."""

    system: str
    run: int
    path: Path
    manifest: dict[str, Any]
    records: dict[str, dict[str, Any]] = field(default_factory=dict)


def _manifest_in(d: Path) -> Path | None:
    for name in MANIFEST_NAMES:
        if (d / name).is_file():
            return d / name
    return None


def _case_files(d: Path) -> list[Path]:
    return sorted(p for p in d.glob("*.json") if p.name not in MANIFEST_NAMES)


def run_index_of(d: Path, manifest: dict[str, Any]) -> int:
    """Repeat number of a run directory: the `__run<k>` suffix of its name, else 1."""
    m = _RUN_SUFFIX.match(d.name)
    return int(m.group("k")) if m else 1


def discover_runs(root: str | Path) -> list[RunSet]:
    """Every run under `root` (a driver output directory, `data/eval/runs/<id>`, or a tree of them), with its case records loaded.

    A half-written or unreadable case file is skipped. Two directories claiming the same (system, run) are an error: scoring must not silently pick one.
    """
    base = Path(root)
    if not base.is_dir():
        raise FileNotFoundError(f"{base} is not a directory")
    out: list[RunSet] = []
    seen: dict[tuple[str, int], Path] = {}
    for dirpath, dirnames, _files in os.walk(base):
        dirnames[:] = sorted(n for n in dirnames if n != "_events")
        d = Path(dirpath)
        mp = _manifest_in(d)
        if mp is None:
            continue
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        system = str(manifest.get("system") or _RUN_SUFFIX.sub(r"\g<system>", d.name))
        k = run_index_of(d, manifest)
        if (system, k) in seen:
            raise ValueError(f"system {system!r} run {k} appears twice: {seen[(system, k)]} and {d}")
        seen[(system, k)] = d
        rs = RunSet(system=system, run=k, path=d, manifest=manifest)
        for p in _case_files(d):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if isinstance(rec, dict):
                rs.records[str(rec.get("case_id") or p.stem)] = rec
        out.append(rs)
    return sorted(out, key=lambda r: (r.system.lower(), r.run))


def discover_rights(root: str | Path) -> dict[str, list[dict[str, Any]]]:
    """T4 Rights Radar scenario records under `root`, by arm name: directories without a manifest whose JSON files carry `rule`, `predicted` and `designed`."""
    found: dict[str, list[dict[str, Any]]] = {}
    for dirpath, dirnames, files in os.walk(Path(root)):
        dirnames[:] = [n for n in dirnames if n != "_events"]
        d = Path(dirpath)
        if _manifest_in(d) is not None:
            continue
        rows = []
        for name in sorted(f for f in files if f.endswith(".json")):
            try:
                rec = json.loads((d / name).read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if isinstance(rec, dict) and {"rule", "predicted", "designed"} <= rec.keys():
                rows.append({**rec, "case_id": name[:-5]})
        if rows:
            found.setdefault(str(rows[0].get("arm") or d.name), []).extend(rows)
    return found


def read_events(run: RunSet, case_id: str) -> list[dict[str, Any]]:
    """The case's event log lines (`_events/<case_id>.jsonl`), [] when absent."""
    p = run.path / "_events" / f"{case_id}.jsonl"
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


# ---------------------------------------------------------------------------------------------------------------- slices and gold
def resolve_slice_ids(
    slice_name: str, gold_source: str, testsets_dir: str | Path | None = None, *, open_blind: bool = False,
    lock: Path | None = None, check_tag: bool = True,
) -> set[str]:
    """The case ids of a slice. `dev` and `open` read id manifests only; `blind` is refused (`BlindSliceError`) unless `open_blind` is set, the freeze tag exists and no lock exists.

    Args:
        slice_name: dev | open | blind
        gold_source: agreed | rule (the id sets are the same in both golds)
        testsets_dir: the test-set root (default: the configured one)
        open_blind: the explicit flag of plan 5.8 (CLI `--open-blind`)
        lock: lock file path override (tests)
        check_tag: False only in tests
    """
    if slice_name not in SLICES:
        raise ValueError(f"slice must be one of {SLICES}, got {slice_name!r}")
    t1 = gs.t1_dir(gold_source, testsets_dir)
    if slice_name == "dev":
        return {str(r["case_id"]) for r in gs.load_t1("dev", gold_source, testsets_dir)}
    if slice_name == "open":
        manifest = json.loads((t1 / "manifest_open.json").read_text(encoding="utf-8"))
        return {str(i) for i in manifest["case_ids"]}
    from vakeel_sahayak.testsets.blind import open_blind as _open_blind

    return {str(i) for i in _open_blind(str(t1), confirm=open_blind, lock=lock, check_tag=check_tag)}


def gold_rows(slice_name: str, ids: set[str], gold_source: str, testsets_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """T1 case rows (with `gold` G1..G7 of the requested source) of the slice, in file order; ids absent from the gold are simply missing."""
    split = "dev" if slice_name == "dev" else "test"
    return [r for r in gs.load_t1(split, gold_source, testsets_dir) if str(r["case_id"]) in ids]


def gold_provenance(gold_source: str, testsets_dir: str | Path | None = None) -> dict[str, Any]:
    """`gold_source`, directory and hashes of the gold read (what the tables print as label source)."""
    return gs.gold_info(gold_source, testsets_dir)
