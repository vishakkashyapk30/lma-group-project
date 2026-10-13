"""Vakeel agent (plan §3.2). Drafting, checking and repair, the application, the hearing card (plan §8). Qwen3-14B on Ada."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.bail_brief import BailBrief, Ground
from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack
from vakeel_sahayak.schemas.sparring import Objection, Reply


class VakeelAgent(BaseAgent):
    """Drafting, checking and repair, the application, the hearing card (plan §8). Qwen3-14B on Ada."""

    NAME = AgentName.VAKEEL
    ROLE_MODEL = "agents_14b"

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Vakeel's full job for the current graph state.

        Args:
            state: see behaviour

        Returns:
            Updated state.
        """
        raise NotImplementedError

    def draft_grounds(self, state: CaseGraphState, packs: list[EvidencePack]) -> list[Ground]:
        """Draft one ground per chosen factor; each sentence cites [F:field] facts and [A:doc#para] authorities (plan §8.1 step 1).

        Args:
            state: see behaviour
            packs: see behaviour

        Returns:
            Grounds.
        """
        raise NotImplementedError

    def reply_to_objections(self, state: CaseGraphState, objections: list[Objection]) -> list[Reply]:
        """Answer Abhiyojak's objections under the same citation and checking rules (step 2).

        Args:
            state: see behaviour
            objections: see behaviour

        Returns:
            Replies.
        """
        raise NotImplementedError

    def check_claims(self, grounds: list[Ground]) -> list[Ground]:
        """NLI fact and authority support, transfer and good-law flags, no unretrieved citation (step 3).

        Args:
            grounds: see behaviour

        Returns:
            Grounds with check set.
        """
        raise NotImplementedError

    def repair_or_flag(self, grounds: list[Ground]) -> list[Ground]:
        """At most 2 rounds: re-retrieve via Sutradhar or reword; else NEEDS_REVIEW. Nothing is dropped silently (step 4).

        Args:
            grounds: see behaviour

        Returns:
            Grounds.
        """
        raise NotImplementedError

    def assemble_brief(self, state: CaseGraphState) -> BailBrief:
        """Assemble BailBrief including dependencies and open issues (plan §8.1).

        Args:
            state: see behaviour

        Returns:
            BailBrief.
        """
        raise NotImplementedError

    def build_hearing_card(self, state: CaseGraphState) -> dict[str, Any]:
        """Hearing-prep card (plan §8.3).

        Args:
            state: see behaviour

        Returns:
            Card.
        """
        raise NotImplementedError
