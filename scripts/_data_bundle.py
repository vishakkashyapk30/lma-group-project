"""Helpers of scripts/data_bundle.sh and scripts/data_install.sh: count rows of the bundled files, write the bundle manifest, check an install.

python scripts/_data_bundle.py manifest <data_dir> <out.json>     # row counts and sizes of what the bundle holds
python scripts/_data_bundle.py check <data_dir> <bundle_manifest.json> [raw]   # exit 1 when a count differs (raw: also the raw archive's file counts)
python scripts/_data_bundle.py paths <data_dir> data|raw         # the paths (relative to data/) that one archive holds, one per line
python scripts/_data_bundle.py state <data_dir> data|raw         # sha256 of the sorted (path, size, mtime) list of one archive's files (resume key)
python scripts/_data_bundle.py archives <bundle_manifest.json> <bundle_dir>   # record parts and bytes of both archive families in the manifest
python scripts/_data_bundle.py models <models_dir>                # names and sizes only (never the weights)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXCLUDED = ("key", "token", "secret", ".env")  # file names left out of the tar (same patterns as data_bundle.sh)
KATHBATH = "raw/kathbath/hindi/test_known"
KATHBATH_FILES = (
    f"{KATHBATH}/manifest.jsonl",
    f"{KATHBATH}/transcription_n2w.txt",
)  # transcripts and the audio index; the 3.6 GB of audio is not bundled
RAW_DIRS = (
    "open_india_law",
    "ipc2bns_verify",
    "kathbath",
)  # data/raw folders of the second archive (raw.tar.part-*); data/raw/MANIFEST.json joins them
COUNTED = (
    "interim/orders.jsonl",
    "interim/statutes.jsonl",
    "interim/concordance_edges.jsonl",
    "interim/oil_metadata.jsonl",
    "interim/hindi_native.jsonl",
    *KATHBATH_FILES,
)


def family_paths(data: Path, family: str) -> list[str]:
    """Paths (relative to data/) that the `data` archive (gzip, derived data) or the `raw` archive (plain tar, public source data) holds."""
    if family == "raw":
        return [f"raw/{d}" for d in RAW_DIRS if (data / "raw" / d).is_dir()] + (
            ["raw/MANIFEST.json"] if (data / "raw" / "MANIFEST.json").is_file() else []
        )
    paths = [d for d in ("interim", "stores", "testsets", "gaps", "eval") if (data / d).is_dir()]
    if (data / "raw" / "MANIFEST.json").is_file():
        paths.append("raw/MANIFEST.json")
    return paths + [f for f in KATHBATH_FILES if (data / f).is_file()]


def family_files(data: Path, family: str) -> list[Path]:
    """Files of one archive family, key, token, secret and .env names left out."""
    out: list[Path] = []
    for rel in family_paths(data, family):
        p = data / rel
        out += [p] if p.is_file() and not any(x in p.name.lower() for x in EXCLUDED) else bundled(p)
    return sorted(out)


def state(data: Path, family: str) -> str:
    """Resume key of an archive: sha256 of its sorted (relative path, size, mtime) list."""
    import hashlib

    h = hashlib.sha256()
    for p in family_files(data, family):
        st = p.stat()
        h.update(f"{p.relative_to(data)}\t{st.st_size}\t{st.st_mtime_ns}\n".encode())
    return h.hexdigest()


def bundled(root: Path) -> list[Path]:
    """Files of a folder that the tar holds (names with key, token, secret or .env in them are left out)."""
    return (
        [p for p in root.rglob("*") if p.is_file() and not any(x in p.name.lower() for x in EXCLUDED)]
        if root.is_dir()
        else []
    )


def real(root: Path) -> list[Path]:
    """`bundled(root)` without the placeholders a git clone carries (.gitkeep): they are not data."""
    return [p for p in bundled(root) if p.name != ".gitkeep"]


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
        files = real(root)
        out["folders"][folder] = {"files": len(files), "bytes": sum(p.stat().st_size for p in files)}
    raw_files = family_files(data, "raw")
    out["raw"] = {
        "files": len(raw_files),
        "bytes": sum(p.stat().st_size for p in raw_files),
        "folders": {
            d: {
                "files": len(bundled(data / "raw" / d)),
                "bytes": sum(p.stat().st_size for p in bundled(data / "raw" / d)),
            }
            for d in RAW_DIRS
            if (data / "raw" / d).is_dir()
        },
    }
    raw = data / "raw" / "MANIFEST.json"
    out["raw_manifest_datasets"] = (
        sorted((json.loads(raw.read_text(encoding="utf-8")).get("datasets") or {}).keys()) if raw.is_file() else []
    )
    return out


def check(data: Path, expected: dict, raw: bool = False) -> list[str]:
    """Problems found when comparing an installed data folder with the bundle manifest (empty list: all counts match)."""
    problems = []
    for rel, n in (expected.get("rows") or {}).items():
        got = lines(data / rel) if (data / rel).is_file() else None
        if got != n:
            problems.append(f"{rel}: {got} rows, bundle manifest says {n}")
    for folder, info in (expected.get("folders") or {}).items():
        root = data / folder
        got = len(real(root))
        # older manifests also counted a .gitkeep of the owner's clone: either count may match, a fresh clone's placeholders never fail the check
        if info["files"] not in (got, len(bundled(root))):
            problems.append(f"{folder}/: {got} files, bundle manifest says {info['files']}")
    if not (data / "raw" / "MANIFEST.json").is_file():
        problems.append("raw/MANIFEST.json is missing")
    if raw:
        for d, info in ((expected.get("raw") or {}).get("folders") or {}).items():
            got = len(bundled(data / "raw" / d))
            if got != info["files"]:
                problems.append(f"raw/{d}/: {got} files, bundle manifest says {info['files']}")
    return problems


def archives(manifest_path: Path, bundle: Path) -> dict:
    """Record parts and bytes of the data (gzip) and raw (plain tar) archive families in the bundle manifest (existing keys are kept)."""
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    fam = {"data": ("data.tar.gz.part-*", "gzip"), "raw": ("raw.tar.part-*", "none")}
    m["archives"] = {}
    for name, (pattern, comp) in fam.items():
        parts = sorted(bundle.glob(pattern))
        m["archives"][name] = {"parts": len(parts), "bytes": sum(p.stat().st_size for p in parts), "compression": comp}
    m.setdefault("raw", {})["parts"] = m["archives"]["raw"]["parts"]
    manifest_path.write_text(json.dumps(m, indent=1), encoding="utf-8")
    return m


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
        problems = check(
            Path(argv[2]), json.loads(Path(argv[3]).read_text(encoding="utf-8")), raw=len(argv) > 4 and argv[4] == "raw"
        )
        for p in problems:
            print("SANITY:", p)
        print("sanity check:", "FAILED" if problems else "ok (row and file counts match the bundle manifest)")
        return 1 if problems else 0
    if cmd == "paths":
        sys.stdout.write("".join(f"{p}\n" for p in family_paths(Path(argv[2]), argv[3])))
        return 0
    if cmd == "state":
        print(state(Path(argv[2]), argv[3]))
        return 0
    if cmd == "archives":
        archives(Path(argv[2]), Path(argv[3]))
        return 0
    if cmd == "models":
        sys.stdout.write(models(Path(argv[2])))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
