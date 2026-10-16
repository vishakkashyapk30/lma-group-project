"""Date-based train/dev/test splits (plan §2): train before 2024; dev early 2024 (50 orders); test mid-2024 to 2025 (200 orders, >=60 BNS-era).

Windows, sample sizes and the BNS-era date come from configs/splits.yaml. Orders in a gap (April-May 2024), orders
outside every window, and eligible orders that were not sampled are labelled `unused`: they are not training data and
not test data. Dev and test orders must split cleanly (plan §15.1), so only orders whose text splits cleanly (or that
carry pre-split `parts`) are eligible.
"""

from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.order_splitter import analyse_split
from vakeel_sahayak.pipelines.section_extract import extract_sections
from vakeel_sahayak.pipelines.text_utils import normalise_date, read_jsonl

log = logging.getLogger(__name__)


def _splits_config() -> dict[str, Any]:
    """The `splits` block of the configuration."""
    from vakeel_sahayak.config import load_config

    return load_config().splits


def is_bns_era(offence_date: str, cutoff: str | None = None) -> bool:
    """Offence on or after 1 July 2024.

    Args:
        offence_date: ISO date; other written forms are normalised first
        cutoff: ISO BNS start date; read from the configuration when omitted (pass it in loops)

    Returns:
        bool. An unparseable date is not BNS-era.
    """
    iso = normalise_date(offence_date)
    if not iso:
        return False
    cutoff = cutoff or str(_splits_config().get("bns_era_offence_on_or_after", "2024-07-01"))
    return date.fromisoformat(iso) >= date.fromisoformat(cutoff)


def order_is_bns_era(order: dict[str, Any], cutoff: str | None = None) -> bool:
    """BNS-era status of an order record: the offence date if known, else whether its text charges BNS/BNSS sections.

    Args:
        order: record with optional `offence_date`, `text`
        cutoff: see `is_bns_era`

    Returns:
        bool.
    """
    offence = normalise_date(order.get("offence_date"))
    if offence:
        return is_bns_era(offence, cutoff)
    refs = extract_sections(str(order.get("text") or ""))
    return any(r.startswith("BNS ") for r in refs) and not any(r.startswith("IPC ") for r in refs)


def _splits_cleanly(order: dict[str, Any]) -> bool:
    """True when the order carries a recorded `clean_split` verdict, pre-split parts, or text that passes the clean-split test; True if no text is given."""
    if isinstance(order.get("clean_split"), bool):  # the verdict of `analyse_split`, recorded at ingest (oil_ingest) to avoid re-splitting
        return bool(order["clean_split"])
    if order.get("parts"):
        return all(str(v).strip() for v in dict(order["parts"]).values()) and len(order["parts"]) == 5
    text = order.get("text") or order.get("full_text")
    return analyse_split(str(text)).clean if text else True


def _round_robin_by_court(orders: list[dict[str, Any]], n: int, rng: random.Random) -> list[dict[str, Any]]:
    """Take up to `n` orders cycling across courts so no High Court dominates (plan §2)."""
    by_court: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for o in orders:
        by_court[str(o.get("court") or "unknown")].append(o)
    for items in by_court.values():
        rng.shuffle(items)
    courts = sorted(by_court)
    rng.shuffle(courts)
    chosen: list[dict[str, Any]] = []
    while len(chosen) < n and any(by_court.values()):
        for court in courts:
            if by_court[court] and len(chosen) < n:
                chosen.append(by_court[court].pop())
    return chosen


def assign_splits(orders_path: str, out_path: str, seed: int = 0) -> dict[str, int]:
    """Assign split labels; sample dev and test across High Courts.

    Input: JSONL, one order per line with `doc_id`, `date`, optionally `court`, `offence_date`, `text` or `parts`.
    Output `out_path`: one JSON object `{doc_id: "train" | "dev" | "test"}`. Orders in no split (the April-May 2024
    gap, outside every window, undated, unsampled, or whose text does not split cleanly) are omitted. A BNS-era
    shortfall against the configured minimum is logged as a warning.

    Args:
        orders_path: see behaviour
        out_path: see behaviour
        seed: sampling seed (deterministic)

    Returns:
        Counts per split: `{"train": n, "dev": n, "test": n}`.
    """
    cfg = _splits_config()
    train_before = str(cfg.get("train", {}).get("before", "2024-01-01"))
    dev, test = cfg.get("dev", {}), cfg.get("test", {})
    cutoff = str(cfg.get("bns_era_offence_on_or_after", "2024-07-01"))
    rng = random.Random(seed)
    label: dict[str, str] = {}
    dev_pool: list[dict[str, Any]] = []
    test_pool: list[dict[str, Any]] = []
    for o in read_jsonl(orders_path):
        d = normalise_date(o.get("date"))
        if not o.get("doc_id") or not d:
            continue
        o = {**o, "date": d}
        doc = str(o["doc_id"])
        if d < train_before:
            label[doc] = "train"
        elif str(dev.get("from", "")) <= d <= str(dev.get("to", "")) and _splits_cleanly(o):
            dev_pool.append(o)
        elif str(test.get("from", "")) <= d <= str(test.get("to", "")) and _splits_cleanly(o):
            test_pool.append(o)
    for o in _round_robin_by_court(dev_pool, int(dev.get("n", 50)), rng):
        label[str(o["doc_id"])] = "dev"
    min_bns = int(test.get("min_bns_era", 60))
    chosen_test = _choose_test(test_pool, int(test.get("n", 200)), min_bns, rng, cutoff)
    for o in chosen_test:
        label[str(o["doc_id"])] = "test"
    n_bns = sum(1 for o in chosen_test if order_is_bns_era(o, cutoff))
    if n_bns < min_bns:
        log.warning("test split has %d BNS-era orders; the plan asks for at least %d", n_bns, min_bns)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(label, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    return {k: sum(1 for v in label.values() if v == k) for k in ("train", "dev", "test")}


def read_splits(path: str | Path) -> dict[str, str]:
    """Read a splits file: a JSON object `{doc_id: split}` (also accepts JSONL rows with `doc_id` and `split`).

    Args:
        path: file written by `assign_splits`

    Returns:
        doc id to split name.
    """
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    rows = data if isinstance(data, list) else [json.loads(line) for line in text.splitlines() if line.strip()]
    return {str(r["doc_id"]): str(r.get("split")) for r in rows if r.get("doc_id")}


def _choose_test(
    pool: list[dict[str, Any]], n: int, min_bns: int, rng: random.Random, cutoff: str | None = None
) -> list[dict[str, Any]]:
    """Sample the test set: first the BNS-era quota across courts, then the remainder from everything left."""
    bns = [o for o in pool if order_is_bns_era(o, cutoff)]
    first = _round_robin_by_court(bns, min(min_bns, n), rng)
    taken = {str(o["doc_id"]) for o in first}
    rest = [o for o in pool if str(o["doc_id"]) not in taken]
    return first + _round_robin_by_court(rest, n - len(first), rng)
