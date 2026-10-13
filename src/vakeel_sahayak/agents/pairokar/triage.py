"""Per-case triage card construction (plan §11)."""

from __future__ import annotations

from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.triage import TriageCard


def make_card(case_id: str, rights: RightsReport, dossier: CaseDossier, missing_docs: list[str]) -> TriageCard:
    """Build the card: urgency reasons, flags, missing documents.

    Args:
        case_id: see behaviour
        rights: see behaviour
        dossier: see behaviour
        missing_docs: see behaviour

    Returns:
        TriageCard.
    """
    raise NotImplementedError
