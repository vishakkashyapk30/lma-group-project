"""List of Dates and Events built from case.timeline (plan §7.2)."""

from __future__ import annotations

from vakeel_sahayak.schemas.store_rows import TimelineEvent


def build_list_of_dates(timeline: list[TimelineEvent]) -> list[dict[str, str]]:
    """One row per dated event, sorted, with source (document, page); conflicting dates side by side.

    Args:
        timeline: see behaviour

    Returns:
        Rows.
    """
    raise NotImplementedError
