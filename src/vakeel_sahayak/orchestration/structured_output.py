"""Schema-constrained decoding helper for plans and tool calls (plan §3.3)."""

from __future__ import annotations

from pydantic import BaseModel

from vakeel_sahayak.models.base import LLMClient


def constrained_generate(client: LLMClient, prompt: str, schema: type[BaseModel], max_tokens: int = 2048) -> BaseModel:
    """Generate a plan or tool call with JSON-schema-constrained decoding (vLLM structured outputs) so every call parses; tools still validate argument values (plan §3.3).

    Args:
        client: see behaviour
        prompt: see behaviour
        schema: JSON schema to enforce
        max_tokens: see behaviour

    Returns:
        A validated model instance.
    """
    raise NotImplementedError
