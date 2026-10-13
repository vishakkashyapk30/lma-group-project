"""Abhiyojak agent (plan §3.2). Prosecution sparring with its own prompt and context; sees only drafted grounds, dossier and its own stores (plan §9). Qwen3-14B on Ada."""

from __future__ import annotations

from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.schemas.sparring import Objection, SparringRecord


class AbhiyojakAgent(BaseAgent):
    """Prosecution sparring with its own prompt and context; sees only drafted grounds, dossier and its own stores (plan §9). Qwen3-14B on Ada."""

    NAME = AgentName.ABHIYOJAK
    ROLE_MODEL = "agents_14b"

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Abhiyojak's full job for the current graph state.

        Args:
            state: see behaviour

        Returns:
            Updated state.
        """
        raise NotImplementedError

    def raise_objections(self, state: CaseGraphState) -> list[Objection]:
        """Round 1: up to two objections per ground plus general ones (gravity, flight risk, witness tampering, antecedents, statutory bars); discard and log ungrounded ones.

        Args:
            state: see behaviour

        Returns:
            Objections.
        """
        raise NotImplementedError

    def judge_replies(self, state: CaseGraphState, objections: list[Objection]) -> list[Objection]:
        """Round 2: mark each reply ANSWERED, PARTLY or UNANSWERED with a reason; UNANSWERED goes to counsel as NEEDS_REVIEW.

        Args:
            state: see behaviour
            objections: see behaviour

        Returns:
            Objections with verdicts.
        """
        raise NotImplementedError

    def spar(self, state: CaseGraphState) -> SparringRecord:
        """Run two rounds within budget.

        Args:
            state: see behaviour

        Returns:
            SparringRecord.
        """
        raise NotImplementedError
