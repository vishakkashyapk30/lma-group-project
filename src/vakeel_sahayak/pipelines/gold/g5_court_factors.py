"""Gold label G5: Factors the court discussed (plan §15.1). From: reasoning. Method: Keyword rules and Llama; agreed only."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.pipelines.gold.common import agreed_view, factor_gold, run_gold
from vakeel_sahayak.schemas.enums import OrderPart


def build_gold(parts_path: str, out_path: str) -> int:
    """Build G5 for every cleanly split test order.

    Args:
        parts_path: JSONL from `order_splitter.split_all`
        out_path: output JSONL (record format in `gold/common.py`)

    Returns:
        Number of orders labelled.
    """
    return run_gold("G5", parts_path, out_path, label_detail)


def label_order(parts: dict[OrderPart, str]) -> dict[str, Any]:
    """Label one order: the agreed labels only (`label_detail` without the per-labeler lists).

    Args:
        parts: the five order parts

    Returns:
        Gold record fields without `rule_labels` and `llm_labels`.
    """
    return agreed_view(label_detail(parts))


def label_detail(parts: dict[OrderPart, str]) -> dict[str, Any]:
    """Label one order for G5; keep only labels both labelers agree on.

    Args:
        parts: the five order parts

    Returns:
        Gold record fields: factor values the rules find in the reasoning.
    """
    return factor_gold(parts, OrderPart.REASONING)
