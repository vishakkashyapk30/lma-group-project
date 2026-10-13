"""Pairokar agent (plan §3.2). Batch triage desk (plan §11). Rules + Qwen3-14B; laptop and Ada."""

from __future__ import annotations

from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.schemas.triage import TriageCard


class PairokarAgent(BaseAgent):
    """Batch triage desk (plan §11). Rules + Qwen3-14B; laptop and Ada."""

    NAME = AgentName.PAIROKAR
    ROLE_MODEL = "agents_14b"

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Pairokar's full job for the current graph state.

        Args:
            state: see behaviour

        Returns:
            Updated state.
        """
        raise NotImplementedError

    def stage1(self, files: list[str]) -> list[TriageCard]:
        """Run Munshi, Peshkar and Rights Radar on every file; one TriageCard each.

        Args:
            files: see behaviour

        Returns:
            Cards.
        """
        raise NotImplementedError

    def decide_next_steps(self, cards: list[TriageCard]) -> list[TriageCard]:
        """Per case: queue a full brief, flag for counsel, or ask for documents first.

        Args:
            cards: see behaviour

        Returns:
            Cards with next_step.
        """
        raise NotImplementedError

    def stage2(self, cards: list[TriageCard], gpu_budget_hours: float) -> list[str]:
        """Full runs in urgency order within the session budget; save each output as it finishes; no bulk export.

        Args:
            cards: see behaviour
            gpu_budget_hours: see behaviour

        Returns:
            Case ids completed.
        """
        raise NotImplementedError
