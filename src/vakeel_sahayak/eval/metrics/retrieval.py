"""Metrics: Recall@10 of court-cited precedents (G2), slot-fill rate, share of reasoning authorities, CHANGED used without qualification, overruled cited (plan §15.8)."""

from __future__ import annotations

from vakeel_sahayak.schemas.retrieval_plan import EvidencePack


def recall_at_k(retrieved: list[str], gold: list[str], k: int = 10) -> float:
    """Document-level recall@k.

    Args:
        retrieved: see behaviour
        gold: see behaviour
        k: see behaviour

    Returns:
        Recall.
    """
    raise NotImplementedError


def slot_fill_rate(packs: list[EvidencePack]) -> float:
    """Share of required slots FILLED.

    Args:
        packs: see behaviour

    Returns:
        Rate.
    """
    raise NotImplementedError
