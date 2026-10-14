"""Metrics: map_section accuracy on IPC2BNS-Verify (1,140 queries); T6 tool-call accuracy; recovery from injected tool errors (plan §15.8)."""

from __future__ import annotations

from typing import Any


def map_section_accuracy(predictions: list[str], gold: list[str]) -> float:
    """Accuracy.

    Args:
        predictions: see behaviour
        gold: see behaviour

    Returns:
        Accuracy.
    """
    raise NotImplementedError


def tool_call_accuracy(calls: list[dict[str, Any]], gold: list[dict[str, Any]]) -> dict[str, float]:
    """Name and argument validity.

    Args:
        calls: see behaviour
        gold: see behaviour

    Returns:
        Metrics.
    """
    raise NotImplementedError
