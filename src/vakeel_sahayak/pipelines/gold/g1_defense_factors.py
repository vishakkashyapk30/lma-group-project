"""Gold label G1: Factors the defense argued (plan §15.1). From: defense submissions. Method: Keyword rules and Llama-3.1-8B; agreed only."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.pipelines.gold.common import agreed_view, factor_gold, run_gold
from vakeel_sahayak.schemas.enums import OrderPart


def build_gold(parts_path: str, out_path: str) -> int:
    """Build G1 for every cleanly split test order.

    Args:
        parts_path: JSONL from `order_splitter.split_all`
        out_path: output JSONL (record format in `gold/common.py`)

    Returns:
        Number of orders labelled.
    """
    return run_gold("G1", parts_path, out_path, label_detail)


def label_order(parts: dict[OrderPart, str]) -> dict[str, Any]:
    """Label one order: the agreed labels only (`label_detail` without the per-labeler lists).

    Args:
        parts: the five order parts

    Returns:
        Gold record fields without `rule_labels` and `llm_labels`.
    """
    return agreed_view(label_detail(parts))


def label_detail(parts: dict[OrderPart, str]) -> dict[str, Any]:
    """Label one order for G1; keep only labels both labelers agree on.

    Args:
        parts: the five order parts

    Returns:
        Gold record fields: factor values the rules find in the defense submissions.
    """
    return factor_gold(parts, OrderPart.DEFENSE)
