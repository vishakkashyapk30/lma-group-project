"""Helpers of scripts/data_bundle.sh and scripts/data_install.sh: count rows of the bundled files, write the bundle manifest, check an install.

    python scripts/_data_bundle.py manifest <data_dir> <out.json>     # row counts and sizes of what the bundle holds
    python scripts/_data_bundle.py check <data_dir> <bundle_manifest.json>   # exit 1 when a count differs
    python scripts/_data_bundle.py models <models_dir>                # names and sizes only (never the weights)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXCLUDED = ("key", "token", "secret", ".env")  # file names left out of the tar (same patterns as data_bundle.sh)
COUNTED = ("interim/orders.jsonl", "interim/statutes.jsonl", "interim/concordance_edges.jsonl", "interim/oil_metadata.jsonl")


def bundled(root: Path) -> list[Path]:
    """Files of a folder that the tar holds (names with key, token, secret or .env in them are left out)."""
    return [p for p in root.rglob("*") if p.is_file() and not any(x in p.name.lower() for x in EXCLUDED)] if root.is_dir() else []


def lines(path: Path) -> int:
    """Number of lines of a text file."""
    with path.open("rb") as fh:
        return sum(1 for _ in fh)


def manifest(data: Path) -> dict:
    """Row counts of the interim files, the store MANIFEST.json of the shipped stores, and the file count and bytes of each bundled folder."""
    out: dict = {"rows": {}, "folders": {}}
    for rel in COUNTED:
        if (data / rel).is_file():
            out["rows"][rel] = lines(data / rel)
    store_manifest = data / "stores" / "MANIFEST.json"
    if store_manifest.is_file():
        out["stores_manifest"] = json.loads(store_manifest.read_text(encoding="utf-8"))
    for folder in ("interim", "stores", "testsets", "gaps", "eval"):
        root = data / folder
        files = bundled(root)
        out["folders"][folder] = {"files": len(files), "bytes": sum(p.stat().st_size for p in files)}
    raw = data / "raw" / "MANIFEST.json"
    out["raw_manifest_datasets"] = sorted((json.loads(raw.read_text(encoding="utf-8")).get("datasets") or {}).keys()) if raw.is_file() else []
    return out


def check(data: Path, expected: dict) -> list[str]:
    """Problems found when comparing an installed data folder with the bundle manifest (empty list: all counts match)."""
    problems = []
    for rel, n in (expected.get("rows") or {}).items():
        got = lines(data / rel) if (data / rel).is_file() else None
        if got != n:
            problems.append(f"{rel}: {got} rows, bundle manifest says {n}")
    for folder, info in (expected.get("folders") or {}).items():
        root = data / folder
        got = len(bundled(root))
        if got != info["files"]:
            problems.append(f"{folder}/: {got} files, bundle manifest says {info['files']}")
    if not (data / "raw" / "MANIFEST.json").is_file():
        problems.append("raw/MANIFEST.json is missing")
    return problems


def models(root: Path) -> str:
    """Names and sizes of the model folders (a listing, never the weights)."""
    rows = []
    for p in sorted(root.glob("*")) if root.is_dir() else []:
        files = [f for f in p.rglob("*") if f.is_file()] if p.is_dir() else [p]
        rows.append(f"{sum(f.stat().st_size for f in files) / 1e9:8.2f} GB  {p.name}")
        if p.is_dir():
            for q in sorted(p.glob("*")):
                fs = [f for f in q.rglob("*") if f.is_file()] if q.is_dir() else [q]
                rows.append(f"{sum(f.stat().st_size for f in fs) / 1e9:8.2f} GB    {p.name}/{q.name}")
    return "\n".join(rows) + ("\n" if rows else "")


def main(argv: list[str]) -> int:
    """Command line entry."""
    cmd = argv[1]
    if cmd == "manifest":
        Path(argv[3]).write_text(json.dumps(manifest(Path(argv[2])), indent=1), encoding="utf-8")
        return 0
    if cmd == "check":
        problems = check(Path(argv[2]), json.loads(Path(argv[3]).read_text(encoding="utf-8")))
        for p in problems:
            print("SANITY:", p)
        print("sanity check:", "FAILED" if problems else "ok (row and file counts match the bundle manifest)")
        return 1 if problems else 0
    if cmd == "models":
        sys.stdout.write(models(Path(argv[2])))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
