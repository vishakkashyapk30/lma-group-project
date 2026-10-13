"""Tools in interaction (plan §4.3). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolSpec


def ask_user(questions: list[str], case_id: str) -> list[str]:
    """Ask counsel. Munshi and Peshkar share a limit of 3 questions per round; unreadable pages are grouped into one question. (plan §4.3)

    Args:
        questions: see behaviour
        case_id: see behaviour

    Returns:
        Counsel's answers (blocks via interrupt).
    """
    raise NotImplementedError


ASK_USER_SPEC = ToolSpec(
    name="ask_user",
    description="Ask counsel. Munshi and Peshkar share a limit of 3 questions per round; unreadable pages are grouped into one question.",
    agents=[AgentName.MUNSHI, AgentName.PESHKAR],
    stores=[],
    plan_ref="§4.3",
)
