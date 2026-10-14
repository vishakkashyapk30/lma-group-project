"""Baseline B2. Whole-document embeddings: each order one BGE-M3 vector truncated at 8K tokens; top-3 orders in full. (plan §15.3)"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.schemas.bail_brief import BailBrief


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Produce a brief for one T1 case under B2.

    Args:
        case: see behaviour
        ctx: see behaviour

    Returns:
        BailBrief.
    """
    raise NotImplementedError
