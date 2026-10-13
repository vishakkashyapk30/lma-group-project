"""Gold label G3: Dossier fields and dated events (plan §15.1). From: whole order. Method: Regex rules and Llama agree."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.pipelines.gold.common import active_labeler, agreed_view, combine, part_text, run_gold
from vakeel_sahayak.pipelines.order_facts import dossier_fields, extract_dates
from vakeel_sahayak.pipelines.order_splitter import PART_ORDER
from vakeel_sahayak.schemas.enums import OrderPart


def build_gold(parts_path: str, out_path: str) -> int:
    """Build G3 for every cleanly split test order.

    Args:
        parts_path: JSONL from `order_splitter.split_all`
        out_path: output JSONL (record format in `gold/common.py`)

    Returns:
        Number of orders labelled.
    """
    return run_gold("G3", parts_path, out_path, label_detail)


def flatten(fields: dict[str, Any], events: list[str]) -> list[str]:
    """Candidate labels as strings: 'sections=IPC 420', 'arrest_date=2023-03-12', 'event=2023-03-12'."""
    labels: list[str] = []
    for key, value in fields.items():
        labels.extend(f"{key}={v}" for v in (value if isinstance(value, list) else [value]))
    return labels + [f"event={iso}" for iso in events]


def label_order(parts: dict[OrderPart, str]) -> dict[str, Any]:
    """Label one order: the agreed labels only (`label_detail` without the per-labeler lists).

    Args:
        parts: the five order parts

    Returns:
        Gold record fields without `rule_labels` and `llm_labels`.
    """
    return agreed_view(label_detail(parts))


def label_detail(parts: dict[OrderPart, str]) -> dict[str, Any]:
    """Label one order for G3; keep only labels both labelers agree on.

    The rules propose candidate labels (dossier fields and dates). The LLM labeler, when given, is offered exactly those
    candidates and confirms the ones it finds in the order; the agreed ones are gold.

    Args:
        parts: the five order parts (joined to the whole order)

    Returns:
        Gold record fields plus `fields` (dossier-style values) and `events` (date, sentence).
    """
    text = part_text(parts, *PART_ORDER)
    fields = dossier_fields(text)
    mentions = extract_dates(text)
    events = sorted({m.iso for m in mentions})
    rule = flatten(fields, events)
    return {
        **combine(rule, active_labeler(), text, rule),
        "fields": fields,
        "events": [{"date": m.iso, "sentence": m.sentence} for m in mentions],
    }
