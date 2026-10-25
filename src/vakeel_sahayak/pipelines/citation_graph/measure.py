"""Citation resolution rate on a fixed, seeded sample of citation occurrences (VI-05; docs/evaluation-plan.md M10, M42).

`draw_sample` reads the reasoning part of a seeded random subset of the interim orders, extracts every citation
occurrence and keeps (a) a uniform sample of `n_uniform` occurrences (the headline rate) and (b) up to `per_format`
occurrences of each format (so INSC, SCC OnLine and Cri LJ, which are rare, still get a rate). `measure` resolves the
sample with any `CitationIndex` and reports the rate per format. Ground truth is not needed: the rate is coverage, not
accuracy (accuracy is T9's job).

CLI: `python -m vakeel_sahayak.pipelines.citation_graph.measure draw|measure ...` (see `main`).
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.citation_graph.extract import extract_citations, parse_citation
from vakeel_sahayak.pipelines.text_utils import read_jsonl, write_jsonl

SEED = 20261025


def draw_sample(
    orders_path: str, out_path: str, *, seed: int = SEED, n_orders: int = 40000, n_uniform: int = 2000, per_format: int = 250
) -> dict[str, Any]:
    """Draw the sample and write it as JSONL (`citing_doc_id`, `raw`, `kind`, `stratum`: 'uniform' and/or 'format')."""
    from vakeel_sahayak.pipelines.order_splitter import analyse_split
    from vakeel_sahayak.schemas.enums import OrderPart

    ids: list[str] = []
    for row in read_jsonl(orders_path):
        ids.append(str(row.get("doc_id")))
    rng = random.Random(seed)
    chosen = set(rng.sample(ids, min(n_orders, len(ids))))
    occurrences: list[dict[str, Any]] = []
    for row in read_jsonl(orders_path):
        doc_id = str(row.get("doc_id"))
        if doc_id not in chosen:
            continue
        reasoning = analyse_split(str(row.get("text") or "")).parts.get(OrderPart.REASONING, "")
        for raw in extract_citations(reasoning):
            parsed = parse_citation(raw)
            occurrences.append({"citing_doc_id": doc_id, "raw": raw, "kind": parsed.kind if parsed else "unknown"})
    occurrences.sort(key=lambda r: (r["citing_doc_id"], r["raw"]))
    uniform = rng.sample(range(len(occurrences)), min(n_uniform, len(occurrences)))
    by_kind: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(occurrences):
        by_kind[r["kind"]].append(i)
    strat: set[int] = set()
    for kind in sorted(by_kind):
        strat.update(rng.sample(by_kind[kind], min(per_format, len(by_kind[kind]))))
    picked = sorted(set(uniform) | strat)
    rows = [{**occurrences[i], "stratum": [s for s, ok in (("uniform", i in set(uniform)), ("format", i in strat)) if ok]} for i in picked]
    write_jsonl(out_path, rows)
    return {
        "seed": seed, "orders_sampled": len(chosen), "occurrences_in_those_orders": len(occurrences),
        "occurrences_by_kind": dict(Counter(r["kind"] for r in occurrences)), "sample_rows": len(rows),
        "uniform_rows": len(uniform),
    }  # fmt: skip


def measure(index: Any, sample_path: str) -> dict[str, Any]:
    """Resolve the sample with `index`: rate overall on the uniform stratum and per format on the format stratum."""
    uni = [0, 0]
    per: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    uni_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in read_jsonl(sample_path):
        hit = 1 if index.resolve(row["raw"]) else 0
        if "uniform" in row["stratum"]:
            uni[0] += 1
            uni[1] += hit
            uni_kind[row["kind"]][0] += 1
            uni_kind[row["kind"]][1] += hit
        if "format" in row["stratum"]:
            per[row["kind"]][0] += 1
            per[row["kind"]][1] += hit
    rate = lambda s: round(s[1] / s[0], 4) if s[0] else None  # noqa: E731
    return {
        "uniform": {"n": uni[0], "resolved": uni[1], "rate": rate(uni)},
        "uniform_by_format": {k: {"n": v[0], "resolved": v[1], "rate": rate(v)} for k, v in sorted(uni_kind.items())},
        "per_format_sample": {k: {"n": v[0], "resolved": v[1], "rate": rate(v)} for k, v in sorted(per.items())},
    }


def main(argv: list[str] | None = None) -> int:
    """`draw --orders O --out S` or `measure --sample S --metadata M [--orders O] --out R` (index: records of M, plus the orders' own fields)."""
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    d.add_argument("--orders", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--seed", type=int, default=SEED)
    m = sub.add_parser("measure")
    m.add_argument("--sample", required=True)
    m.add_argument("--orders", help="orders.jsonl: its titles and citations are indexed (the 'before' index when used alone)")
    m.add_argument("--metadata", help="oil_metadata.jsonl to add to the index")
    m.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "draw":
        info = draw_sample(a.orders, a.out, seed=a.seed)
        print(json.dumps(info, indent=1))
        return 0
    from vakeel_sahayak.pipelines.store_builders.fast_index import FastCitationIndex

    records: list[dict[str, Any]] = []
    if a.orders:
        records += [
            {"doc_id": r.get("doc_id"), "title": r.get("title"), "court": r.get("court"), "date": r.get("date"), "citations": r.get("citations")}
            for r in read_jsonl(a.orders)
        ]
    if a.metadata:
        records += list(read_jsonl(a.metadata))
    result = measure(FastCitationIndex(records), a.sample)
    result["index_records"] = len(records)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
