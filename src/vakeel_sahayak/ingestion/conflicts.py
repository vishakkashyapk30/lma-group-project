"""Conflict handling between documents (plan §4.3 step 5)."""

from __future__ import annotations

from vakeel_sahayak.schemas.store_rows import TimelineEvent


def detect_conflicts(timeline: list[TimelineEvent]) -> list[tuple[str, list[str]]]:
    """Find fields where documents disagree (e.g. arrest date); keep both values and pass to Peshkar as AMBIGUOUS.

    Args:
        timeline: see behaviour

    Returns:
        (field, event ids) pairs.
    """
    raise NotImplementedError
