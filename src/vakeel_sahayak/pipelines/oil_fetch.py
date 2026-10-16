"""Fetch the part of Open India Law this project needs (plan §2 source 1) without downloading all 54 GB.

The release (`v2026.08.1`, CC BY 4.0) is 26 Parquet files of judgment *chunks* (53.6 GB) plus 37 legislation files. The
Hugging Face repo `vaquill/open-india-law` is gated (log in and accept the terms); the same files are served, ungated,
by the mirror the dataset's own README names (`https://oss-data-in.vaquill.ai`). Both carry the same bytes and the same
`SHA256SUMS.json`. This module reads the mirror with HTTP range requests, row group by row group, keeps only the chunks
of *bail candidate* cases and writes them to small local Parquet shards:

    data/raw/open_india_law/judgments/<court-file>/rg-00012.parquet     chunks of candidate cases
    data/raw/open_india_law/state/<court-file>.json                     finished row groups (the resume point)
    data/raw/open_india_law/legislation/in_central_legislation.parquet  verified against SHA256SUMS.json

A candidate is deliberately loose (superset); `oil_ingest` applies the strict bail test, the sexual-offence / POCSO /
juvenile filter and the reassembly. High Courts: decisions dated 2019-01-01..2025-12-31 whose case type or opening
text is a bail matter. Supreme Court: any year, judgments that discuss bail at some length. A case whose chunks straddle
two row groups is kept from the group where it was recognised; `oil_ingest` drops cases with missing chunks.

Run as `python -m vakeel_sahayak.pipelines.oil_fetch --out data/raw/open_india_law [--courts sikkim delhi]`.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import re
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

VERSION = "v2026.08.1"
MIRROR = "https://oss-data-in.vaquill.ai"
HF_REPO = "vaquill/open-india-law"
HC_FILES = (
    "allahabad andhra-pradesh bombay calcutta chhattisgarh delhi gauhati gujarat himachal-pradesh jammu-and-kashmir "
    "jharkhand karnataka kerala madhya-pradesh madras manipur meghalaya orissa patna punjab-and-haryana rajasthan "
    "sikkim telangana tripura uttarakhand"
).split()
SC_FILE = "supreme-court"
LEGISLATION_FILES = ("in_central_legislation.parquet",)
HC_FROM, HC_TO = "2019-01-01", "2025-12-31"

# Columns kept in the shards. `text_original` is the chunk body; `text` repeats it behind a 3-line header, so it is not read.
KEEP = [
    "case_id", "chunk_index", "total_chunks", "text_original", "char_start", "char_end", "section_type", "court",
    "court_code", "bench", "bench_strength", "judges", "title", "petitioner", "respondent", "disposition",
    "case_number", "citation", "decision_date", "date_of_registration", "year", "source_url",
]  # fmt: skip
META = ["case_id", "chunk_index", "title", "decision_date", "case_number"]

_I = re.IGNORECASE
_BAIL_TYPE = re.compile(
    r"\b(?:bail|b\.?\s?a\.?|a\.?\s?b\.?\s?a\.?|crl\.?\s?m\.?\s?b|crmb|bl\.?\s?apl|blapl|anticipatory|s\.?b\.?\s?crmb)\b", _I
)
_BAIL_WORD = re.compile(r"\bbail\b", _I)
_PROCEDURE = re.compile(r"cr\.?\s?p\.?\s?c|code\s+of\s+criminal\s+procedure|\bbnss\b|bharatiya\s+nagarik", _I)
_HEAD_CHARS = 6000
_SC_MIN_BAIL_MENTIONS = 4


def _sha256(path: Path) -> str:
    """SHA-256 of a file, read in 1 MiB blocks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class HttpRangeFile(io.RawIOBase):
    """A read-only seekable file over HTTP range requests, with a small read-ahead cache and retries."""

    def __init__(self, url: str, retries: int = 12, block: int = 1 << 20) -> None:
        import requests

        self.url, self.retries, self.block = url, retries, block
        self._session = requests.Session()
        head = self._call(lambda: self._session.head(url, allow_redirects=True, timeout=60))
        self.size = int(head.headers["content-length"])
        self._pos = 0
        self._cache: tuple[int, bytes] = (0, b"")

    def _call(self, fn: Any) -> Any:
        for attempt in range(self.retries):
            try:
                resp = fn()
                resp.raise_for_status()
                return resp
            except Exception as exc:  # noqa: BLE001 - network errors of every kind are retried
                if attempt == self.retries - 1:
                    raise
                log.warning("retry %d for %s: %s", attempt + 1, self.url, exc)
                time.sleep(min(60, 2**attempt))
        raise RuntimeError("unreachable")

    def readable(self) -> bool:  # noqa: D102
        return True

    def seekable(self) -> bool:  # noqa: D102
        return True

    def tell(self) -> int:  # noqa: D102
        return self._pos

    def seek(self, offset: int, whence: int = 0) -> int:  # noqa: D102
        self._pos = offset if whence == 0 else self._pos + offset if whence == 1 else self.size + offset
        return self._pos

    def _fetch(self, start: int, length: int) -> bytes:
        end = min(self.size, start + length) - 1
        resp = self._call(
            lambda: self._session.get(self.url, headers={"Range": f"bytes={start}-{end}"}, timeout=180)
        )
        return resp.content

    def readinto(self, buffer: Any) -> int:  # noqa: D102
        want = min(len(buffer), self.size - self._pos)
        if want <= 0:
            return 0
        start, data = self._cache
        if not (start <= self._pos and self._pos + want <= start + len(data)):
            data = self._fetch(self._pos, max(want, self.block))
            self._cache = (self._pos, data)
            start = self._pos
        chunk = data[self._pos - start : self._pos - start + want]
        buffer[: len(chunk)] = chunk
        self._pos += len(chunk)
        return len(chunk)


def case_heads(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group chunk rows by case id, each group sorted by chunk index."""
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_case[str(row["case_id"])].append(row)
    for chunks in by_case.values():
        chunks.sort(key=lambda r: r["chunk_index"])
    return by_case


def is_hc_candidate(title: str | None, chunks: list[dict[str, Any]]) -> bool:
    """Loose test: a bail case type in the title, or a bail word and a CrPC/BNSS reference in the opening text."""
    if _BAIL_TYPE.search((title or "").split(" of ")[0]):
        return True
    head = ""
    for chunk in chunks:
        head += str(chunk.get("text_original") or "")
        if len(head) >= _HEAD_CHARS:
            break
    head = head[:_HEAD_CHARS]
    return bool(_BAIL_WORD.search(head) and _PROCEDURE.search(head))


def is_sc_candidate(chunks: list[dict[str, Any]]) -> bool:
    """Loose test for a Supreme Court judgment that discusses bail: several mentions and a CrPC/BNSS reference."""
    text = " ".join(str(c.get("text_original") or "") for c in chunks)
    return len(_BAIL_WORD.findall(text)) >= _SC_MIN_BAIL_MENTIONS and bool(_PROCEDURE.search(text))


def select_row_group(pf: Any, index: int, supreme: bool) -> tuple[Any | None, dict[str, int]]:
    """Read one row group and return (pyarrow table of the chunks of candidate cases or None, counts).

    The small metadata columns are read first; the large `text_original` column is only read when some case passes the
    date window (all High Court years 2019-2025; Supreme Court any year).
    """
    import pyarrow as pa
    import pyarrow.compute as pc

    names = set(pf.schema_arrow.names)
    meta = pf.read_row_group(index, columns=[c for c in META if c in names])
    counts = {"rows": meta.num_rows}
    if not supreme:
        dates = pc.cast(pc.utf8_slice_codeunits(meta["decision_date"], 0, 10), pa.string())
        in_window = pc.and_(pc.greater_equal(dates, HC_FROM), pc.less_equal(dates, HC_TO))
        window_rows = pc.fill_null(in_window, False)
        if not pc.any(window_rows).as_py():
            return None, {**counts, "cases_in_window": 0, "cases_kept": 0}
    else:
        window_rows = pa.array([True] * meta.num_rows)
    full = pf.read_row_group(index, columns=[c for c in KEEP if c in names])
    full = full.filter(window_rows)
    rows = full.to_pylist()
    by_case = case_heads(rows)
    keep: set[str] = set()
    for case_id, chunks in by_case.items():
        ok = is_sc_candidate(chunks) if supreme else is_hc_candidate(chunks[0].get("title"), chunks)
        if ok:
            keep.add(case_id)
    counts.update(cases_in_window=len(by_case), cases_kept=len(keep))
    if not keep:
        return None, counts
    mask = pc.is_in(full["case_id"], value_set=pa.array(sorted(keep)))
    return full.filter(mask), counts


def process_file(file_stem: str, out_dir: Path, source: str, workers: int = 1, limit_groups: int | None = None) -> dict[str, Any]:
    """Stream one judgments file (`in_<stem>_judgments.parquet`) into candidate shards, skipping finished row groups.

    Args:
        file_stem: court name as in the file name ('delhi', 'supreme-court')
        out_dir: the dataset folder (`data/raw/open_india_law`)
        source: mirror base URL (the version folder is appended) or a local folder holding the Parquet files
        workers: concurrent row groups for this file
        limit_groups: process at most this many unfinished row groups (testing and pilots)

    Returns:
        Totals: row groups done, rows scanned, cases in window, cases kept, shard bytes.
    """
    import pyarrow.parquet as pq

    name = f"in_{file_stem}_judgments.parquet"
    handle: Any = HttpRangeFile(f"{source.rstrip('/')}/{VERSION}/{name}") if source.startswith("http") else open(Path(source) / name, "rb")
    pf = pq.ParquetFile(handle)
    shard_dir = out_dir / "judgments" / file_stem
    shard_dir.mkdir(parents=True, exist_ok=True)
    state_path = out_dir / "state" / f"{file_stem}.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = json.loads(state_path.read_text()) if state_path.is_file() else {"groups": {}}
    state["num_row_groups"], state["num_rows"] = pf.metadata.num_row_groups, pf.metadata.num_rows
    todo = [g for g in range(pf.metadata.num_row_groups) if str(g) not in state["groups"]]
    if limit_groups is not None:
        todo = todo[:limit_groups]
    lock = threading.Lock()

    def work(g: int) -> None:
        local: Any = HttpRangeFile(f"{source.rstrip('/')}/{VERSION}/{name}") if source.startswith("http") else open(Path(source) / name, "rb")
        try:
            table, counts = select_row_group(pq.ParquetFile(local), g, file_stem == SC_FILE)
            if table is not None:
                tmp = shard_dir / f"rg-{g:05d}.parquet.tmp"
                pq.write_table(table, tmp, compression="zstd", compression_level=6)
                tmp.rename(shard_dir / f"rg-{g:05d}.parquet")
            with lock:
                state["groups"][str(g)] = counts
                state_path.write_text(json.dumps(state))
        finally:
            local.close()

    if workers > 1:
        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(work, todo))
    else:
        for g in todo:
            work(g)
    handle.close()
    done = state["groups"].values()
    return {
        "file": name,
        "row_groups_done": len(state["groups"]),
        "row_groups_total": state["num_row_groups"],
        "rows_scanned": sum(c["rows"] for c in done),
        "cases_in_window": sum(c.get("cases_in_window", 0) for c in done),
        "cases_kept": sum(c.get("cases_kept", 0) for c in done),
        "shard_bytes": sum(p.stat().st_size for p in shard_dir.glob("rg-*.parquet")),
    }


def fetch_sc_metadata(out_dir: Path, source: str, workers: int = 8) -> dict[str, Any]:
    """Metadata of every Supreme Court judgment (one row per case) for citation resolution: `sc_metadata.jsonl`.

    Reads only the small columns (case id, chunk index, title, date, neutral citation, court, case number) of the Supreme Court file,
    so about 3-5% of its bytes. Skipped when the file exists.
    """
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    target = out_dir / "sc_metadata.jsonl"
    if target.is_file():
        return {"file": target.name, "rows": sum(1 for _ in target.open(encoding="utf-8")), "reused": True}
    name = f"in_{SC_FILE}_judgments.parquet"
    open_file = (lambda: HttpRangeFile(f"{source.rstrip('/')}/{VERSION}/{name}")) if source.startswith("http") else (lambda: open(Path(source) / name, "rb"))
    first = pq.ParquetFile(open_file())
    columns = [c for c in ("case_id", "chunk_index", "title", "decision_date", "citation", "court", "case_number") if c in first.schema_arrow.names]

    def work(g: int) -> list[dict[str, Any]]:
        table = pq.ParquetFile(open_file()).read_row_group(g, columns=columns)
        table = table.filter(pc.equal(table["chunk_index"], pa.scalar(0, table["chunk_index"].type)))
        return [{k: v for k, v in r.items() if k != "chunk_index"} for r in table.to_pylist()]

    rows: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(workers) as pool:
        for part in pool.map(work, range(first.metadata.num_row_groups)):
            for r in part:
                rows.setdefault(str(r["case_id"]), r)
    tmp = target.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows.values():
            doc_id = str(r["case_id"])
            neutral = re.fullmatch(r"((?:19|20)\d{2})_INSC_(\d+)", doc_id)  # Supreme Court ids are neutral citations: 2011_INSC_772 -> "2011 INSC 772"
            cites = ([r["citation"]] if r.get("citation") else []) + ([f"{neutral.group(1)} INSC {neutral.group(2)}"] if neutral else [])
            fh.write(json.dumps({"doc_id": doc_id, "title": r.get("title"), "date": str(r.get("decision_date") or "")[:10], "court": r.get("court") or "Supreme Court of India", "citations": cites, "case_number": r.get("case_number")}, ensure_ascii=False) + "\n")
    tmp.replace(target)
    return {"file": target.name, "rows": len(rows), "reused": False}


def fetch_legislation(out_dir: Path, source: str) -> list[dict[str, Any]]:
    """Download the legislation files and verify them against the release's `SHA256SUMS.json`. Idempotent.

    Returns:
        One manifest entry per file: name, bytes, sha256, verified.
    """
    import requests

    dest = out_dir / "legislation"
    dest.mkdir(parents=True, exist_ok=True)
    base = f"{source.rstrip('/')}/{VERSION}"
    sums = requests.get(f"{base}/SHA256SUMS.json", timeout=60).json()
    (out_dir / "SHA256SUMS.json").write_text(json.dumps(sums, indent=1))
    entries = []
    for name in LEGISLATION_FILES:
        want = sums["files"].get(name, {}).get("sha256")
        path = dest / name
        if not (path.is_file() and (not want or _sha256(path) == want)):
            with requests.get(f"{base}/{name}", stream=True, timeout=120) as resp:
                resp.raise_for_status()
                tmp = path.with_suffix(".tmp")
                with tmp.open("wb") as fh:
                    for block in resp.iter_content(1 << 20):
                        fh.write(block)
            tmp.rename(path)
        got = _sha256(path)
        entries.append({"file": name, "bytes": path.stat().st_size, "sha256": got, "verified": bool(want) and got == want})
        if want and got != want:
            raise ValueError(f"checksum mismatch for {name}: expected {want}, got {got}")
    return entries


def main(argv: list[str] | None = None) -> int:
    """CLI: fetch legislation and the bail-candidate chunks of the selected courts."""
    parser = argparse.ArgumentParser(description="Fetch the bail subset of Open India Law (plan §2).")
    parser.add_argument("--out", default="data/raw/open_india_law")
    parser.add_argument("--source", default=MIRROR, help="mirror URL, or a local folder with the Parquet files")
    parser.add_argument("--courts", nargs="*", help="High Court file stems (default all); 'supreme-court' for the Supreme Court")
    parser.add_argument("--workers", type=int, default=4, help="row groups read concurrently within a file")
    parser.add_argument("--limit-groups", type=int, help="pilot: at most this many row groups per file")
    parser.add_argument("--no-legislation", action="store_true")
    parser.add_argument("--no-sc-metadata", action="store_true", help="skip the Supreme Court metadata file used for citation resolution")
    parser.add_argument("--only-sc-metadata", action="store_true", help="fetch only sc_metadata.jsonl")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"version": VERSION, "source": args.source, "files": []}
    if args.only_sc_metadata and (out / "fetch_summary.json").is_file():
        summary = json.loads((out / "fetch_summary.json").read_text())
    if not args.no_legislation:
        summary["legislation"] = fetch_legislation(out, args.source)
    pending = [] if args.only_sc_metadata else list(args.courts or [*HC_FILES, SC_FILE])
    for attempt in range(1, 6):  # a file that fails on a network error is retried on the next pass (finished row groups are kept)
        failed = []
        for stem in pending:
            try:
                result = process_file(stem, out, args.source, args.workers, args.limit_groups)
            except Exception as exc:  # noqa: BLE001
                log.warning("pass %d: %s failed: %s", attempt, stem, exc)
                failed.append(stem)
                continue
            log.info("%s", result)
            summary["files"] = [f for f in summary["files"] if f["file"] != result["file"]] + [result]
        pending = failed
        if not pending:
            break
        time.sleep(30)
    summary["failed"] = pending
    if not args.no_sc_metadata:
        try:
            summary["sc_metadata"] = fetch_sc_metadata(out, args.source)
        except Exception as exc:  # noqa: BLE001
            log.warning("sc metadata failed: %s", exc)
            summary["sc_metadata"] = {"error": str(exc)}
    (out / "fetch_summary.json").write_text(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
