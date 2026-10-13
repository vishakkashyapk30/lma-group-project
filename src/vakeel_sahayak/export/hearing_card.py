"""One-page hearing-prep card (plan §8.3). No outcome prediction, no grant rates."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.sparring import SparringRecord


def build_hearing_card(brief: BailBrief, sparring: SparringRecord, case_id: str) -> dict[str, Any]:
    """Likely bench concerns (caselaw.similar and same-section-family reasoning), three points to lead with, conditions courts impose in similar grants, open issues.

    Args:
        brief: see behaviour
        sparring: see behaviour
        case_id: see behaviour

    Returns:
        Card content.
    """
    raise NotImplementedError
