"""Evaluation labeler Llama-3.1-8B (4-bit). Never used by the system; non-Qwen so gold is not Qwen output (plan §12, §15.1)."""

from __future__ import annotations


class EvalLabeler:
    """Llama-3.1-8B labeler for G1, G3-G7 and citation treatments."""

    def label(self, text: str, label_set: list[str]) -> list[str]:
        """Label text against a closed label set; agreed-labels-only logic lives in pipelines/gold.

        Args:
            text: see behaviour
            label_set: see behaviour

        Returns:
            Labels.
        """
        raise NotImplementedError
