"""Metrics: Unsupported-fact rate: share of factual sentences MiniCheck finds unsupported by the input; checker validation (plan §15.9) (plan §15.8)."""

from __future__ import annotations

from vakeel_sahayak.schemas.bail_brief import BailBrief


def unsupported_fact_rate(brief: BailBrief, input_text: str) -> float:
    """MiniCheck over factual sentences.

    Args:
        brief: see behaviour
        input_text: see behaviour

    Returns:
        Rate.
    """
    raise NotImplementedError


def validate_checker(sentences: list[str]) -> dict[str, float]:
    """In-domain check: input sentences supported; copies with a changed date, number or name unsupported.

    Args:
        sentences: see behaviour

    Returns:
        Accuracy stats.
    """
    raise NotImplementedError
