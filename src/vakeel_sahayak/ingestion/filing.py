"""Filing rules: what goes where in the case shelf (plan §4.4)."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import InfoKind, StoreName

FILING_RULES: dict[str, str] = {
    "document_text": "case.docs",
    "dated_event": "case.timeline",
    "party": "case.facts",
    "section": "case.facts",
    "earlier_outcome": "case.timeline+case.facts",
    "custody_health_personal": "case.facts",
    "unreadable_or_missing": "open_questions",
}


def target_stores(info_kind: InfoKind) -> list[StoreName]:
    """Which case-shelf store(s) an item belongs in.

    Args:
        info_kind: see behaviour

    Returns:
        Stores.
    """
    raise NotImplementedError
