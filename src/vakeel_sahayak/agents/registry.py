"""Agent registry (plan §3.2)."""

from __future__ import annotations

from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.schemas.enums import AgentName

AGENT_CLASSES: dict[str, str] = {
    "MUNSHI": "vakeel_sahayak.agents.munshi.agent.MunshiAgent",
    "PESHKAR": "vakeel_sahayak.agents.peshkar.agent.PeshkarAgent",
    "SUTRADHAR": "vakeel_sahayak.agents.sutradhar.agent.SutradharAgent",
    "VAKEEL": "vakeel_sahayak.agents.vakeel.agent.VakeelAgent",
    "ABHIYOJAK": "vakeel_sahayak.agents.abhiyojak.agent.AbhiyojakAgent",
    "PAIROKAR": "vakeel_sahayak.agents.pairokar.agent.PairokarAgent",
}


def get_agent_class(name: AgentName) -> type[BaseAgent]:
    """Resolve an agent class by name.

    Args:
        name: see behaviour

    Returns:
        Agent class.
    """
    raise NotImplementedError
