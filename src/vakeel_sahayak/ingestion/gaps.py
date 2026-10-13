"""Gap handling: re-read, search remaining pages, or ask counsel (plan §4.3 step 4)."""

from __future__ import annotations

from vakeel_sahayak.schemas.ingestion_report import Gap


def resolve_gap(item: str, case_id: str) -> Gap:
    """Decide whether to re-read a likely page with a stronger route, search remaining pages, or ask counsel; return the action taken.

    Args:
        item: see behaviour
        case_id: see behaviour

    Returns:
        Gap record.
    """
    raise NotImplementedError
