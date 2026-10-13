"""Tools in drafting.application (plan §8.2). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolSpec


def assemble_application(case_id: str) -> str:
    """Fill the python-docx template from the brief. (plan §8.2)

    Args:
        case_id: see behaviour

    Returns:
        Path of the DOCX.
    """
    raise NotImplementedError


ASSEMBLE_APPLICATION_SPEC = ToolSpec(
    name="assemble_application",
    description="Fill the python-docx template from the brief.",
    agents=[AgentName.VAKEEL],
    stores=[],
    plan_ref="§8.2",
)
