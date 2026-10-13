"""Qwen3-VL transcription only, never summarise (step 4). Plan §4.2."""

from __future__ import annotations

from vakeel_sahayak.ingestion.ladder import RouteOutcome


def vision_route(file_path: str, page: int) -> RouteOutcome:
    """Qwen3-VL transcription only, never summarise (step 4).

    Args:
        file_path: see behaviour
        page: see behaviour

    Returns:
        RouteOutcome.
    """
    raise NotImplementedError
