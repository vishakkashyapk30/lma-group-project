"""Tools in drafting.claims (plan §8.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolSpec
from vakeel_sahayak.tools.types import ClaimCheckResult


def check_claim(claim: str, refs: list[str] | None = None) -> ClaimCheckResult:
    """Fact support (NLI vs dossier quote), authority support (NLI vs cited paragraph), transfer flag, good-law flag, and no citation that was not retrieved. (plan §8.1)

    Args:
        claim: see behaviour
        refs: [F:field] and [A:doc#para] references

    Returns:
        ClaimCheckResult.
    """
    raise NotImplementedError


def render_citation(doc_id: str, para: int | None = None) -> str:
    """Render citation text from corpus metadata; the model writes only IDs. (plan §8.1)

    Args:
        doc_id: see behaviour
        para: see behaviour

    Returns:
        Citation string.
    """
    raise NotImplementedError


CHECK_CLAIM_SPEC = ToolSpec(
    name="check_claim",
    description="Fact support (NLI vs dossier quote), authority support (NLI vs cited paragraph), transfer flag, good-law flag, and no citation that was not retrieved.",
    agents=[AgentName.VAKEEL],
    stores=[],
    plan_ref="§8.1",
)

RENDER_CITATION_SPEC = ToolSpec(
    name="render_citation",
    description="Render citation text from corpus metadata; the model writes only IDs.",
    agents=[AgentName.VAKEEL],
    stores=[],
    plan_ref="§8.1",
)
