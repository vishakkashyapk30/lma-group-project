"""Run-time use of evidence contracts: slot needs, allowed stores, applicability (plan §6.1)."""

from __future__ import annotations

from vakeel_sahayak.contracts.models import EvidenceContract
from vakeel_sahayak.schemas.enums import StoreName
from vakeel_sahayak.schemas.retrieval_plan import SlotResult


def unfilled_slots(contract: EvidenceContract, filled: list[SlotResult]) -> list[str]:
    """Slots still needing evidence.

    Args:
        contract: see behaviour
        filled: see behaviour

    Returns:
        Slot names.
    """
    raise NotImplementedError


def allowed_stores(contract: EvidenceContract, slot: str) -> list[StoreName]:
    """Stores the slot may use.

    Args:
        contract: see behaviour
        slot: see behaviour

    Returns:
        Stores.
    """
    raise NotImplementedError
