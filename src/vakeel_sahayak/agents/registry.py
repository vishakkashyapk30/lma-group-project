"""Agent registry (plan §3.2)."""

from __future__ import annotations

import importlib
from typing import Any

from vakeel_sahayak.agents.base import AgentContext, BaseAgent
from vakeel_sahayak.schemas.enums import AgentName

AGENT_CLASSES: dict[str, str] = {
    "MUNSHI": "vakeel_sahayak.agents.munshi.agent.MunshiAgent",
    "PESHKAR": "vakeel_sahayak.agents.peshkar.agent.PeshkarAgent",
    "SUTRADHAR": "vakeel_sahayak.agents.sutradhar.agent.SutradharAgent",
    "VAKEEL": "vakeel_sahayak.agents.vakeel.agent.VakeelAgent",
    "ABHIYOJAK": "vakeel_sahayak.agents.abhiyojak.agent.AbhiyojakAgent",
    "PAIROKAR": "vakeel_sahayak.agents.pairokar.agent.PairokarAgent",
}
# The model role of each agent (configs/models.yaml); Peshkar's follows A5's `extractor` switch at run time.
AGENT_ROLES: dict[AgentName, str] = {
    AgentName.MUNSHI: "munshi_4b",
    AgentName.PESHKAR: "extractor_4b",
    AgentName.SUTRADHAR: "agents_14b",
    AgentName.VAKEEL: "agents_14b",
    AgentName.ABHIYOJAK: "agents_14b",
    AgentName.PAIROKAR: "agents_14b",
}


def get_agent_class(name: AgentName) -> type[BaseAgent]:
    """Resolve an agent class by name.

    Args:
        name: an AgentName or its value ('VAKEEL'); case-insensitive

    Returns:
        Agent class.

    Raises:
        ValueError: for an unknown agent.
    """
    key = str(getattr(name, "value", name)).upper()
    if key not in AGENT_CLASSES:
        raise ValueError(f"unknown agent {name!r}: use one of {sorted(AGENT_CLASSES)}")
    module, _, cls_name = AGENT_CLASSES[key].rpartition(".")
    cls = getattr(importlib.import_module(module), cls_name)
    if not (isinstance(cls, type) and issubclass(cls, BaseAgent)):
        raise TypeError(f"{AGENT_CLASSES[key]} is not a BaseAgent subclass")
    return cls


def create_agent(name: AgentName, ctx: AgentContext, **kwargs: Any) -> BaseAgent:
    """Instantiate an agent for a context (extra keyword arguments go to the agent's constructor)."""
    return get_agent_class(name)(ctx, **kwargs)
