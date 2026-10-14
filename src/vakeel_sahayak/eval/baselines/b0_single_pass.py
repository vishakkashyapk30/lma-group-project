"""Baseline B0. Single pass: raw facts and checklist to brief in one call. No retrieval, no agents. (plan §15.3)"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.schemas.bail_brief import BailBrief


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Produce a brief for one T1 case under B0.

    Args:
        case: see behaviour
        ctx: see behaviour

    Returns:
        BailBrief.
    """
    raise NotImplementedError
