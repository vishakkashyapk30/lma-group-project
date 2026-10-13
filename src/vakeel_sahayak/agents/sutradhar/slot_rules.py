"""Rule checks that assess a slot: court reasoning, factor tag, section-family overlap, date before the case (plan §6.2 step 2.3)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.enums import Factor
from vakeel_sahayak.schemas.retrieval_plan import SlotResult


def assess_slot(
    slot: str, items: list[dict[str, Any]], need: str | int, case_date: str, factor: Factor, section_family: list[str]
) -> SlotResult:
    """Return FILLED, WEAK or MISSING with a reason.

    Args:
        slot: see behaviour
        items: see behaviour
        need: see behaviour
        case_date: see behaviour
        factor: see behaviour
        section_family: see behaviour

    Returns:
        SlotResult.
    """
    raise NotImplementedError
