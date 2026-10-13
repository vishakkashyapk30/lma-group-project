"""A6 variant and default fallback: contracts run in a fixed order with fixed queries, no planning or sufficiency check (plan §6.5, §15.4, §19)."""

from __future__ import annotations

from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack


def run_fixed_router(state: CaseGraphState) -> list[EvidencePack]:
    """Execute each applicable contract with templated queries.

    Args:
        state: see behaviour

    Returns:
        Evidence packs.
    """
    raise NotImplementedError
