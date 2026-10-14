"""Baseline B3. Naive chunking: B1 with fixed 512, 512 with 20% overlap, recursive splitter, semantic chunking or page chunks; best on dev goes into generation. (plan §15.3)"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.schemas.bail_brief import BailBrief


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Produce a brief for one T1 case under B3.

    Args:
        case: see behaviour
        ctx: see behaviour

    Returns:
        BailBrief.
    """
    raise NotImplementedError
