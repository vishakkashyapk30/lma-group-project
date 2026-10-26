"""Build the S6 / B5 store-prior training orders and train the prior (offline, no model call, no manual label).

Source: `data/interim/orders.jsonl` + `splits.json`. Only TRAIN-split High Court orders dated before 2024 with a clean split are eligible; every test or
dev id, and every order that shares an FIR with a test order (`pipelines.leakage.excluded_doc_ids`, the 464 excluded T1 ids), is dropped. At most
`--n` orders are sampled, balanced round-robin over (court, BNS era). Labels are the court's own text read by the rule labelers (G1 rule labels,
G2 resolved citations, G3 sections) and the order's split parts; no hosted or local model is called.

    .venv/bin/python scripts/build_store_prior_train.py [--n 1500] [--out-dir data/eval] [--seed 17]

Writes `<out-dir>/store_prior_train_orders.jsonl`, `<out-dir>/store_prior.json` (the artefact) and `<out-dir>/store_prior_manifest.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("VS_MODELS", "offline")
os.environ.setdefault("VS_LLM_BACKEND", "offline")
REPO = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--interim", default=str(Path(os.environ.get("VS_DATA_DIR") or REPO / "data") / "interim"))
    ap.add_argument("--out-dir", default=str(Path(os.environ.get("VS_DATA_DIR") or REPO / "data") / "eval"))
    a = ap.parse_args(argv)
    from vakeel_sahayak.agents.sutradhar.store_prior import train_from_file
    from vakeel_sahayak.pipelines.gold import g2_cited_precedents as g2mod
    from vakeel_sahayak.pipelines.gold import g3_dossier_fields as g3mod
    from vakeel_sahayak.pipelines.gold.g1_defense_factors import label_detail as g1_detail
    from vakeel_sahayak.pipelines.leakage import excluded_doc_ids
    from vakeel_sahayak.pipelines.order_splitter import analyse_split
    from vakeel_sahayak.pipelines.splits import read_splits
    from vakeel_sahayak.schemas.enums import OrderPart

    interim = Path(a.interim)
    orders_path, splits_path = str(interim / "orders.jsonl"), str(interim / "splits.json")
    splits = read_splits(splits_path)
    excluded = excluded_doc_ids(splits_path, orders_path)
    strata: dict[tuple[str, bool], list[str]] = defaultdict(list)
    seen = 0
    with open(orders_path, encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            seen += 1
            did, court = str(o.get("doc_id") or ""), str(o.get("court") or "")
            if splits.get(did) != "train" or did in excluded or str(o.get("date") or "9") >= "2024-01-01":
                continue
            if "high court" not in court.lower() or o.get("clean_split") is False:
                continue
            strata[(court, bool(o.get("bns_era")))].append(did)
    rng = random.Random(a.seed)
    for ids in strata.values():
        ids.sort()
        rng.shuffle(ids)
    keys = sorted(strata)
    chosen: list[str] = []
    while len(chosen) < a.n and any(strata[k] for k in keys):
        for k in keys:
            if strata[k] and len(chosen) < a.n:
                chosen.append(strata[k].pop())
    want = set(chosen)
    records, dropped_split = [], 0
    index = None
    meta_path = g2mod.metadata_file(orders_path)
    if meta_path:
        from vakeel_sahayak.pipelines.citation_graph.resolve import load_index

        index = load_index(str(meta_path))
    with open(orders_path, encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            did = str(o.get("doc_id") or "")
            if did not in want:
                continue
            res = analyse_split(str(o.get("text") or ""))
            if not res.clean:
                dropped_split += 1
                continue
            parts = {p.value: t for p, t in res.parts.items()}
            op = {OrderPart(k): v for k, v in parts.items() if k in {p.value for p in OrderPart}}
            d1, d2, d3 = g1_detail(op), g2mod.label_detail(op, index), g3mod.label_detail(op)
            records.append({
                "doc_id": did, "court": o.get("court"), "date": o.get("date"), "split": "train", "bns_era": bool(o.get("bns_era")),
                "parts": parts,
                "gold": {"G1": {"labels": d1.get("rule_labels") or []}, "G2": {k: d2.get(k) for k in ("labels", "raw", "unresolved")},
                         "G3": {"fields": d3.get("fields") or {}}},
            })
    records.sort(key=lambda r: r["doc_id"])
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    train_path = out / "store_prior_train_orders.jsonl"
    train_path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records), encoding="utf-8")
    result = train_from_file(train_path, out / "store_prior.json")
    by_court: dict[str, int] = defaultdict(int)
    for r in records:
        by_court[f"{r['court']} | {'bns' if r['bns_era'] else 'ipc'}"] += 1
    manifest = {
        "artefact": result["path"], "digest": result["digest"], "train_orders_file": str(train_path),
        "train_orders_sha256": hashlib.sha256(train_path.read_bytes()).hexdigest(), "seed": a.seed, "requested": a.n,
        "orders_scanned": seen, "excluded_ids": len(excluded), "eligible_strata": len(keys), "sampled": len(chosen), "split_unclean_dropped": dropped_split,
        "records": len(records), "trainer_stats": {k: v for k, v in result.items() if k not in ("digest", "path")}, "by_court_era": dict(sorted(by_court.items())),
        "label_provenance": "rule labelers on the court's own order text (G1 rule_labels, G2 resolved citations via oil_metadata, G3 rule fields, split parts); train split before 2024 only; "
                            "test, dev, blind and same-FIR orders excluded; no model call, no manual label",
    }
    (out / "store_prior_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "by_court_era"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
