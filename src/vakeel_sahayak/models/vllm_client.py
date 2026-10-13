"""vLLM client for Qwen3-14B-AWQ / Qwen3-32B-AWQ on Ada, run inside the experiment script with no long-lived server (plan §12, §17); reached through an SSH tunnel in the demo (plan §13.1)."""

from __future__ import annotations

from vakeel_sahayak.models.base import LLMClient


class VllmClient(LLMClient):
    """vLLM client for Qwen3-14B-AWQ / Qwen3-32B-AWQ on Ada, run inside the experiment script with no long-lived server (plan §12, §17); reached through an SSH tunnel in the demo (plan §13.1)."""

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
