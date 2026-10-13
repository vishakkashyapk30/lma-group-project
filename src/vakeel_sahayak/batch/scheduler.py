"""Batch scheduler (plan §11)."""

from __future__ import annotations

from vakeel_sahayak.batch.queue import TriageQueue
from vakeel_sahayak.schemas.triage import TriageCard


class Scheduler:
    """Decides per case: queue a full brief, flag for counsel, or ask for documents first; re-prioritises as results arrive (plan §11)."""

    def triage_all(self, queue: TriageQueue) -> list[TriageCard]:
        """Stage 1: Munshi, Peshkar and Rights Radar on every file (cheap).

        Args:
            queue: see behaviour

        Returns:
            Cards.
        """
        raise NotImplementedError

    def decide(self, card: TriageCard) -> str:
        """full_brief | flag_counsel | request_documents.

        Args:
            card: see behaviour

        Returns:
            Decision.
        """
        raise NotImplementedError

    def reprioritise(self, cards: list[TriageCard]) -> list[TriageCard]:
        """e.g. a case found to face a statutory bar moves down.

        Args:
            cards: see behaviour

        Returns:
            Reordered cards.
        """
        raise NotImplementedError

    def run_stage2(self, queue: TriageQueue) -> None:
        """Run full runs in urgency order; vLLM prefix caching covers shared prompts.

        Args:
            queue: see behaviour
        """
        raise NotImplementedError
