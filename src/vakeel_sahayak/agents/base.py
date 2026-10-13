"""Base agent and context (plan §3.2, §3.3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.models.base import LLMClient
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import AgentName, EventKind
from vakeel_sahayak.schemas.events import Event


@dataclass
class AgentContext:
    """Everything an agent needs, injected (plan §3.3)."""

    case_id: str
    config: AppConfig
    log: EventLog
    budgets: BudgetTracker
    llm: LLMClient  # from models.factory.get_llm(role)
    switches: Switches
    tools: dict[str, Callable[..., Any]]  # filtered by configs/tools.yaml


class BaseAgent(ABC):
    """Abstract agent. Subclasses declare NAME and ROLE_MODEL, never import model libraries directly, and emit an Event for every tool call (plan §3.3)."""

    NAME: AgentName
    ROLE_MODEL: str  # key in configs/models.yaml; allowed tools come from configs/tools.yaml

    def __init__(self, ctx: AgentContext) -> None:
        """Bind the agent to its context.

        Args:
            ctx: see behaviour
        """
        raise NotImplementedError

    @abstractmethod
    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run the agent's job for the current graph state.

        Args:
            state: see behaviour

        Returns:
            Updated state.
        """
        raise NotImplementedError

    def call_tool(self, name: str, **kwargs: Any) -> Any:
        """Call a registered tool: check it is allowed, charge the budget, append TOOL_CALL and TOOL_RESULT events.

        Args:
            name: see behaviour
            kwargs: see behaviour

        Returns:
            The tool result.
        """
        raise NotImplementedError

    def emit(self, kind: EventKind, payload: dict[str, Any]) -> Event:
        """Append an event to the log.

        Args:
            kind: see behaviour
            payload: see behaviour

        Returns:
            The event.
        """
        raise NotImplementedError
