"""Baseline B4. Every store, no orchestrator: each store queried with facts and factor names, fused with reciprocal-rank fusion; drafting, checks and sparring as in Full. (plan §15.3)"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.schemas.bail_brief import BailBrief


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Produce a brief for one T1 case under B4.

    Args:
        case: see behaviour
        ctx: see behaviour

    Returns:
        BailBrief.
    """
    raise NotImplementedError
