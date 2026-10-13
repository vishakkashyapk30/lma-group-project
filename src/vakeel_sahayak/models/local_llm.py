"""Qwen3-4B (base or +QLoRA adapter, int4) on the laptop for Munshi and Peshkar (plan §12)."""

from __future__ import annotations

from vakeel_sahayak.models.base import LLMClient


class LocalLLMClient(LLMClient):
    """Qwen3-4B (base or +QLoRA adapter, int4) on the laptop for Munshi and Peshkar (plan §12)."""

    def generate(
        self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None
    ) -> str:
        """Generate.

        Args:
            prompt: see behaviour
            max_tokens: see behaviour
            temperature: see behaviour
            json_schema: see behaviour

        Returns:
            Completion.
        """
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        """Count tokens.

        Args:
            text: see behaviour

        Returns:
            Count.
        """
        raise NotImplementedError
