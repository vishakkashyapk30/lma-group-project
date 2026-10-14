"""The Full system through the batch desk (plan §11 'Reuse', §15.3)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.schemas.bail_brief import BailBrief


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Munshi, Peshkar, Sutradhar, Vakeel, Abhiyojak and all checks.

    Args:
        case: see behaviour
        ctx: see behaviour

    Returns:
        BailBrief.
    """
    raise NotImplementedError
