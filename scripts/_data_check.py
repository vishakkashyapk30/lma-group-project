"""`make data-check`: which data, stores, test sets and models are on this machine, compared with the team bundle.

    python scripts/_data_check.py [--data DIR] [--models DIR] [--config configs/models.yaml] [--require-models] [--json]

Prints a table (area, item, present or MISSING, detail). The exit code is 1 when a REQUIRED item is missing (interim files, the seven stores, the
test sets T1 to T6, T8 and T9, the gap statutes) or when a file or row count is below `data/bundle_manifest.json` (installed from the bundle; a count
above it only prints a note, because a local rebuild adds files). Optional items: `hindi_native`, the Hindi test set `t2_hindi_native`, Kathbath and the
T1 models (required with `--require-models`; `make models` fetches them). The raw source data (`raw/open_india_law`, `raw/ipc2bns_verify`, the Kathbath audio; in the
`raw.tar.part-*` archive of the bundle) is optional and reported, and required only with `--require-raw` or `REQUIRE_RAW=1`. The data folder defaults to `$VS_DATA_DIR` or `data`, the models folder to
`$VS_MODELS_DIR` or `models`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _data_bundle import bundled, lines  # noqa: E402  (helpers of the bundle scripts)

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ["orders.jsonl", "statutes.jsonl", "concordance_edges.jsonl", "oil_metadata.jsonl", "splits.json"]
STORES = [
    "law/statutes.sqlite",
    "law/concordance.sqlite",
    "caselaw/citations.sqlite",
    "caselaw/reasoning.sqlite",
    "caselaw/similar.sqlite",
    "advocacy/arguments.sqlite",
    "advocacy/objections.sqlite",
]
TESTSETS = [
    "t1/cases.jsonl",
    "t2/truth.jsonl",
    "t3/updates.jsonl",
    "t4/scenarios.jsonl",
    "t5/cases.jsonl",
    "t6/questions.jsonl",
    "t8/utterances.jsonl",
    "t9/strings.jsonl",
]
GAPS = ["statutes/crpc.jsonl", "statutes/ndps.jsonl", "statutes/first_schedule_ipc.jsonl"]
KATHBATH = "raw/kathbath/hindi/test_known"


def _size(path: Path) -> str:
    n = path.stat().st_size
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.1f} MB" if n >= 1e6 else f"{n / 1e3:.0f} KB"


def _file(area: str, data: Path, rel: str, required: bool = True, count_rows: bool = False) -> dict:
    p = data / rel
    ok = p.is_file() and p.stat().st_size > 0
    detail = ""
    if ok:
        detail = f"{lines(p):,} rows, {_size(p)}" if count_rows else _size(p)
    return {"area": area, "item": rel, "present": ok, "required": required, "detail": detail}


def model_ids(config: Path) -> list[str]:
    """Ids of the T1 models in the `weights:` table of configs/models.yaml."""
    import yaml

    tiers = yaml.safe_load(config.read_text(encoding="utf-8")).get("weights", {})
    return [m["id"] for m in (tiers.get("T1") or {}).get("models", [])]


def check_all(
    data: Path, models: Path, config: Path, require_models: bool = False, require_raw: bool = False
) -> tuple[list[dict], list[str]]:
    """The table rows and the notes on counts against the bundle manifest."""
    rows = [_file("interim", data, f"interim/{n}", count_rows=n.endswith(".jsonl")) for n in INTERIM]
    rows.append(_file("hindi_native", data, "interim/hindi_native.jsonl", required=False, count_rows=True))
    rows += [_file("stores", data, f"stores/{n}") for n in STORES]
    rows += [_file("testsets", data, f"testsets/{n}", count_rows=n.endswith(".jsonl")) for n in TESTSETS]
    rows.append(_file("testsets", data, "testsets/t2_hindi_native/truth.jsonl", required=False, count_rows=True))
    rows += [_file("gaps/statutes", data, f"gaps/{n}", count_rows=True) for n in GAPS]
    for n in ("manifest.jsonl", "transcription_n2w.txt"):
        rows.append(_file("kathbath", data, f"{KATHBATH}/{n}", required=False, count_rows=True))
    audio = data / KATHBATH / "audio"
    n_audio = sum(1 for _ in audio.glob("*.m4a")) if audio.is_dir() else 0
    rows.append(
        {
            "area": "raw",
            "item": f"{KATHBATH}/audio",
            "present": n_audio > 0,
            "required": require_raw,
            "detail": f"{n_audio} files"
            if n_audio
            else "in the raw archive of the bundle (RAW=1 make data-install ...), or: python -m vakeel_sahayak.pipelines.kathbath_fetch --out data/raw/kathbath --limit 3130",
        }
    )
    oil = data / "raw" / "open_india_law"
    n_shards = sum(1 for _ in (oil / "judgments").rglob("*")) if (oil / "judgments").is_dir() else 0
    rows.append(
        {
            "area": "raw",
            "item": "raw/open_india_law/judgments",
            "present": n_shards > 0,
            "required": require_raw,
            "detail": f"{n_shards} files" if n_shards else "in the raw archive of the bundle, or: make datasets",
        }
    )
    for rel in ("legislation/in_central_legislation.parquet", "sc_metadata.jsonl", "SHA256SUMS.json"):
        rows.append(_file("raw", data, f"raw/open_india_law/{rel}", required=require_raw))
    ipc = data / "raw" / "ipc2bns_verify"
    have_ipc = ipc.is_dir() and any(ipc.rglob("*"))
    rows.append(
        {
            "area": "raw",
            "item": "raw/ipc2bns_verify",
            "present": have_ipc,
            "required": require_raw,
            "detail": "" if have_ipc else "in the raw archive of the bundle, or: make datasets",
        }
    )
    for mid in model_ids(config) if config.is_file() else []:
        d = models / "hf" / mid.replace("/", "--")
        have = d.is_dir() and any(d.rglob("*"))
        rows.append(
            {
                "area": "models (T1)",
                "item": mid,
                "present": have,
                "required": require_models,
                "detail": "" if have else "make models",
            }
        )
    notes: list[str] = []
    bm = data / "bundle_manifest.json"
    if bm.is_file():
        expected = json.loads(bm.read_text(encoding="utf-8"))
        for rel, n in (expected.get("rows") or {}).items():
            got = lines(data / rel) if (data / rel).is_file() else None
            if got is None or got < n:
                rows.append(
                    {
                        "area": "bundle",
                        "item": f"{rel} rows",
                        "present": False,
                        "required": True,
                        "detail": f"{got} found, bundle manifest says {n}",
                    }
                )
            elif got > n:
                notes.append(f"{rel}: {got} rows, bundle manifest says {n} (rebuilt locally?)")
        for folder, info in (expected.get("folders") or {}).items():
            got = len(bundled(data / folder))
            if got < info["files"]:
                rows.append(
                    {
                        "area": "bundle",
                        "item": f"{folder}/ files",
                        "present": False,
                        "required": True,
                        "detail": f"{got} found, bundle manifest says {info['files']}",
                    }
                )
            elif got > info["files"]:
                notes.append(f"{folder}/: {got} files, bundle manifest says {info['files']} (local additions)")
    else:
        notes.append(
            "no data/bundle_manifest.json (data not installed from the bundle): counts were not compared with it"
        )
    return rows, notes


def render(rows: list[dict]) -> str:
    """The table as text."""
    w = max(len(r["item"]) for r in rows)
    out = [f"{'area':<14} {'item':<{w}}  {'status':<8} {'need':<8} detail"]
    for r in rows:
        status = "present" if r["present"] else "MISSING"
        need = "required" if r["required"] else "optional"
        out.append(f"{r['area']:<14} {r['item']:<{w}}  {status:<8} {need:<8} {r['detail']}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    """Command line entry."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=os.environ.get("VS_DATA_DIR", str(ROOT / "data")))
    ap.add_argument("--models", default=os.environ.get("VS_MODELS_DIR", str(ROOT / "models")))
    ap.add_argument("--config", default=str(ROOT / "configs" / "models.yaml"))
    ap.add_argument("--require-models", action="store_true", default=os.environ.get("REQUIRE_MODELS") == "1")
    ap.add_argument("--require-raw", action="store_true", default=os.environ.get("REQUIRE_RAW") == "1")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rows, notes = check_all(Path(a.data), Path(a.models), Path(a.config), a.require_models, a.require_raw)
    missing = [r for r in rows if r["required"] and not r["present"]]
    if a.json:
        print(json.dumps({"ok": not missing, "rows": rows, "notes": notes}, indent=1))
    else:
        print(render(rows))
        for n in notes:
            print("note:", n)
        optional = [r for r in rows if not r["required"] and not r["present"]]
        print(f"\nrequired missing: {len(missing)}; optional missing: {len(optional)}")
        if missing:
            print(
                "fix: make data (needs access to the team bundle), or rebuild: make datasets interim stores (see data/README.md)"
            )
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
