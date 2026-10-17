"""Run-time use of evidence contracts: slot needs, allowed stores, applicability (plan §6.1).

The contract fixes what evidence a ground needs and which stores may hold it; everything here only reads it. Whether a
factor applies to a case is decided in `factor_pick.py` from the dossier and the RightsReport.
"""

from __future__ import annotations

from functools import cache

from vakeel_sahayak.contracts.models import EvidenceContract
from vakeel_sahayak.schemas.enums import Factor, SlotStatus, StoreName
from vakeel_sahayak.schemas.retrieval_plan import SlotResult


@cache
def contract_for(factor: Factor) -> EvidenceContract:
    """The validated contract of a factor (loaded once)."""
    from vakeel_sahayak.contracts.loader import load_contract

    return load_contract(Factor(factor))


def unfilled_slots(contract: EvidenceContract, filled: list[SlotResult]) -> list[str]:
    """Slots still needing evidence: the contract's non-optional slots (in contract order) with no FILLED result yet.

    An optional slot (coverage and phrasing only) never blocks a factor, so it is not listed.

    Args:
        contract: the factor's evidence contract
        filled: slot results so far (only FILLED ones count; WEAK and MISSING slots stay unfilled)

    Returns:
        Slot names.
    """
    done = {r.slot for r in filled if r.status == SlotStatus.FILLED}
    return [name for name, slot in contract.slots.items() if not is_optional(slot.need) and name not in done]


def allowed_stores(contract: EvidenceContract, slot: str) -> list[StoreName]:
    """Stores the slot may use, in the contract's order (the order Sutradhar tries them).

    Args:
        contract: the factor's evidence contract
        slot: a slot name of the contract

    Returns:
        Stores (empty for a slot served by a tool alone, such as a Rights Radar entry).

    Raises:
        KeyError: the contract has no such slot.
    """
    return [StoreName(s) for s in contract.slots[slot].stores]


def slot_tools(contract: EvidenceContract, slot: str) -> list[str]:
    """Non-store tools a slot may use (`rights_check`, `date_calc`, `ask_user`)."""
    return list(contract.slots[slot].tools)


def is_optional(need: str | int) -> bool:
    """True for an 'optional' slot (coverage and phrasing; its absence is never an open issue)."""
    return need == "optional"


def required_count(need: str | int) -> int:
    """How many items a slot needs to be FILLED: the integer itself, 1 for 'required', 0 for 'optional'."""
    if isinstance(need, int) and not isinstance(need, bool):
        return max(0, need)
    if str(need).isdigit():
        return int(str(need))
    return 0 if is_optional(need) else 1


def required_slots(contract: EvidenceContract) -> list[str]:
    """Slots that must be FILLED before the factor stops: every slot that is not optional."""
    return [name for name, slot in contract.slots.items() if not is_optional(slot.need)]
