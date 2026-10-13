"""Gold label G7: Rights computations the court states itself (custody vs 60/90 days, s.436A/479 thresholds) (plan §15.1). From: reasoning. Method: Keywords (167(2), 187(3), default bail, 436A, 479) and Llama; agreed only."""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.pipelines.gold.common import active_labeler, agreed_view, combine, run_gold
from vakeel_sahayak.pipelines.order_facts import custody_days
from vakeel_sahayak.schemas.enums import OrderPart, RightsCheckName

# Keywords of the plan, mapped to the Rights Radar check each belongs to (plan §7.3).
RIGHTS_KEYWORDS: dict[RightsCheckName, str] = {
    RightsCheckName.DEFAULT_BAIL: r"167\s?\(\s?2\s?\)|187\s?\(\s?3\s?\)|default\s+bail|statutory\s+bail|indefeasible\s+right|\b(?:60|90|sixty|ninety)\s+days\b",
    RightsCheckName.UNDERTRIAL_LIMIT: r"\b436[\s-]?A\b|(?:section|sec\.?|s\.)\s*479\b|\b479\s+(?:of\s+(?:the\s+)?)?(?:BNSS|B\.N\.S\.S)|(?:one[\s-]?half|one[\s-]?third|half)\s+of\s+(?:the\s+)?(?:maximum\s+)?(?:period|sentence|punishment)",
}
LABEL_SET = [c.value for c in RIGHTS_KEYWORDS]
_COMPILED = {c: re.compile(p, re.IGNORECASE) for c, p in RIGHTS_KEYWORDS.items()}


def build_gold(parts_path: str, out_path: str) -> int:
    """Build G7 for every cleanly split test order.

    Args:
        parts_path: JSONL from `order_splitter.split_all`
        out_path: output JSONL (record format in `gold/common.py`)

    Returns:
        Number of orders labelled.
    """
    return run_gold("G7", parts_path, out_path, label_detail)


def label_order(parts: dict[OrderPart, str]) -> dict[str, Any]:
    """Label one order: the agreed labels only (`label_detail` without the per-labeler lists).

    Args:
        parts: the five order parts

    Returns:
        Gold record fields without `rule_labels` and `llm_labels`.
    """
    return agreed_view(label_detail(parts))


def label_detail(parts: dict[OrderPart, str]) -> dict[str, Any]:
    """Label one order for G7; keep only labels both labelers agree on.

    Labels are Rights Radar check names (`default_bail`, `undertrial_limit`) whose keywords the court's reasoning uses.

    Args:
        parts: the five order parts

    Returns:
        Gold record fields, plus `custody_days_stated` when the reasoning states a custody duration.
    """
    reasoning = parts.get(OrderPart.REASONING, "")
    rule = [c.value for c in RIGHTS_KEYWORDS if _COMPILED[c].search(reasoning)]
    record = combine(rule, active_labeler(), reasoning, LABEL_SET)
    record["custody_days_stated"] = custody_days(reasoning) if rule else None
    return record
