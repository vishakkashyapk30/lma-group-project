"""Native Hindi High Court bail orders from the raw Open India Law shards (fallback for HLDC, plan §2 source 3, docs/evaluation-plan.md T2).

HLDC (Hindi UP district-court documents) is gated on Hugging Face. The raw shards already hold native Hindi High Court bail orders (the shards
are the bail selection of week 0). This module scans every shard of every court, one parquet file at a time (only four columns are read), and
keeps a case when its first chunk is more than 30% Devanagari, then joins the chunks in order. Output `data/interim/hindi_native.jsonl`, one row
per case: `case_id, court, year, decision_date, title, text, devanagari_share, source_shard, chars`.

Kept: High Court orders only (the four Supreme Court rows are dropped), Devanagari share of the full text >= 0.5, length >= 800 characters, not in the T1 dev/test/blind slices (`testsets/t1/*.jsonl`, the sealed
hashes), not a dev/test order of `splits.json`, not excluded as a same-FIR order, no duplicate case id or duplicate text.

The Devanagari share is Devanagari letters and vowel signs over letters (Devanagari plus Latin); digits (both scripts), the danda, spaces and punctuation are not counted.
These are High Court orders (Allahabad and a few others), not Uttar Pradesh district-court documents like HLDC.

    python -m vakeel_sahayak.pipelines.hindi_native [--raw DIR --out FILE --splits FILE --t1 DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

FIRST_CHUNK_MIN = 0.30
FULL_TEXT_MIN = 0.50
MIN_CHARS = 800
COLUMNS = ["case_id", "chunk_index", "text_original", "court", "title", "decision_date", "year"]
_LATIN = re.compile(r"[A-Za-z]")
_DEVA = re.compile(r"[\u0900-\u0963\u0970-\u097f]")
_SPACES = re.compile(r"\s+")


def devanagari_share(text: str) -> float:
    """Devanagari characters over letters (Devanagari plus Latin); 0.0 when there are none."""
    dev = len(_DEVA.findall(text))
    latin = len(_LATIN.findall(text))
    return dev / (dev + latin) if dev + latin else 0.0


def leakage_ids(splits_path: str | None, t1_dir: str | None) -> set[str]:
    """Doc ids that must not enter the set: T1 cases and dev, sealed blind hashes, dev/test orders of `splits.json`, same-FIR orders of test orders."""
    out: set[str] = set()
    if splits_path and Path(splits_path).is_file():
        splits = json.loads(Path(splits_path).read_text(encoding="utf-8"))
        out.update(d for d, s in splits.items() if s in ("dev", "test", "blind"))
    if t1_dir and Path(t1_dir).is_dir():
        for name in ("cases.jsonl", "dev.jsonl"):
            f = Path(t1_dir) / name
            if f.is_file():
                for line in f.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        row = json.loads(line)
                        out.update(str(row[k]) for k in ("doc_id", "case_id") if row.get(k))
    return out


def blind_hashes(t1_dir: str | None) -> set[str]:
    """Salted hashes of the sealed blind slice (never the ids)."""
    f = Path(t1_dir or "") / "manifest_blind.json"
    return set(json.loads(f.read_text(encoding="utf-8")).get("hashes", [])) if f.is_file() else set()


def _flush(chunks: dict[int, str], meta: dict[str, Any], shard: str, case_id: str) -> dict[str, Any]:
    text = "\n".join(chunks[i] for i in sorted(chunks))
    return {"case_id": case_id, "court": meta["court"], "year": meta["year"], "decision_date": meta["decision_date"], "title": meta["title"],
            "text": text, "devanagari_share": round(devanagari_share(text), 4), "source_shard": shard, "chars": len(text)}  # fmt: skip


def iter_native_cases(shards: list[Path], raw_dir: Path | None = None):
    """Yield candidate cases (first chunk > 30% Devanagari) from parquet shards, one file at a time.

    Chunks of a case are joined in `chunk_index` order.
    """
    import pyarrow.parquet as pq

    pending: dict[str, tuple[dict[int, str], dict[str, Any], str]] = {}
    for shard in shards:
        name = str(shard.relative_to(raw_dir)) if raw_dir else str(shard)
        pf = pq.ParquetFile(shard)
        for batch in pf.iter_batches(batch_size=2000, columns=[c for c in COLUMNS if c in pf.schema_arrow.names]):
            for r in batch.to_pylist():
                cid = str(r["case_id"])
                idx = int(r.get("chunk_index") or 0)
                text = r.get("text_original") or ""
                if idx == 0 and devanagari_share(text) > FIRST_CHUNK_MIN:
                    meta = {
                        "court": r.get("court"),
                        "year": r.get("year"),
                        "decision_date": str(r.get("decision_date") or "")[:10],
                        "title": r.get("title"),
                    }
                    pending[cid] = ({}, meta, name)
                if cid in pending:
                    pending[cid][0][idx] = text
    # emitted after the last shard: 23 cases of the release have chunks in two shards (a case started in an earlier shard is completed by the later one)
    for cid in sorted(pending):
        chunks, meta, src = pending[cid]
        yield _flush(chunks, meta, src, cid)


def build(raw_dir: str, out_path: str, splits_path: str | None = None, t1_dir: str | None = None) -> dict[str, Any]:
    """Scan all shards and write the JSONL; returns the report (counts per court and year)."""
    from vakeel_sahayak.testsets.blind import blind_hash

    raw = Path(raw_dir)
    shards = sorted(raw.glob("*/rg-*.parquet")) or sorted(raw.rglob("*.parquet"))
    banned = leakage_ids(splits_path, t1_dir)
    sealed = blind_hashes(t1_dir)
    report: dict[str, Any] = {
        "shards": len(shards),
        "candidates": 0,
        "dropped_not_high_court": 0,
        "dropped_low_share": 0,
        "dropped_short": 0,
        "dropped_leakage": 0,
        "dropped_duplicate": 0,
    }
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_text: set[str] = set()
    for row in iter_native_cases(shards, raw):
        report["candidates"] += 1
        if "supreme court" in str(row["court"]).lower():
            report["dropped_not_high_court"] += 1
        elif row["devanagari_share"] < FULL_TEXT_MIN:
            report["dropped_low_share"] += 1
        elif row["chars"] < MIN_CHARS:
            report["dropped_short"] += 1
        elif row["case_id"] in banned or (sealed and blind_hash(row["case_id"]) in sealed):
            report["dropped_leakage"] += 1
        else:
            key = hashlib.sha256(_SPACES.sub(" ", row["text"]).strip().encode()).hexdigest()
            if row["case_id"] in seen_ids or key in seen_text:
                report["dropped_duplicate"] += 1
                continue
            seen_ids.add(row["case_id"])
            seen_text.add(key)
            rows.append(row)
    rows.sort(key=lambda r: r["case_id"])
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    report["kept"] = len(rows)
    report["per_court"] = dict(sorted(Counter(str(r["court"]) for r in rows).items()))
    report["per_year"] = dict(sorted(Counter(str(r["year"]) for r in rows).items()))
    report["per_court_year"] = {
        c: dict(sorted(Counter(str(r["year"]) for r in rows if r["court"] == c).items())) for c in report["per_court"]
    }
    return report


def main(argv: list[str] | None = None) -> int:
    """CLI."""
    from vakeel_sahayak.config import load_config

    paths = load_config().paths
    ap = argparse.ArgumentParser(description="Build data/interim/hindi_native.jsonl")
    ap.add_argument("--raw", default=str(Path(paths.raw_dir) / "open_india_law" / "judgments"))
    ap.add_argument("--out", default=str(Path(paths.interim_dir) / "hindi_native.jsonl"))
    ap.add_argument("--splits", default=str(Path(paths.interim_dir) / "splits.json"))
    ap.add_argument("--t1", default=str(Path(paths.testsets_dir) / "t1"))
    args = ap.parse_args(argv)
    report = build(args.raw, args.out, args.splits, args.t1)
    Path(args.out).with_suffix(".report.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
