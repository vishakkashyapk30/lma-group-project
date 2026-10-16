"""Open India Law ingest: bail orders (High Courts 2019-2025, SC judgments on bail) and statute text -> the repo's interim formats (plan §2 source 1).

Input is the local subset written by `oil_fetch` (`data/raw/open_india_law/`): Parquet shards of judgment *chunks* (one row per
chunk; `case_id`, `chunk_index`, `text_original`, `char_start`/`char_end`, court, title, `decision_date`, bench, disposition,
`case_number`, `citation`, `source_url`...) and the legislation file (one row per section chunk: `act_id`, `title`,
`section_number`, `chunk_id`, `text` behind an "Act: ... | Section N: Title" header).

Outputs (UTF-8 JSONL, one object per line):

- `<out_dir>/orders.jsonl`: the format of `store_builders.corpus` (doc_id, text, date, court, title, citations,
  neutral_citation, bench_size, bench, offence_date, fir_key, outcome when the court's disposition is unambiguous...) plus
  provenance (`source`: dataset, version, file, case id, source URL) and ingest flags.
- `<out_dir>/statutes.jsonl`: `StatuteRow` per line.
- `<out_dir>/orders_index.jsonl.gz`: one compact row per selected order of the whole population (the feasibility check reads it).
- `<out_dir>/ingest_report.json`: counts of everything read, selected, skipped and why, and the sampling.

Steps for a case: reassemble the chunks (the offsets `char_start`/`char_end` remove the overlap between neighbouring
chunks; a case with a missing chunk is dropped), strip the markdown markers, apply the strict bail test (case type or
opening text; plan keywords such as "BAIL APPLN", "439 Cr.P.C.", "483 BNSS"), drop sexual-offence, POCSO and juvenile
matters (`privacy.sensitive_matters`, plan §16; counts by reason in the report), then derive FIR key and offence date from the text.

Streaming, parallel and resumable: pass 1 ingests each raw shard in a worker process and caches only its stats and compact index rows
(`<out_dir>/.oil_shards/*.meta.json.gz`, skipped when newer than the shard); the population index `orders_index.jsonl.gz` covers every
selected order. Pass 2 applies the sampling rules (`choose_kept`: per court and year cap, the evaluation pool always kept) and writes
only the chosen orders (`*.kept-<hash>.jsonl.gz`), concatenated atomically into `orders.jsonl`. Memory is one shard per worker.

CLI: `python -m vakeel_sahayak.pipelines.oil_ingest orders|statutes|feasibility|all [--raw ...] [--out data/interim]`.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.concordance.refs import make_ref
from vakeel_sahayak.pipelines.leakage import fir_key
from vakeel_sahayak.pipelines.section_extract import charged_sections, extract_sections
from vakeel_sahayak.pipelines.text_utils import normalise_date
from vakeel_sahayak.privacy.sensitive_matters import is_declined_matter
from vakeel_sahayak.schemas.store_rows import StatuteRow

log = logging.getLogger(__name__)

DATASET = "vaquill/open-india-law"
VERSION = "v2026.08.1"
DEFAULT_KEYWORDS = ["BAIL APPLN", "439 Cr.P.C.", "483 BNSS"]  # plan §2; matched flexibly (case, dots, spaces)
HEAD_CHARS = 6000
_I = re.IGNORECASE

# case-type prefix of the title: "BAIL APPLN./8/2016 of ..." -> "BAIL APPLN."
_BAIL_TYPE = re.compile(
    r"\b(?:bail|b\.?\s?a\.?|a\.?\s?b\.?\s?a\.?|crl\.?\s?m\.?\s?b|crmb|bl\.?\s?apl|blapl|anticipatory|s\.?b\.?\s?crmb)\b", _I
)
_BAIL_WORD = re.compile(r"\bbail\b", _I)
# the bail sections of the old and new code (CrPC 437-439 and BNSS 480, 482, 483) next to the code name
_BAIL_SECTION = re.compile(
    r"(?:\b(?:43[789]|44[0])\s*(?:\([0-9a-z]\)\s*)?(?:of\s+(?:the\s+)?)?(?:cr\.?\s?p\.?\s?c|code\s+of\s+criminal\s+procedure)"
    r"|\b(?:48[023]|47[89])\s*(?:\([0-9a-z]\)\s*)?(?:of\s+(?:the\s+)?)?(?:bnss|bharatiya\s+nagarik)"
    r"|(?:cr\.?\s?p\.?\s?c|bnss)\W{0,6}(?:sections?|secs?\.?|s\.)\W{0,3}(?:43[789]|44[0]|48[023]|47[89])\b"
    r"|(?:sections?|secs?\.?|s\.)\W{0,3}(?:43[789]|44[0]|48[023]|47[89])\W{0,12}(?:cr\.?\s?p\.?\s?c|bnss)"
    r"|\b(?:regular|anticipatory|interim|pre[- ]arrest|post[- ]arrest)\s+bail)",
    _I,
)
_EXTRA_SENSITIVE = re.compile(r"\brape\b|\bprosecutrix\b|\bsexual\s+(?:assault|offence)s?\b|\bgang[- ]?rape\b|\bpocso\b", _I)
_MARKERS = re.compile(r"^[ \t]*\[(?:TITLE|SECTION|HEADER|FOOTER|PAGE)\][ \t]*(?:#+[ \t]*)?", _I | re.MULTILINE)
_RULE = re.compile(r"^[ \t]*[-_=*]{5,}[ \t]*$", re.MULTILINE)
_NEUTRAL = re.compile(r"^\s*(?:19|20)\d{2}\s*:\s*[A-Z][A-Za-z-]*\s*:\s*\d+|\b(?:19|20)\d{2}\s+INSC\s+\d+", _I)
_INCIDENT = re.compile(
    r"(?:date\s+of\s+(?:the\s+)?(?:incident|occurrence|offence|alleged\s+offence)|(?:incident|occurrence|offence)\s+(?:took\s+place|occurred)"
    r"|(?:alleged\s+to\s+have\s+(?:occurred|taken\s+place)|on\s+or\s+about))\W{0,12}"
    r"(?:on\s+)?(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*(?:19|20)\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Z][a-z]+,?\s+(?:19|20)\d{2})",
    _I,
)
_FIR_DATE = re.compile(
    r"\bF\.?\s?I\.?\s?R\.?\s*(?:No\.?\s*[\w/.-]*\s*)?(?:,?\s*(?:was\s+)?(?:registered\s+)?(?:dated|dt\.?|on|of))\W{0,4}"
    r"(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*(?:19|20)\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Z][a-z]+,?\s+(?:19|20)\d{2})",
    _I,
)
_BNS_CUTOFF = "2024-07-01"
# wider than `leakage.fir_key`: any crime / case number of the investigating police station in the opening text
_ANY_CRIME_NUMBER = re.compile(
    r"(?:\bF\.?\s?I\.?\s?R\.?|case\s+crime|crime|p\.?\s?s\.?\s+case|police\s+station\s+case|\bcase)\s*(?:no\.?|number)\s*[:#.-]?\s*\d{1,6}", _I
)


# --------------------------------------------------------------------------------------------- reassembly
def reassemble(chunks: list[dict[str, Any]]) -> tuple[str, bool]:
    """Join the chunks of one case into its text.

    Chunks are ordered by `chunk_index`; where `char_start` lies before the end of the text already placed (the overlap
    between neighbours) the repeated characters are dropped.

    Returns:
        (text, complete). `complete` is False when `chunk_index` values are missing or duplicated against `total_chunks`.
    """
    ordered = sorted(chunks, key=lambda c: c["chunk_index"])
    out: list[str] = []
    placed_end = 0
    for chunk in ordered:
        body = str(chunk.get("text_original") or "")
        start = chunk.get("char_start")
        if start is not None and out and start < placed_end:
            body = body[placed_end - start :] if placed_end - start < len(body) else ""
        out.append(body)
        placed_end = chunk["char_end"] if chunk.get("char_end") is not None else placed_end + len(body)
    total = ordered[0].get("total_chunks")
    indexes = [c["chunk_index"] for c in ordered]
    complete = indexes == list(range(len(indexes))) and (total is None or total == len(indexes))
    return "".join(out), complete


def clean_text(text: str) -> str:
    """Strip the extractor's markdown markers (`[TITLE] #`, `[SECTION] ##`), rule lines and runs of blank lines."""
    text = _MARKERS.sub("", text)
    text = re.sub(r"^[ \t]*#+[ \t]+", "", text, flags=re.MULTILINE)
    text = _RULE.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ---------------------------------------------------------------------------------------------- selection
@lru_cache(maxsize=8)
def _keyword_regex(keywords: tuple[str, ...]) -> re.Pattern[str]:
    """Flexible regex for plan keywords: dots and spaces optional ('439 Cr.P.C.' matches '439 CrPC' and 'Section 439 of Cr. P. C.')."""
    parts = []
    for kw in keywords:
        tokens = [re.sub(r"[.\s]+", r"\\s?\\.?\\s?", re.escape(t).replace(r"\.", ".")) for t in kw.split()]
        parts.append(r"\W{0,3}".join(tokens))
    return re.compile("|".join(f"(?:{p})" for p in parts), _I)


def case_type_of(title: str | None) -> str:
    """The case type before the first '/' of an OIL title ('BAIL APPLN./8/2016 of A Vs State' -> 'BAIL APPLN.')."""
    return (title or "").split(" of ")[0].split("/")[0].strip()


def is_bail_order(title: str | None, text: str, keywords: list[str] | None = None) -> tuple[bool, str]:
    """The strict bail test: a bail case type, a plan keyword in the opening text, or bail named with a bail section.

    Returns:
        (selected, basis) with basis one of 'case_type', 'keyword', 'bail_section', 'no'.
    """
    if _BAIL_TYPE.search(case_type_of(title)):
        return True, "case_type"
    head = text[:HEAD_CHARS]
    if keywords and _keyword_regex(tuple(keywords)).search(head) and _BAIL_WORD.search(head):
        return True, "keyword"
    if _BAIL_WORD.search(head) and _BAIL_SECTION.search(head):
        return True, "bail_section"
    return False, "no"


def is_bail_judgment(text: str, min_mentions: int = 4) -> bool:
    """Supreme Court test: several mentions of bail and a CrPC/BNSS reference."""
    return len(_BAIL_WORD.findall(text)) >= min_mentions and bool(re.search(r"cr\.?\s?p\.?\s?c|\bbnss\b|code\s+of\s+criminal", text, _I))


def declined_reason(title: str | None, text: str) -> str | None:
    """Reason a matter is dropped at ingest (sexual offence, POCSO, juvenile; plan §16), or None to keep it.

    The charged sections and the opening text go through `privacy.sensitive_matters`; ingest additionally drops opening
    texts naming rape, a prosecutrix or sexual assault, since declining is the safe error for victim identity.
    """
    head = f"{title or ''}\n{text[:HEAD_CHARS]}"
    sections = list(dict.fromkeys(extract_sections(head)))
    declined, reason = is_declined_matter(sections, [title or "", head])
    if declined:
        kind = "pocso" if reason and "POCSO" in reason else "juvenile" if reason and "Juvenile" in reason else "sexual_offence"
        return kind
    if _EXTRA_SENSITIVE.search(head):
        return "sexual_offence_keyword"
    return None


# --------------------------------------------------------------------------------------------- derivation
def _bench(chunk: dict[str, Any]) -> tuple[list[str], int | None]:
    judges = [str(j) for j in (chunk.get("judges") or []) if j]
    strength = chunk.get("bench_strength")
    size = int(strength) if isinstance(strength, int) and strength > 0 else (len(judges) or None)
    return judges, size


def extract_offence_date(text: str, bns_cutoff: str = _BNS_CUTOFF) -> tuple[str | None, str | None]:
    """The offence date written in the order and where it came from.

    Prefers an explicit incident date ('on or about', 'date of the incident'); falls back to the FIR date. A FIR dated before the
    BNS date proves the offence was earlier; a FIR dated on or after it is used only when the text charges no IPC section
    (the police charge IPC for offences before 1 July 2024), otherwise no offence date is given.

    Returns:
        (ISO date or None, source 'incident' | 'fir_date' | None).
    """
    head = text[: HEAD_CHARS * 2]
    m = _INCIDENT.search(head)
    if m and (iso := _to_iso(m.group(1))):
        return iso, "incident"
    m = _FIR_DATE.search(head)
    if m and (iso := _to_iso(m.group(1))):
        if iso < bns_cutoff or not any(r.startswith("IPC ") for r in extract_sections(head)):
            return iso, "fir_date"
    return None, None


def _to_iso(raw: str) -> str | None:
    """'7 - 10 - 2016', '07.10.2016' or '7th October, 2016' to ISO (None when not a real date)."""
    return normalise_date(re.sub(r"\s*([./-])\s*", r"\1", raw.strip()))


def case_record(chunks: list[dict[str, Any]], text: str, shard: str, keywords: list[str] | None = None) -> dict[str, Any] | None:
    """Build the `orders.jsonl` record of one reassembled case (None when it has no usable date)."""
    first = chunks[0]
    date = normalise_date(str(first.get("decision_date") or ""))
    if not date:
        return None
    judges, bench_size = _bench(first)
    citation = str(first.get("citation") or "").strip()
    offence, source = extract_offence_date(text)
    fkey = fir_key({"text": text, "court": first.get("court")})
    sections = charged_sections(extract_sections(text[:HEAD_CHARS]))
    rec: dict[str, Any] = {
        "doc_id": str(first["case_id"]),
        "text": text,
        "date": date,
        "court": str(first.get("court") or "unknown"),
        "title": first.get("title"),
        "case_number": first.get("case_number"),
        "case_type": case_type_of(first.get("title")),
        "disposition": first.get("disposition"),
        "citations": [citation] if citation else [],
        "bench": judges,
        "bench_size": bench_size,
        "offence_date": offence,
        "offence_date_source": source,
        "fir_key": fkey,
        "charged_sections": sections,
        "source": {
            "dataset": DATASET,
            "version": VERSION,
            "file": shard,
            "case_id": str(first["case_id"]),
            "source_url": first.get("source_url") or None,
            "licence": "CC BY 4.0",
        },
    }
    if citation and _NEUTRAL.search(citation):
        rec["neutral_citation"] = citation
    return rec


# ------------------------------------------------------------------------------------------------- shards
SC_NAME = "Supreme Court of India"
DEFAULT_CAP_PER_COURT_YEAR = 800
DEFAULT_SC_PER_YEAR = 120
DEFAULT_SC_FROM_YEAR = 1990


def canonical_court(stem: str) -> str:
    """Court name from the raw file stem ('punjab-and-haryana' -> 'Punjab and Haryana High Court'); the release spells courts several ways."""
    if stem == "supreme-court":
        return SC_NAME
    words = [w if w == "and" else w.capitalize() for w in stem.split("-")]
    return " ".join(words) + " High Court"


def _is_supreme(court: str | None) -> bool:
    return "supreme" in (court or "").lower()


def _read_shard_cases(path: Path) -> dict[str, list[dict[str, Any]]]:
    import pyarrow.parquet as pq

    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pq.read_table(path).to_pylist():
        by_case[str(row["case_id"])].append(row)
    return by_case


def ingest_shard(path: Path, keywords: list[str] | None = None) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Convert one raw shard to order records and a counter of what happened to its cases.

    Each record carries `clean_split` (the repo splitter's verdict, High Court orders) and `bns_era`, so the feasibility check and the
    sampling rules never need to re-read the text.
    """
    from vakeel_sahayak.pipelines.order_splitter import analyse_split
    from vakeel_sahayak.pipelines.splits import order_is_bns_era

    court_name = canonical_court(path.parent.name)
    supreme = _is_supreme(court_name)
    stats: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    for chunks in _read_shard_cases(path).values():
        stats["cases_read"] += 1
        text, complete = reassemble(chunks)
        if not complete:
            stats["dropped_incomplete"] += 1
            continue
        text = clean_text(text)
        if not text:
            stats["dropped_no_text"] += 1
            continue
        title = chunks[0].get("title")
        if supreme:
            ok, basis = is_bail_judgment(text), "sc_discusses_bail"
        else:
            ok, basis = is_bail_order(title, text, keywords)
        if not ok:
            stats["dropped_not_bail"] += 1
            continue
        reason = declined_reason(title, text)
        if reason:
            stats[f"declined_{reason}"] += 1
            continue
        rec = case_record(sorted(chunks, key=lambda c: c["chunk_index"]), text, path.parent.name + "/" + path.name, keywords)
        if rec is None:
            stats["dropped_no_date"] += 1
            continue
        rec["court"] = court_name
        rec["court_as_published"] = chunks[0].get("court") or None
        rec["selection_basis"] = basis
        rec["bns_era"] = order_is_bns_era(rec)
        if supreme:
            rec["bail_mentions"] = len(_BAIL_WORD.findall(text))
        else:
            rec["clean_split"] = analyse_split(text).clean
        stats["selected"] += 1
        stats["selected_sc" if supreme else "selected_hc"] += 1
        stats[f"basis_{basis}"] += 1
        records.append(rec)
    return records, stats


def _hash_key(doc_id: str) -> str:
    """Stable pseudo-random order of doc ids (the sampling is deterministic and independent of file order)."""
    return hashlib.sha1(doc_id.encode()).hexdigest()


def _in_eval_window(date: str, cfg: dict[str, Any]) -> bool:
    return any(str(cfg.get(w, {}).get("from", "9")) <= date <= str(cfg.get(w, {}).get("to", "0")) for w in ("dev", "test"))


def _stem(shard: Path) -> str:
    return f"{shard.parent.name}__{shard.stem}"


def _meta_path(cache: Path, shard: Path) -> Path:
    return cache / f"{_stem(shard)}.meta.json.gz"


def _index_row(r: dict[str, Any]) -> dict[str, Any]:
    """Compact index row of a record (what the sampling rules and the feasibility check need)."""
    return {
        "doc_id": r["doc_id"], "court": r["court"], "date": r["date"], "clean_split": r.get("clean_split"), "bns_era": r["bns_era"],
        "offence_date_source": r.get("offence_date_source"), "bail_mentions": r.get("bail_mentions"),
        "has_fir": bool(r.get("fir_key")), "has_offence_date": bool(r.get("offence_date")), "chars": len(r["text"]),
    }  # fmt: skip


def _index_shard(args: tuple[str, str, list[str]]) -> str:
    """Pass 1 for one raw shard (runs in a worker process): write its stats and index rows, not the texts."""
    shard_s, cache_s, keywords = args
    shard, cache = Path(shard_s), Path(cache_s)
    records, stats = ingest_shard(shard, keywords)
    tmp = _meta_path(cache, shard).with_name(_meta_path(cache, shard).name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=3) as fh:
        json.dump({"stats": stats, "index": [_index_row(r) for r in records]}, fh)
    tmp.replace(_meta_path(cache, shard))
    return shard_s


def _kept_piece(cache: Path, shard: Path, ids: set[str]) -> Path:
    return cache / f"{_stem(shard)}.kept-{hashlib.sha1(','.join(sorted(ids)).encode()).hexdigest()[:12]}.jsonl.gz"


def _write_kept(args: tuple[str, str, list[str], list[str]]) -> str:
    """Pass 2 for one raw shard: re-ingest it and write only the orders chosen by the sampling rules."""
    shard_s, cache_s, keywords, ids_list = args
    shard, cache = Path(shard_s), Path(cache_s)
    ids = set(ids_list)
    piece = _kept_piece(cache, shard, ids)
    for stale in cache.glob(f"{_stem(shard)}.kept-*.jsonl.gz"):
        if stale != piece:
            stale.unlink()
    if piece.is_file():
        return shard_s
    records, _ = ingest_shard(shard, keywords)
    tmp = piece.with_name(piece.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=3) as fh:
        for r in records:
            if r["doc_id"] in ids:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(piece)
    return shard_s


def _run_parallel(fn: Any, jobs: list[Any], workers: int | None) -> None:
    import os
    from concurrent.futures import ProcessPoolExecutor

    n_workers = workers or min(8, os.cpu_count() or 1)
    if jobs and n_workers > 1:
        with ProcessPoolExecutor(n_workers) as pool:
            list(pool.map(fn, jobs, chunksize=2))
    else:
        for job in jobs:
            fn(job)


def index_shards(raw_dir: str, out_dir: str, keywords: list[str], workers: int | None = None) -> tuple[list[Path], Counter[str], list[dict[str, Any]]]:
    """Pass 1: ingest every raw shard (in parallel, cached per shard) into stats and a compact index row per selected order."""
    cache = Path(out_dir) / ".oil_shards"
    cache.mkdir(parents=True, exist_ok=True)
    shards = sorted(Path(raw_dir, "judgments").glob("*/rg-*.parquet"))
    todo = [
        (str(sh), str(cache), keywords)
        for sh in shards
        if not (_meta_path(cache, sh).is_file() and _meta_path(cache, sh).stat().st_mtime >= sh.stat().st_mtime)
    ]
    _run_parallel(_index_shard, todo, workers)
    total: Counter[str] = Counter()
    index: list[dict[str, Any]] = []
    for sh in shards:
        with gzip.open(_meta_path(cache, sh), "rt", encoding="utf-8") as fh:
            loaded = json.load(fh)
        total.update(loaded["stats"])
        for row in loaded["index"]:
            row["shard"] = sh.parent.name + "/" + sh.name
            index.append(row)
    return shards, total, index


def choose_kept(index: list[dict[str, Any]], cap: int, sc_per_year: int, sc_from_year: int, windows: dict[str, Any]) -> tuple[set[str], dict[str, int]]:
    """Which orders enter `orders.jsonl`.

    High Courts: per (court, year) at most `cap` orders in stable hash order, plus every cleanly split order inside the dev and test
    windows (the pool the evaluation splits are drawn from; the BNS-era orders of the test pool are among them), so the sampling cannot
    shrink the evaluation pool. Supreme Court: from `sc_from_year`, the `sc_per_year` judgments per year with the most mentions of bail.
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    sc_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in index:
        if _is_supreme(row["court"]):
            sc_groups[row["date"][:4]].append(row)
        else:
            groups[(row["court"], row["date"][:4])].append(row)
    kept: set[str] = set()
    counts: Counter[str] = Counter()
    for rows in groups.values():
        must = [r for r in rows if r["clean_split"] and _in_eval_window(r["date"], windows)]
        must_ids = {r["doc_id"] for r in must}
        rest = sorted((r for r in rows if r["doc_id"] not in must_ids), key=lambda r: _hash_key(r["doc_id"]))
        take = must_ids | {r["doc_id"] for r in rest[: max(0, cap - len(must_ids))]}
        kept |= take
        counts["hc_kept"] += len(take)
        counts["hc_kept_must_keep"] += len(must_ids)
    for year, rows in sc_groups.items():
        if int(year) < sc_from_year:
            counts["sc_before_from_year"] += len(rows)
            continue
        top = sorted(rows, key=lambda r: (-(r.get("bail_mentions") or 0), _hash_key(r["doc_id"])))[:sc_per_year]
        kept |= {r["doc_id"] for r in top}
        counts["sc_kept"] += len(top)
    return kept, dict(counts)


def select_bail_orders(
    raw_dir: str,
    out_dir: str,
    keywords: list[str] | None = None,
    cap_per_court_year: int = DEFAULT_CAP_PER_COURT_YEAR,
    sc_per_year: int = DEFAULT_SC_PER_YEAR,
    sc_from_year: int = DEFAULT_SC_FROM_YEAR,
) -> int:
    """Filter the Open India Law subset to bail orders and write `orders.jsonl`, shard by shard and resumably.

    Pass 1 ingests every raw shard in parallel into stats and an index row per selected order (cached per shard), and writes the
    full-population index `orders_index.jsonl.gz` (doc_id, court, date, clean split, BNS era, offence-date source, FIR key present) that the
    feasibility check reads. Pass 2 samples (see `choose_kept`) so `orders.jsonl` stays within the disk budget and the stores
    stay buildable; the report states the population and the sample.

    Args:
        raw_dir: `data/raw/open_india_law` (the `judgments/<court>/rg-*.parquet` shards from `oil_fetch`)
        out_dir: interim folder; receives `orders.jsonl`, `orders_index.jsonl.gz`, `ingest_report.json` and the cache `.oil_shards/`
        keywords: plan keywords that select a case from its opening text (default `DEFAULT_KEYWORDS`)
        cap_per_court_year: High Court orders kept per court and year (None-like 0 keeps all)
        sc_per_year: Supreme Court judgments kept per year
        sc_from_year: earliest Supreme Court year kept

    Returns:
        Number of orders written to `orders.jsonl`.
    """
    from vakeel_sahayak.config import load_config

    keywords = DEFAULT_KEYWORDS if keywords is None else keywords
    shards, total, index = index_shards(raw_dir, out_dir, keywords)
    seen: set[str] = set()
    unique = []
    for row in index:
        if row["doc_id"] in seen:
            total["duplicate_case_ids"] += 1
            continue
        seen.add(row["doc_id"])
        unique.append(row)
    cfg = load_config().splits
    if cap_per_court_year <= 0:
        kept, sample_counts = {r["doc_id"] for r in unique}, {"cap": "none"}
    else:
        kept, sample_counts = choose_kept(unique, cap_per_court_year, sc_per_year, sc_from_year, cfg)
    out = Path(out_dir)
    with gzip.open(out / "orders_index.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as fh:
        for row in unique:
            fh.write(json.dumps({**row, "in_orders_jsonl": row["doc_id"] in kept}, ensure_ascii=False) + "\n")
    ids_by_shard: dict[str, list[str]] = defaultdict(list)
    for row in unique:
        if row["doc_id"] in kept:
            ids_by_shard[row["shard"]].append(row["doc_id"])
    cache = out / ".oil_shards"
    jobs = [(str(sh), str(cache), keywords, ids_by_shard[sh.parent.name + "/" + sh.name]) for sh in shards if ids_by_shard.get(sh.parent.name + "/" + sh.name)]
    _run_parallel(_write_kept, jobs, None)
    written: set[str] = set()
    by_court_year: Counter[str] = Counter()
    tmp = out / "orders.jsonl.tmp"
    with tmp.open("w", encoding="utf-8") as fh:
        for job in jobs:
            with gzip.open(_kept_piece(cache, Path(job[0]), set(job[3])), "rt", encoding="utf-8") as src:
                for line in src:
                    rec = json.loads(line)
                    if rec["doc_id"] not in written:
                        written.add(rec["doc_id"])
                        fh.write(line)
                        by_court_year[f"{rec['court']}|{rec['date'][:4]}"] += 1
    tmp.replace(out / "orders.jsonl")
    population: Counter[str] = Counter(f"{r['court']}|{r['date'][:4]}" for r in unique)
    report = {
        "dataset": DATASET,
        "version": VERSION,
        "shards": len(shards),
        "keywords": keywords,
        "counts": dict(sorted(total.items())),
        "population": {"high_court_orders": sum(1 for r in unique if not _is_supreme(r["court"])), "supreme_court_judgments": sum(1 for r in unique if _is_supreme(r["court"]))},
        "sampling": {"cap_per_court_year": cap_per_court_year, "sc_per_year": sc_per_year, "sc_from_year": sc_from_year, **sample_counts, "written": len(written)},
        "population_by_court_year": dict(sorted(population.items())),
        "orders_by_court_year": dict(sorted(by_court_year.items())),
    }
    path = out / "ingest_report.json"
    existing = json.loads(path.read_text()) if path.is_file() else {}
    path.write_text(json.dumps({**existing, "orders": report}, indent=1), encoding="utf-8")
    log.info("population %s, wrote %d orders: %s", report["population"], len(written), dict(total))
    return len(written)


# --------------------------------------------------------------------------------------------- statutes
_ACTS: list[tuple[str, re.Pattern[str], set[str] | None]] = [
    ("IPC", re.compile(r"^The Indian Penal Code, 45 of 1860"), None),
    ("BNS", re.compile(r"^The Bharatiya Nyaya Sanhita, 2023$"), None),
    ("BNSS", re.compile(r"^The Bharatiya Nagarik Suraksha Sanhita, 2023$"), None),
    ("CrPC", re.compile(r"^The Code of Criminal Procedure, 1973"), None),
    ("NDPS", re.compile(r"^The Narcotic Drugs and Psychotropic Substances Act, 1985$"), {"37"}),
    ("UAPA", re.compile(r"^The Unlawful Activities \(Prevention\) Act, 1967$"), {"43D"}),
    ("PMLA", re.compile(r"^The Prevention of Money-Laundering Act, 2002$"), {"45"}),
]
# header of every chunk: "Act: <title> (<year>) | India | ..." then "Chapter ...| Section N: <title>** . **—** <first words of the text>", then a blank line
_HEADER = re.compile(r"^Act:[^\n]*\n(?:Chapter[^\n]*\|\s*Section\s+\S+:\s*(?P<title>[^*\n]*)[^\n]*)?\n*")
_PART = re.compile(r"_p(\d+)$")
_NUMBER = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
           "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty": 20}  # fmt: skip
_TERM = re.compile(r"(?:extend|up)\s+to\s+(?P<n>\d+|[a-z]+(?:[- ]\w+)?)\s+(?P<u>years?|months?)", _I)


def max_punishment(text: str) -> str | None:
    """The heaviest punishment named in a penal section: 'death', 'life', or 'N years' / 'N months'; None when none is named."""
    low = text.lower()
    if re.search(r"punished\s+with\s+death|sentence\s+of\s+death|death,", low):
        return "death"
    best: tuple[float, str] | None = None
    for m in _TERM.finditer(text):
        raw = m.group("n").lower().replace("-", " ").split()
        value = int(raw[0]) if raw[0].isdigit() else _NUMBER.get(raw[0])
        if value is None:
            continue
        years = value if m.group("u").lower().startswith("year") else value / 12
        if best is None or years > best[0]:
            best = (years, f"{value} {m.group('u').lower().rstrip('s')}{'s' if value != 1 else ''}")
    if re.search(r"imprisonment\s+for\s+life|imprisonment\s+for\s+the\s+remainder", low):
        return "life"
    return best[1] if best else None


def extract_statute_texts(raw_dir: str, out_dir: str) -> int:
    """Write `statutes.jsonl` (StatuteRow per line): IPC, BNS, BNSS, CrPC when present, NDPS s.37, UAPA s.43D, PMLA s.45.

    The legislation file holds one row per section chunk (`..._s318_p0`, `_p1`...); the chunks of a section are joined in order
    after their "Act ... | Section N: Title" header. `bailable` and `cognisable` are left unset: they come from the CrPC/BNSS
    First Schedule, which this release does not carry. The CrPC 1973 is absent from the release, so no CrPC rows are written
    (the report says so).

    Args:
        raw_dir: folder with `legislation/in_central_legislation.parquet`
        out_dir: interim folder

    Returns:
        Number of sections written.
    """
    import pyarrow.parquet as pq

    path = Path(raw_dir) / "legislation" / "in_central_legislation.parquet"
    table = pq.read_table(path, columns=["act_id", "chunk_id", "title", "section_number", "text"])
    parts: dict[tuple[str, str], list[tuple[int, str, str | None]]] = defaultdict(list)
    wanted: dict[str, tuple[str, set[str] | None]] = {}
    for row in table.to_pylist():
        title = row["title"] or ""
        for code, pattern, only in _ACTS:
            if pattern.search(title):
                section = row["section_number"] or ""
                if not section or (only is not None and section not in only):
                    break
                wanted[row["act_id"]] = (code, only)
                m = _PART.search(row["chunk_id"] or "")
                head = _HEADER.match(row["text"] or "")
                body = (row["text"] or "")[head.end() :] if head else (row["text"] or "")
                parts[(row["act_id"], section)].append(
                    (int(m.group(1)) if m else -1, _plain(body), (head.group("title") or "").strip(" .—-") if head else None)
                )
                break
    rows: list[StatuteRow] = []
    for (act_id, section), pieces in sorted(parts.items(), key=lambda kv: (kv[0][0], _section_key(kv[0][1]))):
        code = wanted[act_id][0]
        pieces.sort(key=lambda p: p[0])
        seen: list[str] = []
        for _, body, _ in pieces:  # identical chunks (a whole-section chunk next to its parts) are kept once
            if body and body not in seen:
                seen.append(body)
        text = "\n\n".join(seen)
        title = next((t for _, _, t in pieces if t), None)
        if title:
            text = f"{title}\n\n{text}"
        rows.append(StatuteRow(code=code, section=make_ref(code, section).split(" ", 1)[1], text=text, max_punishment=max_punishment(text) if code in ("IPC", "BNS") else None))
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "statutes.jsonl").write_text("".join(r.model_dump_json() + "\n" for r in rows), encoding="utf-8")
    counts = Counter(r.code for r in rows)
    report_path = Path(out_dir) / "ingest_report.json"
    existing = json.loads(report_path.read_text()) if report_path.is_file() else {}
    existing["statutes"] = {
        "counts": dict(counts),
        "absent_from_release": [c for c, _, _ in _ACTS if c not in counts],
        "bailable_cognisable": "not in the release (CrPC/BNSS First Schedule missing)",
    }
    report_path.write_text(json.dumps(existing, indent=1), encoding="utf-8")
    return len(rows)


def _plain(body: str) -> str:
    """A legislation chunk body as plain text: no markdown bold/italics, no heading or amendment-note lines ('## _Of ..._', '> 3. Ins. by ...')."""
    lines = [ln for ln in body.splitlines() if not ln.lstrip().startswith(("#", ">"))]
    text = "\n".join(lines).replace("**", "")
    text = re.sub(r"\(\s*_([0-9A-Za-z]+)_\s*\)", r"(\1)", text)
    text = re.sub(r"(?<![\w])_([^_\n]+)_(?![\w])", r"\1", text)
    text = re.sub(r"\s+\.\s+—", ".—", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _section_key(section: str) -> tuple[int, str]:
    m = re.match(r"(\d+)(.*)", section)
    return (int(m.group(1)), m.group(2)) if m else (10**6, section)


# ------------------------------------------------------------------------------------------- feasibility
def _read_index(interim: Path) -> Any:
    """Rows of `orders_index.jsonl.gz` (one per selected order of the whole population)."""
    with gzip.open(interim / "orders_index.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


def check_feasibility(interim_dir: str, raw_dir: str | None = None, citation_sample: int = 3000) -> dict[str, Any]:
    """Week-0 data feasibility (plan §14, §18 week 0, §19); writes `feasibility_report.json` and `.md` into `interim_dir`.

    The population numbers (orders, clean splits, BNS era, courts, FIR numbers, offence dates) come from `orders_index.jsonl.gz`, which
    covers every selected order, not only the sample in `orders.jsonl`. The splits are assigned by the repo's `assign_splits` on
    `orders.jsonl` (written to `splits.json`); the sampling keeps every cleanly split dev/test-window order,
    so the dev and test pools are the same as for the whole population. The citation resolution rate is measured on a sample of
    `orders.jsonl`.

    Args:
        interim_dir: folder with `orders.jsonl` and `orders_index.jsonl`
        raw_dir: where `fetch_summary.json` is read from (optional)
        citation_sample: orders sampled for the citation-resolution measurement

    Returns:
        The report dict.
    """
    from vakeel_sahayak.config import load_config
    from vakeel_sahayak.pipelines.order_splitter import analyse_split
    from vakeel_sahayak.pipelines.splits import assign_splits, order_is_bns_era
    from vakeel_sahayak.pipelines.text_utils import read_jsonl

    interim = Path(interim_dir)
    cfg = load_config().splits
    cutoff = str(cfg.get("bns_era_offence_on_or_after", _BNS_CUTOFF))
    dev_w, test_w, train_before = cfg.get("dev", {}), cfg.get("test", {}), str(cfg.get("train", {}).get("before", "2024-01-01"))
    court_stats: dict[str, Counter[str]] = defaultdict(Counter)
    year_stats: Counter[str] = Counter()
    pool: Counter[str] = Counter()
    n_hc = n_sc = n_clean = n_bns = n_bns_clean = n_fir = n_off = n_train = 0
    sources: Counter[str] = Counter()
    for row in _read_index(interim):
        if _is_supreme(row["court"]):
            n_sc += 1
            continue
        n_hc += 1
        clean, bns, d = bool(row["clean_split"]), bool(row["bns_era"]), row["date"]
        n_clean += clean
        n_bns += bns
        n_bns_clean += bns and clean
        n_fir += bool(row["has_fir"])
        n_off += bool(row["has_offence_date"])
        sources[row.get("offence_date_source") or "none"] += 1
        year_stats[d[:4]] += 1
        n_train += d < train_before
        c = court_stats[row["court"]]
        c["orders"] += 1
        c["clean"] += clean
        c["bns_era"] += bns
        c["bns_era_clean"] += bns and clean
        c["fir_key"] += bool(row["has_fir"])
        for name, w in (("dev", dev_w), ("test", test_w)):
            if str(w.get("from", "")) <= d <= str(w.get("to", "")):
                pool[name] += 1
                pool[f"{name}_clean"] += clean
                if name == "test":
                    pool["test_bns_era"] += bns
                    pool["test_bns_era_clean"] += bns and clean
    orders_path = interim / "orders.jsonl"
    counts = assign_splits(str(orders_path), str(interim / "splits.json"))
    labels = json.loads((interim / "splits.json").read_text())
    bns_assigned: Counter[str] = Counter()
    test_by_court: Counter[str] = Counter()
    unclean_reasons: Counter[str] = Counter()
    sample_checked = 0
    broad = broad_total = 0
    for o in read_jsonl(orders_path):
        if not _is_supreme(o.get("court")):
            broad_total += 1
            broad += bool(_ANY_CRIME_NUMBER.search(o["text"][:3000]))
        split = labels.get(o["doc_id"])
        if split in ("dev", "test"):
            bns_assigned[split] += order_is_bns_era(o, cutoff)
            if split == "test":
                test_by_court[o.get("court") or "unknown"] += 1
        if not _is_supreme(o.get("court")) and sample_checked < 1500 and not o.get("clean_split", True):
            sample_checked += 1
            unclean_reasons.update(r.split(":")[0][:70] for r in analyse_split(o["text"]).reasons)
    citation = _citation_resolution(interim_dir, citation_sample, raw_dir)
    n_dt = counts["dev"] + counts["test"]
    min_bns = int(test_w.get("min_bns_era", 60))
    report: dict[str, Any] = {
        "population": {"high_court_bail_orders": n_hc, "supreme_court_bail_judgments": n_sc, "note": "all selected orders; orders.jsonl holds a sample (see ingest_report.json)"},
        "clean_splits": {"count": n_clean, "share": round(n_clean / n_hc, 4) if n_hc else None, "unclean_reasons_in_sample": dict(unclean_reasons.most_common(12))},
        "bns_era": {"definition": f"offence on or after {cutoff} (offence date, else text charging BNS and no IPC)", "orders": n_bns, "cleanly_split": n_bns_clean},
        "by_year": dict(sorted(year_stats.items())),
        "by_court": {c: dict(v) for c, v in sorted(court_stats.items(), key=lambda kv: -kv[1]["orders"])},
        "split_windows": {"train_before": train_before, "dev": dev_w, "test": test_w, "train_orders_in_population": n_train},
        "eligible_pools": {"dev_window": pool["dev"], "dev_window_clean": pool["dev_clean"], "test_window": pool["test"], "test_window_clean": pool["test_clean"], "test_window_bns_era": pool["test_bns_era"], "test_window_bns_era_clean": pool["test_bns_era_clean"]},
        "assigned_splits_on_orders_jsonl": counts,
        "assigned_bns_era": dict(bns_assigned),
        "test_by_court": dict(test_by_court.most_common()),
        "targets": {
            "dev_plus_test_cleanly_split_ge_250": {"required": 250, "assigned": n_dt, "eligible_clean_pool": pool["dev_clean"] + pool["test_clean"], "met": n_dt >= 250},
            "bns_era_in_test_ge_60": {"required": min_bns, "assigned": bns_assigned["test"], "eligible_clean_pool": pool["test_bns_era_clean"], "met": bns_assigned["test"] >= min_bns},
            "planned_sizes": {"dev": int(dev_w.get("n", 50)), "test": int(test_w.get("n", 200))},
        },
        "fir_numbers": {
            "orders_with_fir_key": n_fir,
            "share": round(n_fir / n_hc, 4) if n_hc else None,
            "note": "`leakage.fir_key` finds 'FIR No. n/yyyy' in the first 3,000 characters",
            "sample_any_crime_or_case_number_share": round(broad / broad_total, 4) if broad_total else None,
            "sample_size": broad_total,
        },
        "offence_dates": {"orders_with_offence_date": n_off, "share": round(n_off / n_hc, 4) if n_hc else None, "source": dict(sources)},
        "citations": citation,
    }
    if raw_dir and (Path(raw_dir) / "fetch_summary.json").is_file():
        report["fetch_summary"] = json.loads((Path(raw_dir) / "fetch_summary.json").read_text())
    (interim / "feasibility_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    (interim / "feasibility_report.md").write_text(render_feasibility_md(report), encoding="utf-8")
    return report


def _citation_resolution(interim_dir: str, sample: int, raw_dir: str | None = None, budget_s: float = 600.0) -> dict[str, Any]:
    """Citation resolution against Open India Law records on a random sample of orders.

    The index holds `orders.jsonl` and, when `<raw_dir>/sc_metadata.jsonl` exists (metadata of every Supreme Court judgment in the release,
    `oil_fetch.fetch_sc_metadata`), all Supreme Court judgments. Formal citations resolve by exact lookup; case names by fuzzy matching, which
    is slow on a large index, so unique citation strings are checked in random order until `budget_s` seconds are used and the rate is the
    occurrence-weighted share among those checked (the report says how many were checked).
    """
    import random
    import time
    from collections import Counter

    from vakeel_sahayak.pipelines.citation_graph.extract import extract_citations, parse_citation
    from vakeel_sahayak.pipelines.citation_graph.resolve import CitationIndex
    from vakeel_sahayak.pipelines.text_utils import read_jsonl

    records = list(read_jsonl(Path(interim_dir) / "orders.jsonl"))
    sc_path = Path(raw_dir or "") / "sc_metadata.jsonl"
    sc_records = list(read_jsonl(sc_path)) if raw_dir and sc_path.is_file() else []
    index = CitationIndex([*records, *sc_records])
    rng = random.Random(0)
    picked = rng.sample(records, min(sample, len(records)))
    occurrences: Counter[str] = Counter()
    for o in picked:
        occurrences.update(extract_citations(o["text"]))
    unique = list(occurrences)
    rng.shuffle(unique)
    tally: dict[str, list[int]] = {}
    checked = 0
    deadline = time.monotonic() + budget_s
    for raw in unique:
        if time.monotonic() > deadline:
            break
        parsed = parse_citation(raw)
        kind = parsed.kind if parsed else "unknown"
        weight = occurrences[raw]
        slot = tally.setdefault(kind, [0, 0, 0, 0])
        slot[0] += weight
        slot[1] += weight if index.resolve(raw) else 0
        slot[2] += 1
        checked += 1
    total = sum(v[0] for v in tally.values())
    resolved = sum(v[1] for v in tally.values())
    return {
        "orders_sampled": len(picked),
        "index": {"orders_jsonl": len(records), "supreme_court_metadata": len(sc_records)},
        "citations_in_sample": sum(occurrences.values()),
        "unique_citations": len(unique),
        "unique_checked": checked,
        "weighted_checked": total,
        "weighted_resolved": resolved,
        "rate": round(resolved / total, 4) if total else None,
        "by_format": {k: {"occurrences": v[0], "resolved": v[1], "unique_checked": v[2], "rate": round(v[1] / v[0], 4) if v[0] else None} for k, v in sorted(tally.items())},
        "note": "against the ingested bail subset plus the Supreme Court metadata of the release when present; High Court judgments outside the subset are not in the index, so this is a lower bound",
    }


def render_feasibility_md(r: dict[str, Any]) -> str:
    """Readable summary of the feasibility report."""
    t, pop, pools = r["targets"], r["population"], r["eligible_pools"]
    ok = lambda met, fail="NOT MET": "MET" if met else fail  # noqa: E731
    d250, b60 = t["dev_plus_test_cleanly_split_ge_250"], t["bns_era_in_test_ge_60"]
    lines = [
        "# Week-0 data feasibility (plan §14, §18, §19)",
        "",
        f"- High Court bail orders (2019-2025, sexual-offence / POCSO / juvenile matters removed): **{pop['high_court_bail_orders']:,}**; Supreme Court bail judgments: {pop['supreme_court_bail_judgments']:,}",
        f"- Cleanly split into facts / defense / prosecution / reasoning / operative: **{r['clean_splits']['count']:,}** ({(r['clean_splits']['share'] or 0):.1%})",
        f"- BNS-era ({r['bns_era']['definition']}): **{r['bns_era']['orders']:,}**, of which cleanly split {r['bns_era']['cleanly_split']:,}",
        f"- FIR number found in the text (`leakage.fir_key`): {r['fir_numbers']['orders_with_fir_key']:,} ({(r['fir_numbers']['share'] or 0):.1%}); any crime or case number in the opening text, on the sample in orders.jsonl: {(r['fir_numbers']['sample_any_crime_or_case_number_share'] or 0):.1%}; offence date found: {r['offence_dates']['orders_with_offence_date']:,} ({(r['offence_dates']['share'] or 0):.1%}), sources {r['offence_dates']['source']}",
        f"- Citation resolution (sample of {r['citations']['orders_sampled']:,} orders, {r['citations']['unique_checked']:,} of {r['citations']['unique_citations']:,} unique citations checked, index {r['citations']['index']}): **{r['citations']['rate']}** of occurrences resolve to Open India Law records",
        "",
        "## Plan targets",
        "",
        f"- Cleanly split dev + test orders >= 250: assigned {d250['assigned']} (clean pool in the windows {d250['eligible_clean_pool']:,}) -> **{ok(d250['met'])}**",
        f"- BNS-era orders in the test set >= 60: assigned {b60['assigned']} (clean BNS-era pool in the test window {b60['eligible_clean_pool']:,}) -> **{ok(b60['met'], 'NOT MET (plan §19: report H1c as a pilot)')}**",
        f"- Splits on orders.jsonl: {r['assigned_splits_on_orders_jsonl']}; pools: dev window {pools['dev_window']:,} ({pools['dev_window_clean']:,} clean), test window {pools['test_window']:,} ({pools['test_window_clean']:,} clean)",
        "",
        "## By year",
        "",
        "| year | orders |",
        "|---|---|",
        *[f"| {y} | {n:,} |" for y, n in r["by_year"].items()],
        "",
        "## By court",
        "",
        "| court | orders | cleanly split | BNS-era | FIR number |",
        "|---|---|---|---|---|",
        *[f"| {c} | {v['orders']:,} | {v.get('clean', 0):,} | {v.get('bns_era', 0):,} | {v.get('fir_key', 0):,} |" for c, v in r["by_court"].items()],
        "",
    ]
    return "\n".join(lines)


def write_sample(interim_dir: str, out_dir: str, n: int = 2000) -> int:
    """Write a bounded, court-balanced sample of `orders.jsonl` (round-robin over courts in stable hash order) to `out_dir`.

    `statutes.jsonl` and `concordance_edges.jsonl` are copied alongside, so `build_all --interim out_dir` runs end to end on it
    (the way to prove the store build on a bounded sample before building on everything).

    Returns:
        Number of orders written.
    """
    import shutil

    from vakeel_sahayak.pipelines.text_utils import read_jsonl

    by_court: dict[str, list[tuple[str, str]]] = defaultdict(list)
    with Path(interim_dir, "orders.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            by_court[rec["court"]].append((_hash_key(rec["doc_id"]), rec["doc_id"]))
    queues = {c: sorted(v) for c, v in sorted(by_court.items())}
    chosen: set[str] = set()
    while len(chosen) < n and any(queues.values()):
        for court in queues:
            if queues[court] and len(chosen) < n:
                chosen.add(queues[court].pop(0)[1])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    with (out / "orders.jsonl").open("w", encoding="utf-8") as fh:
        for rec in read_jsonl(Path(interim_dir) / "orders.jsonl"):
            if rec["doc_id"] in chosen:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1
    for name in ("statutes.jsonl", "concordance_edges.jsonl"):
        if (Path(interim_dir) / name).is_file():
            shutil.copyfile(Path(interim_dir) / name, out / name)
    return written


def main(argv: list[str] | None = None) -> int:
    """CLI: `orders`, `statutes`, `feasibility`, `sample` or `all`."""
    parser = argparse.ArgumentParser(description="Convert the Open India Law subset to interim files (plan §2).")
    parser.add_argument("step", choices=["orders", "statutes", "feasibility", "sample", "all"])
    parser.add_argument("--raw", default="data/raw/open_india_law")
    parser.add_argument("--out", default="data/interim")
    parser.add_argument("--cap-per-court-year", type=int, default=DEFAULT_CAP_PER_COURT_YEAR, help="High Court orders kept per court and year; 0 keeps all")
    parser.add_argument("--sc-per-year", type=int, default=DEFAULT_SC_PER_YEAR)
    parser.add_argument("--sc-from-year", type=int, default=DEFAULT_SC_FROM_YEAR)
    parser.add_argument("--n", type=int, default=2000, help="sample size for the `sample` step")
    parser.add_argument("--sample-out", default="data/interim_sample")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if args.step in ("statutes", "all"):
        print("statutes:", extract_statute_texts(args.raw, args.out))
    if args.step in ("orders", "all"):
        print("orders:", select_bail_orders(args.raw, args.out, None, args.cap_per_court_year, args.sc_per_year, args.sc_from_year))
    if args.step == "sample":
        print("sample:", write_sample(args.out, args.sample_out, args.n))
    if args.step in ("feasibility", "all"):
        rep = check_feasibility(args.out, args.raw)
        print(json.dumps({k: rep[k] for k in ("population", "clean_splits", "bns_era", "assigned_splits_on_orders_jsonl")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
