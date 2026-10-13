"""Gold label G6: Conditions imposed (about 10 types: passport, travel, reporting, personal bond, no contact with witnesses, ...) (plan §15.1). From: operative order of grants. Method: Regexes and Llama; agreed only."""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.pipelines.gold.common import active_labeler, agreed_view, combine, run_gold
from vakeel_sahayak.pipelines.order_splitter import infer_outcome
from vakeel_sahayak.schemas.enums import OrderPart

CONDITION_RULES: dict[str, str] = {
    "personal_bond": r"personal\s+bond|bail\s+bond|furnish(?:ing)?\s+(?:a\s+)?(?:bond|personal)",
    "surety": r"\bsureties\b|\bsurety\b|with\s+(?:one|two|2|1)\s+(?:local\s+)?sureties?",
    "passport": r"passport",
    "travel_restriction": r"(?:not\s+(?:to\s+)?leave|shall\s+not\s+leave|leave\s+the\s+(?:country|city|state|jurisdiction))|without\s+(?:prior\s+)?(?:permission|leave)\s+of\s+(?:the\s+)?court|not\s+to\s+travel",
    "reporting": r"report(?:ing)?\s+(?:to|before|at)\s+(?:the\s+)?(?:police|station|investigating|IO|SHO)|mark\s+(?:his\s+|her\s+)?(?:presence|attendance)|appear\s+before\s+(?:the\s+)?(?:investigating|IO|SHO|police)\s+(?:officer\s+)?(?:every|once|on\s+(?:every|each))",
    "cooperate_investigation": r"co[\s-]?operate\s+(?:with\s+)?(?:the\s+)?(?:investigation|investigating|police|IO)|join\s+(?:the\s+)?investigation|available\s+for\s+(?:interrogation|investigation)",
    "appear_in_court": r"(?:appear|attend)\s+(?:before\s+(?:the\s+)?(?:trial\s+)?court\s+)?(?:on\s+)?(?:all\s+|every\s+|each\s+)?(?:the\s+)?(?:dates?|hearings?)|attend\s+the\s+trial|regularly\s+attend",
    "no_contact_witnesses": r"(?:not|shall\s+not|no)\s+(?:to\s+)?(?:contact|influence|threaten|intimidate|approach|pressuri[sz]e)[^.]{0,60}(?:witness|complainant|victim|informant)|no\s+contact\s+with",
    "no_tamper_evidence": r"(?:not|shall\s+not)\s+(?:to\s+)?tamper|tamper(?:ing)?\s+with\s+(?:the\s+)?evidence",
    "no_further_offence": r"(?:not|shall\s+not)\s+(?:to\s+)?(?:commit|indulge\s+in|involve\s+(?:himself|herself)\s+in)\s+(?:any\s+)?(?:similar\s+|other\s+|further\s+)?(?:offence|crime|criminal\s+activit)",
}
CONDITION_TYPES = tuple(CONDITION_RULES)
_COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in CONDITION_RULES.items()}


def build_gold(parts_path: str, out_path: str) -> int:
    """Build G6 for every cleanly split test order.

    Args:
        parts_path: JSONL from `order_splitter.split_all`
        out_path: output JSONL (record format in `gold/common.py`)

    Returns:
        Number of orders labelled.
    """
    return run_gold("G6", parts_path, out_path, label_detail)


def label_order(parts: dict[OrderPart, str]) -> dict[str, Any]:
    """Label one order: the agreed labels only (`label_detail` without the per-labeler lists).

    Args:
        parts: the five order parts

    Returns:
        Gold record fields without `rule_labels` and `llm_labels`.
    """
    return agreed_view(label_detail(parts))


def label_detail(parts: dict[OrderPart, str]) -> dict[str, Any]:
    """Label one order for G6; keep only labels both labelers agree on.

    Only grants carry conditions: an order whose operative part is not a grant gets no labels and `applicable` False.

    Args:
        parts: the five order parts

    Returns:
        Gold record fields: condition types (see `CONDITION_TYPES`) found in the operative order of a grant.
    """
    operative = parts.get(OrderPart.OPERATIVE, "")
    outcome = infer_outcome(operative)
    if outcome != "granted":
        return {**combine([], None, operative, list(CONDITION_TYPES)), "status": "not_applicable", "applicable": False, "outcome": outcome}
    rule = [k for k in CONDITION_TYPES if _COMPILED[k].search(operative)]
    return {**combine(rule, active_labeler(), operative, list(CONDITION_TYPES)), "applicable": True, "outcome": outcome}
