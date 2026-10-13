"""Sutradhar agent (plan §3.2). Orchestrator: evidence contracts, retrieval plans, sufficiency checks, budget, delegation, chat routing (plan §6). Qwen3-14B on Ada."""

from __future__ import annotations

from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.chat import ChatMessage
from vakeel_sahayak.schemas.enums import AgentName, Factor
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack, RetrievalPlan, SlotResult


class SutradharAgent(BaseAgent):
    """Orchestrator: evidence contracts, retrieval plans, sufficiency checks, budget, delegation, chat routing (plan §6). Qwen3-14B on Ada."""

    NAME = AgentName.SUTRADHAR
    ROLE_MODEL = "agents_14b"

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Sutradhar's full job for the current graph state.

        Args:
            state: see behaviour

        Returns:
            Updated state.
        """
        raise NotImplementedError

    def pick_factors(self, state: CaseGraphState) -> list[EvidencePack]:
        """Mark each of the 12 factors favourable, adverse or not applicable with a reason (plan §6.2 step 1).

        Args:
            state: see behaviour

        Returns:
            One pack shell per factor.
        """
        raise NotImplementedError

    def plan_factor(self, factor: Factor, state: CaseGraphState) -> RetrievalPlan:
        """Write a RetrievalPlan for unfilled slots (step 2.1).

        Args:
            factor: see behaviour
            state: see behaviour

        Returns:
            RetrievalPlan.
        """
        raise NotImplementedError

    def run_plan(self, plan: RetrievalPlan) -> list[SlotResult]:
        """Execute calls; independent calls run concurrently (step 2.2).

        Args:
            plan: see behaviour

        Returns:
            Slot results.
        """
        raise NotImplementedError

    def assess(self, factor: Factor, results: list[SlotResult]) -> list[SlotResult]:
        """Mark each slot FILLED/WEAK/MISSING using rule checks (step 2.3).

        Args:
            factor: see behaviour
            results: see behaviour

        Returns:
            Assessed slots.
        """
        raise NotImplementedError

    def replan(self, plan: RetrievalPlan, results: list[SlotResult]) -> RetrievalPlan | None:
        """Reword, relax filters in order (factor, section family, court), follow citations to SC, try another allowed store; None when stopped (step 2.4-2.5).

        Args:
            plan: see behaviour
            results: see behaviour

        Returns:
            Next plan or None.
        """
        raise NotImplementedError

    def delegate(self, state: CaseGraphState, packs: list[EvidencePack]) -> CaseGraphState:
        """Hand packs to Vakeel; send draft to Abhiyojak; route objections back; decide re-retrieve vs reword on failed claims (step 3).

        Args:
            state: see behaviour
            packs: see behaviour

        Returns:
            Updated state.
        """
        raise NotImplementedError

    def answer_chat(self, state: CaseGraphState, question: str) -> ChatMessage:
        """Route a counsel question to the right store or tool and answer briefly with citations; refuse outcome predictions and lay advice (plan §6.4).

        Args:
            state: see behaviour
            question: see behaviour

        Returns:
            ChatMessage.
        """
        raise NotImplementedError

    def reopen_after_change(self, state: CaseGraphState, change_set: ChangeSet) -> list[Factor]:
        """Re-run only affected factors (step 4; plan §10).

        Args:
            state: see behaviour
            change_set: see behaviour

        Returns:
            Factors.
        """
        raise NotImplementedError
