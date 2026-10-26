"""Metrics: Recall@10 of court-cited precedents (G2), slot-fill rate, share of reasoning authorities, CHANGED used without qualification, overruled cited (plan §15.8)."""

from __future__ import annotations

from vakeel_sahayak.schemas.retrieval_plan import EvidencePack


def _doc_id(item: str) -> str:
    """The document id of a retrieved item ('DOC-A#14' -> 'DOC-A')."""
    return item.split("#", 1)[0]


def recall_at_k(retrieved: list[str], gold: list[str], k: int = 10) -> float:
    """Document-level recall@k.

    Args:
        retrieved: see behaviour
        gold: see behaviour
        k: see behaviour

    Returns:
        Recall (gold documents found in the top k, counted once each, over all gold documents).
    """
    gold_set = set(gold)
    if not gold_set:
        return 1.0
    found = {_doc_id(item) for item in retrieved[:k]}
    return len(gold_set & found) / len(gold_set)


def slot_fill_rate(packs: list[EvidencePack]) -> float:
    """Share of slots FILLED across every evidence pack.

    Args:
        packs: the evidence packs Sutradhar produced

    Returns:
        Filled slots / total slots (0.0 when there are no slots).
    """
    from vakeel_sahayak.schemas.enums import SlotStatus

    slots = [slot for pack in packs for slot in pack.slots]
    if not slots:
        return 0.0
    return sum(1 for s in slots if s.status == SlotStatus.FILLED) / len(slots)
