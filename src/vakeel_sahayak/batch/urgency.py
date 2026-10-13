"""The fixed urgency rule (plan §11)."""

from __future__ import annotations

from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.triage import TriageCard


def urgency_key(rights: RightsReport, custody_days: int | None, missing_docs: list[str]) -> tuple:
    """Fixed, explainable urgency order: (1) legal deadlines, (2) days past a threshold, (3) custody length; ties to cases with no missing documents (plan §11).

    Args:
        rights: see behaviour
        custody_days: see behaviour
        missing_docs: see behaviour

    Returns:
        A sortable key.
    """
    raise NotImplementedError


def rank(cards: list[TriageCard]) -> list[TriageCard]:
    """Assign urgency_rank to cards.

    Args:
        cards: see behaviour

    Returns:
        Ranked cards.
    """
    raise NotImplementedError
