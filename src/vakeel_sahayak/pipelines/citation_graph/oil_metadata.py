"""Build `oil_metadata.jsonl`, the metadata index the citation resolver and T1's G2 gold read (VI-05).

Sources, both Open India Law (no manual annotation):
- `data/raw/open_india_law/sc_metadata.jsonl`: one record per Supreme Court judgment (37,014): `doc_id` ('2011_INSC_772'),
  `title` ('A versus B'), `date`, `court`, `citations` (the neutral citation '2011 INSC 772' and the SCR citation
  '[2011] 15 S.C.R. 211'), `case_number` (empty in practice). It has no SCC or AIR citation, so a cited '(2014) 8 SCC 273'
  or 'AIR 1978 SC 597' cannot be resolved by key; those resolve only through the case name.
- `data/interim/orders.jsonl`: the High Court (and some Supreme Court) orders' own fields: title, date, court, bench size,
  the order's own citations (only the Supreme Court orders carry any; High Court orders have none in this dataset).

Output schema (one JSON object per line, sorted by `doc_id`):

| field | meaning |
|---|---|
| `doc_id` | the judgment's id, the same id the stores use |
| `court`, `court_level` | court name as published; 'SC', 'HC' or 'OTHER' |
| `date`, `year` | ISO decision date and its year (null when unknown) |
| `title` | the title as published |
| `case_name` | `title` without the docket prefix ('BAIL/3506/2025 of X Vs Y' -> 'X Vs Y'); what name matching reads |
| `neutral_citation` | '2011 INSC 772' when known, else null |
| `citations` | all formal citations: neutral, SCR, plus any the order itself lists |
| `case_number` | as published (often empty) |
| `bench_size` | number of judges when the order record has it, else null |
| `in_corpus` | true when an order with this id is in `orders.jsonl` (its text is in the stores unless excluded) |
| `source` | 'sc_metadata', 'orders' or 'both' |

A judgment that is only in `sc_metadata.jsonl` (`in_corpus` false) can be resolved and become a graph node but has no text.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.citation_graph.graph import court_level_of
from vakeel_sahayak.pipelines.citation_graph.resolve import clean_case_name
from vakeel_sahayak.pipelines.text_utils import normalise_date, read_jsonl

_NEUTRAL = re.compile(r"\b((?:19|20)\d{2})\s+INSC\s+(\d{1,5})\b")


def _citation_list(value: Any) -> list[str]:
    """Citations of a record's `citations` field (a list, a JSON-list string or one string)."""
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    text = str(value or "").strip()
    if text.startswith("["):
        try:
            loaded = json.loads(text)
            return [str(v) for v in loaded if str(v).strip()] if isinstance(loaded, list) else []
        except ValueError:
            return []
    return [text] if text else []


def _record(doc_id: str, raw: dict[str, Any], source: str, in_corpus: bool) -> dict[str, Any]:
    date = normalise_date(raw.get("date"))
    cites = _citation_list(raw.get("citations"))
    if raw.get("neutral_citation"):
        cites.insert(0, str(raw["neutral_citation"]))
    neutral = next((f"{m.group(1)} INSC {int(m.group(2))}" for c in cites if (m := _NEUTRAL.search(c))), None)
    bench = raw.get("bench_size")
    court = str(raw.get("court") or "") or None
    return {
        "doc_id": doc_id, "court": court, "court_level": court_level_of(court), "date": date,
        "year": int(date[:4]) if date else None, "title": str(raw.get("title") or "") or None,
        "case_name": clean_case_name(raw.get("title")) or None, "neutral_citation": neutral,
        "citations": list(dict.fromkeys(cites)), "case_number": str(raw.get("case_number") or ""),
        "bench_size": int(bench) if str(bench or "").isdigit() else None, "in_corpus": in_corpus, "source": source,
    }  # fmt: skip


def build_oil_metadata(sc_metadata_path: str, orders_path: str, out_path: str) -> dict[str, Any]:
    """Write `oil_metadata.jsonl` from the two sources and return the counts."""
    records: dict[str, dict[str, Any]] = {}
    for raw in read_jsonl(orders_path):
        doc_id = str(raw.get("doc_id") or "")
        if doc_id:
            records[doc_id] = _record(doc_id, raw, "orders", True)
    n_orders = len(records)
    n_sc = n_both = 0
    for raw in read_jsonl(sc_metadata_path):
        doc_id = str(raw.get("doc_id") or "")
        if not doc_id:
            continue
        n_sc += 1
        fresh = _record(doc_id, raw, "sc_metadata", False)
        have = records.get(doc_id)
        if have is None:
            records[doc_id] = fresh
            continue
        n_both += 1
        merged = {**fresh, "bench_size": have["bench_size"], "in_corpus": True, "source": "both"}
        merged["citations"] = list(dict.fromkeys([*fresh["citations"], *have["citations"]]))
        merged["neutral_citation"] = fresh["neutral_citation"] or have["neutral_citation"]
        records[doc_id] = merged
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for doc_id in sorted(records):
            fh.write(json.dumps(records[doc_id], ensure_ascii=False) + "\n")
    levels: dict[str, int] = {}
    for r in records.values():
        levels[r["court_level"]] = levels.get(r["court_level"], 0) + 1
    return {
        "records": len(records), "from_orders": n_orders, "from_sc_metadata": n_sc, "in_both": n_both,
        "sc_only_not_in_corpus": n_sc - n_both, "by_court_level": levels,
        "with_neutral_citation": sum(1 for r in records.values() if r["neutral_citation"]),
        "with_any_formal_citation": sum(1 for r in records.values() if r["citations"]),
    }  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    """CLI: `python -m vakeel_sahayak.pipelines.citation_graph.oil_metadata [--sc ...] [--orders ...] [--out ...]`."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sc", default="data/raw/open_india_law/sc_metadata.jsonl")
    ap.add_argument("--orders", default="data/interim/orders.jsonl")
    ap.add_argument("--out", default="data/interim/oil_metadata.jsonl")
    a = ap.parse_args(argv)
    print(json.dumps(build_oil_metadata(a.sc, a.orders, a.out), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
