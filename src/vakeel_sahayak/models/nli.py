"""DeBERTa-v3 NLI used by span_check and check_claim; threshold tuned on dev (plan §12). MiniCheck is evaluation-only (eval/)."""

from __future__ import annotations

from vakeel_sahayak.models.base import NliClient


class DebertaNliClient(NliClient):
    """DeBERTa-v3 NLI used by span_check and check_claim; threshold tuned on dev (plan §12). MiniCheck is evaluation-only (eval/)."""

    def entails(self, premise: str, hypothesis: str) -> float:
        """Entailment score.

        Args:
            premise: see behaviour
            hypothesis: see behaviour

        Returns:
            Score.
        """
        raise NotImplementedError
