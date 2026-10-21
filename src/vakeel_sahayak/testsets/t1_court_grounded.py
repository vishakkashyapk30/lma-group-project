"""T1 court-grounded bail set: 200 test orders (>=60 BNS-era), facts part as input, gold G1-G7 (plan §15.2; docs/evaluation-plan.md 2.5, 2.6).

Input: the cleanly split candidate orders (`parts_path`, JSON lines of {doc_id, court, date, offence_date, parts, optional split}) and the gold files
`g1.jsonl` .. `g7.jsonl` of `gold_dir` (each row {doc_id, labels, ...}). Rows with `split == "dev"` form the dev set (up to 50); the others are test candidates.

Rules, in order: High Courts only (Supreme Court judgments are excluded from dev and test); all five parts present; the facts part shares no 8-word
sequence with any other part (plan §15.1); all of G1-G7 present. From the test candidates the builder takes 200: first the BNS-era quota (at least 60,
offence on or after 2024-07-01), then orders dated after the Qwen3 release (2025-04, up to 80 so the blind slice can be post-release only), then the
rest, each time cycling across courts with a seeded draw. Too few candidates, or fewer than 60 BNS-era ones, is a ValueError.

The 200 are split into the open test part (120) and the blind slice (80, at least 25 BNS-era, post-release orders first). Blind ids are stored only as
hashes (`manifest_blind.json`); the ids sit in `blind_sealed.json`, opened once through `testsets.blind.open_blind`. Outputs in `out_dir`: `cases.jsonl`
(all 200, in a fixed seeded run order, no role marker), `dev.jsonl`, `manifest.json` (with per-court, per-script and coverage statistics), `manifest_dev.json`,
`manifest_open.json`, `manifest_blind.json`, `blind_sealed.json`.

CLI: `python -m vakeel_sahayak.testsets.t1_court_grounded [--orders ... --splits ... --out ...]` prepares candidates from data/interim and builds T1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.leakage import assert_no_overlap
from vakeel_sahayak.pipelines.splits import order_is_bns_era
from vakeel_sahayak.pipelines.text_utils import read_jsonl, write_jsonl
from vakeel_sahayak.schemas.enums import OrderPart
from vakeel_sahayak.testsets.blind import seal_blind
from vakeel_sahayak.testsets.common import TestSetManifest, write_manifest

SEED = 20241024
SIZE, DEV_N, OPEN_N, BLIND_N = 200, 50, 120, 80
MIN_BNS, MIN_BLIND_BNS = 60, 25
QWEN3_RELEASE = "2025-04-01"
BNS_CUTOFF = "2024-07-01"
GOLD_IDS = [f"G{k}" for k in range(1, 8)]
PARTS = [p.value for p in OrderPart]
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def _is_high_court(court: str) -> bool:
    c = (court or "").lower()
    return "high court" in c and "supreme" not in c


def _script(text: str) -> str:
    """'devanagari' (more than 50% of letters), 'mixed' (more than 5%) or 'latin'."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "latin"
    share = len(DEVANAGARI.findall(text)) / len(letters)
    return "devanagari" if share > 0.5 else "mixed" if share > 0.05 else "latin"


def _read_gold(gold_dir: str) -> dict[str, dict[str, dict[str, Any]]]:
    """gold id -> doc_id -> record (the row without doc_id and gold id)."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for k in range(1, 8):
        path = Path(gold_dir) / f"g{k}.jsonl"
        rows = read_jsonl(str(path)) if path.exists() else []
        out[f"G{k}"] = {str(r["doc_id"]): {kk: v for kk, v in r.items() if kk not in ("doc_id", "gold")} for r in rows if r.get("doc_id")}
    return out


def _clean(row: dict[str, Any], gold: dict[str, dict[str, dict[str, Any]]]) -> str | None:
    """None when the order qualifies, else the reason it is left out."""
    if not _is_high_court(str(row.get("court") or "")):
        return "not_high_court"
    parts = row.get("parts") or {}
    if any(not str(parts.get(p) or "").strip() for p in PARTS):
        return "incomplete_parts"
    if any(str(row["doc_id"]) not in gold[g] for g in GOLD_IDS):
        return "incomplete_gold"
    try:
        assert_no_overlap(str(parts["facts"]), [str(parts[p]) for p in PARTS if p != "facts"], 8)
    except ValueError:
        return "facts_overlap_8gram"
    return None


def _round_robin(rows: list[dict[str, Any]], n: int, rng: random.Random) -> list[dict[str, Any]]:
    """Up to `n` rows cycling across courts (seeded shuffle of rows and of the court order)."""
    by_court: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: str(r["doc_id"])):
        by_court[str(r.get("court"))].append(r)
    for items in by_court.values():
        rng.shuffle(items)
    courts = sorted(by_court)
    rng.shuffle(courts)
    out: list[dict[str, Any]] = []
    while len(out) < n and any(by_court.values()):
        for c in courts:
            if by_court[c] and len(out) < n:
                out.append(by_court[c].pop())
    return out


def _take(pool: list[dict[str, Any]], chosen: list[dict[str, Any]], n: int, pred: Any, rng: random.Random) -> None:
    """Add up to `n` more rows matching `pred` (not yet chosen) to `chosen`."""
    taken = {str(r["doc_id"]) for r in chosen}
    chosen.extend(_round_robin([r for r in pool if str(r["doc_id"]) not in taken and pred(r)], n, rng))


def _flags(row: dict[str, Any]) -> dict[str, Any]:
    facts = str(row["parts"]["facts"])
    return {"bns_era": order_is_bns_era({"offence_date": row.get("offence_date"), "text": facts}, BNS_CUTOFF),
            "post_release": str(row.get("date") or "") >= QWEN3_RELEASE}


def _case(row: dict[str, Any], case_id: str, gold: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    f = _flags(row)
    doc = str(row["doc_id"])
    facts = str(row["parts"]["facts"])
    return {"case_id": case_id, "doc_id": doc, "court": row.get("court"), "date": row.get("date"), "before": row.get("date"), "facts_text": facts,
            "bns_era": f["bns_era"], "post_release": f["post_release"], "script": _script(facts), "gold": {g: gold[g][doc] for g in GOLD_IDS}}


def _run_order_key(doc_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}|{doc_id}".encode()).hexdigest()


def _pick_blind(selected: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    """80 rows: at least 25 BNS-era, post-release orders first (exactly the post-release orders when there are 80 or more)."""
    blind: list[dict[str, Any]] = []
    post = lambda r: _flags(r)["post_release"]  # noqa: E731
    bns = lambda r: _flags(r)["bns_era"]  # noqa: E731
    _take(selected, blind, MIN_BLIND_BNS, lambda r: bns(r) and post(r), rng)
    _take(selected, blind, MIN_BLIND_BNS - sum(1 for r in blind if bns(r)), lambda r: bns(r), rng)
    _take(selected, blind, BLIND_N - len(blind), post, rng)
    _take(selected, blind, BLIND_N - len(blind), lambda r: True, rng)
    return blind


def _stats(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts per court, era, script and coverage of the gold records for a group of cases."""
    n = len(cases) or 1
    g2 = [c["gold"]["G2"] for c in cases]
    raw = sum(len(g.get("raw") or []) for g in g2)
    resolved = sum(len(g.get("labels") or []) for g in g2 if "raw" in g)
    g3_fields = [c["gold"]["G3"].get("fields") for c in cases if isinstance(c["gold"]["G3"].get("fields"), dict)]
    names = sorted({k for f in g3_fields for k in f})
    return {
        "n": len(cases), "per_court": dict(sorted(Counter(str(c["court"]) for c in cases).items())),
        "per_era": {"bns": sum(c["bns_era"] for c in cases), "ipc": sum(not c["bns_era"] for c in cases)},
        "post_release_2025_04": sum(c["post_release"] for c in cases),
        "per_script": dict(Counter(c["script"] for c in cases)),
        "citation_resolution_coverage": {"extracted": raw, "resolved": resolved, "share": round(resolved / raw, 4) if raw else None,
                                         "orders_with_a_resolved_citation": sum(1 for g in g2 if g.get("labels"))},
        "dossier_field_coverage": {f: round(sum(1 for d in g3_fields if d.get(f) not in (None, [], "")) / max(1, len(g3_fields)), 4) for f in names},
        "gold_status": dict(Counter(str(c["gold"][g].get("status", "n/a")) + f"/{g}" for c in cases for g in ("G1", "G3", "G5"))),
        "gold_nonempty_share": {g: round(sum(1 for c in cases if c["gold"][g].get("labels")) / n, 4) for g in GOLD_IDS},
    }


def build_t1_with(parts_path: str, gold_dir: str, out_dir: str, *, seed: int = SEED) -> TestSetManifest:
    """The builder behind `build_t1`, with a seed argument.

    Raises:
        ValueError: fewer than 200 qualifying test candidates, or fewer than 60 of them BNS-era.
    """
    rng = random.Random(seed)
    gold = _read_gold(gold_dir)
    rows = read_jsonl(parts_path)
    dev_rows, test_rows, dropped = [], [], Counter()
    for r in rows:
        if not r.get("doc_id"):
            continue
        why = _clean(r, gold)
        if why:
            dropped[f"{r.get('split') or 'test'}:{why}"] += 1
            continue
        (dev_rows if r.get("split") == "dev" else test_rows).append(r)
    bns_pool = sum(1 for r in test_rows if _flags(r)["bns_era"])
    if len(test_rows) < SIZE:
        raise ValueError(f"only {len(test_rows)} qualifying High Court test candidates; T1 needs {SIZE}")
    if bns_pool < MIN_BNS:
        raise ValueError(f"only {bns_pool} BNS-era candidates; the plan needs at least {MIN_BNS} in T1")
    selected: list[dict[str, Any]] = []
    _take(test_rows, selected, MIN_BNS, lambda r: _flags(r)["bns_era"], rng)
    _take(test_rows, selected, BLIND_N, lambda r: _flags(r)["post_release"] or False, rng)  # reserve room for a post-release blind slice
    _take(test_rows, selected, SIZE - len(selected), lambda r: True, rng)
    selected = selected[:SIZE]
    blind = _pick_blind(selected, rng)
    blind_ids = {str(r["doc_id"]) for r in blind}
    ordered = sorted(selected, key=lambda r: _run_order_key(str(r["doc_id"]), seed))
    cases = [_case(r, f"t1-{i:03d}", gold) for i, r in enumerate(ordered)]
    by_doc = {c["doc_id"]: c for c in cases}
    blind_cases = [by_doc[d] for d in sorted(blind_ids)]
    open_cases = [c for c in cases if c["doc_id"] not in blind_ids]
    dev_sel = _round_robin(dev_rows, DEV_N, rng)
    dev_cases = [_case(r, f"t1dev-{i:03d}", gold) for i, r in enumerate(sorted(dev_sel, key=lambda r: _run_order_key(str(r["doc_id"]), seed)))]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(str(out / "cases.jsonl"), cases)
    write_jsonl(str(out / "dev.jsonl"), dev_cases)
    manifest_dev = {"slice": "dev", "n": len(dev_cases), "case_ids": [c["case_id"] for c in dev_cases], "doc_ids": [c["doc_id"] for c in dev_cases]}
    manifest_open = {"slice": "open", "n": len(open_cases), "case_ids": [c["case_id"] for c in open_cases], "doc_ids": [c["doc_id"] for c in open_cases]}
    (out / "manifest_dev.json").write_text(json.dumps(manifest_dev, indent=1), encoding="utf-8")
    (out / "manifest_open.json").write_text(json.dumps(manifest_open, indent=1), encoding="utf-8")
    hashed = seal_blind([c["case_id"] for c in blind_cases], str(out))
    first = lambda k: cases[:k]  # noqa: E731
    details = {
        "seed": seed, "sizes": {"test": len(cases), "dev": len(dev_cases), "open": len(open_cases), "blind": len(blind_cases)},
        "targets_met": {"test_200": len(cases) == SIZE, "dev_50": len(dev_cases) == DEV_N, "open_120": len(open_cases) == OPEN_N,
                        "blind_80": len(blind_cases) == BLIND_N, "bns_ge_60": sum(c["bns_era"] for c in cases) >= MIN_BNS,
                        "blind_bns_ge_25": sum(c["bns_era"] for c in blind_cases) >= MIN_BLIND_BNS,
                        "blind_all_post_release": all(c["post_release"] for c in blind_cases)},
        "pool": {"high_court_test_candidates": len(test_rows), "bns_era": bns_pool,
                 "post_release": sum(1 for r in test_rows if _flags(r)["post_release"]), "dev_candidates": len(dev_rows),
                 "left_out": dict(sorted(dropped.items()))},
        "test": _stats(cases), "dev": _stats(dev_cases), "open": _stats(open_cases),
        "blind": {**_stats(blind_cases), "per_court": None, "note": "ids are hashes only in manifest_blind.json; only counts are public here"},
        "post_release_subset": {"definition": f"date >= {QWEN3_RELEASE}", "test": sum(c["post_release"] for c in cases),
                                "open_case_ids": [c["case_id"] for c in open_cases if c["post_release"]],
                                "blind_count": sum(c["post_release"] for c in blind_cases)},
        "run_order_prefix": {"first_100_bns": sum(c["bns_era"] for c in first(100)), "first_60_bns": sum(c["bns_era"] for c in first(60))},
        "blind_set_hash": hashed["set_hash"], "blind_hashes": hashed["n"],
        "case_ids": {"test": "numbered in the fixed seeded run order (no role marker)", "dev": "numbered t1dev-*"},
    }
    manifest = TestSetManifest(set_id="T1", size=len(cases), answers_from="G1-G7 (court text, rule labels agreed with the non-Qwen labeler where available)",
                               used_for=["RQ1", "F1", "F3", "F5", "F6", "F7"], path=str(out), details=details)
    write_manifest(manifest, str(out))
    return manifest


def build_t1(parts_path: str, gold_dir: str, out_dir: str) -> TestSetManifest:
    """Sample and package T1.

    Args:
        parts_path: cleanly split candidate orders (JSON lines with `parts`; `split == "dev"` rows form the dev set)
        gold_dir: folder with g1.jsonl .. g7.jsonl
        out_dir: where cases, dev set and the manifests go

    Returns:
        Manifest (size 200; details hold the per-court, per-script and coverage statistics).
    """
    return build_t1_with(parts_path, gold_dir, out_dir)


# ---------------------------------------------------------------------------------------------------------------- CLI over the real interim data
def prepare_candidates(orders_path: str, splits_path: str, work_dir: str) -> str:
    """Candidates for T1 from data/interim: clean-split High Court orders of the dev and test windows, split into parts, with their gold files.

    Writes `work_dir/parts.jsonl` (rows carry `split` = dev | test by date window) and `work_dir/gold/g1..g7.jsonl`; returns the parts path.
    """
    import os

    os.environ.setdefault("VS_MODELS", "offline")  # no labeler is called: gold stays rule-only (provisional) until the non-Qwen labeler runs
    from vakeel_sahayak.pipelines.gold import (
        g1_defense_factors,
        g2_cited_precedents,
        g3_dossier_fields,
        g4_prosecution_objections,
        g5_court_factors,
        g6_conditions,
        g7_rights_computations,
    )
    from vakeel_sahayak.pipelines.order_splitter import analyse_split
    from vakeel_sahayak.pipelines.splits import _splits_config

    cfg = _splits_config()
    dev, test = cfg.get("dev", {}), cfg.get("test", {})
    work = Path(work_dir)
    (work / "gold").mkdir(parents=True, exist_ok=True)
    kept = []
    for o in read_jsonl(orders_path):
        d, court = str(o.get("date") or ""), str(o.get("court") or "")
        if not _is_high_court(court) or o.get("clean_split") is False:
            continue
        window = "dev" if str(dev.get("from")) <= d <= str(dev.get("to")) else "test" if str(test.get("from")) <= d <= str(test.get("to")) else None
        if window is None:
            continue
        res = analyse_split(str(o.get("text") or ""))
        if res.clean:
            meta = {k: v for k, v in o.items() if k not in ("text", "full_text")}
            kept.append({**meta, "split": window, "parts": {p.value: t for p, t in res.parts.items()}})
    parts_path = str(work / "parts.jsonl")
    write_jsonl(parts_path, kept)
    for k, mod in enumerate([g1_defense_factors, g2_cited_precedents, g3_dossier_fields, g4_prosecution_objections, g5_court_factors,
                             g6_conditions, g7_rights_computations], start=1):
        mod.build_gold(parts_path, str(work / "gold" / f"g{k}.jsonl"))
    return parts_path


def update_splits(splits_path: str, out_dir: str) -> dict[str, int]:
    """Rewrite `splits.json` so its dev and test labels are exactly the T1 dev and test orders (a backup `.pre-t1` is kept; train labels stay)."""
    p = Path(splits_path)
    backup = p.with_suffix(p.suffix + ".pre-t1")
    if not backup.exists():
        backup.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    labels = {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if v == "train"}
    for name, file in (("test", "cases.jsonl"), ("dev", "dev.jsonl")):
        for c in read_jsonl(str(Path(out_dir) / file)):
            labels[str(c["doc_id"])] = name
    p.write_text(json.dumps(labels, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return dict(Counter(labels.values()))


def main(argv: list[str] | None = None) -> int:
    """CLI: prepare candidates from the interim data, build T1, optionally rewrite splits.json; `--open-blind` opens the sealed ids once."""
    from vakeel_sahayak.config import load_config

    paths = load_config().paths
    ap = argparse.ArgumentParser(description="Build T1 (court-grounded set)")
    ap.add_argument("--orders", default=str(Path(paths.interim_dir) / "orders.jsonl"))
    ap.add_argument("--splits", default=str(Path(paths.interim_dir) / "splits.json"))
    ap.add_argument("--out", default=str(Path(paths.testsets_dir) / "t1"))
    ap.add_argument("--work", default=str(Path(paths.interim_dir) / "t1_work"))
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--update-splits", action="store_true", help="make splits.json's dev/test labels the T1 ones (backup kept)")
    ap.add_argument("--open-blind", action="store_true", help="open the sealed blind ids once (needs the freeze tag; writes data/eval/blind.lock)")
    args = ap.parse_args(argv)
    if args.open_blind:
        from vakeel_sahayak.testsets.blind import open_blind

        print("\n".join(open_blind(args.out, confirm=True)))
        return 0
    parts = args.work and prepare_candidates(args.orders, args.splits, args.work)
    manifest = build_t1_with(parts, str(Path(args.work) / "gold"), args.out, seed=args.seed)
    print(json.dumps({k: v for k, v in manifest.details.items() if k in ("sizes", "targets_met", "pool")}, indent=1))
    if args.update_splits:
        print("splits.json labels:", update_splits(args.splits, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
