"""Metrics: Recall@10, MRR and nDCG@10 of court-cited precedents (G2), slot-fill rate, share of reasoning authorities, CHANGED used without qualification, overruled cited (plan §15.8)."""

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


def _doc_ranking(retrieved: list[str]) -> list[str]:
    """Document ids in first-seen order (several paragraphs of one document are one entry, at its best rank)."""
    return list(dict.fromkeys(_doc_id(item) for item in retrieved))


def mean_reciprocal_rank(retrieved: list[str], gold: list[str]) -> float:
    """Reciprocal rank of the first gold document (average it over queries for MRR).

    Args:
        retrieved: ranked items ('doc_id' or 'doc_id#para')
        gold: gold document ids

    Returns:
        1 / rank of the first gold document in the document ranking, 0.0 when none is found (1.0 when there is no gold,
        as in `recall_at_k`).
    """
    gold_set = set(gold)
    if not gold_set:
        return 1.0
    for rank, doc in enumerate(_doc_ranking(retrieved), start=1):
        if doc in gold_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], gold: list[str], k: int = 10) -> float:
    """Document-level nDCG@k with binary relevance.

    Args:
        retrieved: ranked items ('doc_id' or 'doc_id#para'); the first k items count, as in `recall_at_k`
        gold: gold document ids

    Returns:
        DCG / ideal DCG, in [0, 1] (1.0 when there is no gold, as in `recall_at_k`).
    """
    import math

    gold_set = set(gold)
    if not gold_set:
        return 1.0
    dcg = sum(1.0 / math.log2(rank + 1) for rank, doc in enumerate(_doc_ranking(retrieved[:k]), start=1) if doc in gold_set)
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(gold_set), k) + 1))
    return dcg / ideal


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


def auroc(scores: list[float], labels: list[bool]) -> float | None:
    """Area under the ROC curve of `scores` for the binary `labels` (M19: AUROC of the score-skew signal for "the top-10 contains a G2 paragraph").

    The Mann-Whitney form: the probability that a random positive scores above a random negative, ties counting one half. Higher scores are predicted positive.

    Returns:
        The AUROC, or None when there is no positive or no negative (it is undefined, not 0.5).

    Raises:
        ValueError: `scores` and `labels` differ in length.
    """
    if len(scores) != len(labels):
        raise ValueError(f"scores and labels differ in length: {len(scores)} != {len(labels)}")
    pos = [s for s, y in zip(scores, labels, strict=True) if y]
    neg = [s for s, y in zip(scores, labels, strict=True) if not y]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))
