"""Metrics: map_section accuracy on IPC2BNS-Verify (1,140 queries); T6 tool-call accuracy; recovery from injected tool errors (plan §15.8)."""

from __future__ import annotations

from typing import Any


def map_section_accuracy(predictions: list[str], gold: list[str]) -> float:
    """Accuracy.

    Args:
        predictions: see behaviour
        gold: see behaviour

    Returns:
        Exact-match accuracy (after trimming whitespace).
    """
    if not gold:
        return 1.0
    hits = sum(1 for p, g in zip(predictions, gold, strict=False) if p.strip() == g.strip())
    return hits / len(gold)


def tool_call_accuracy(calls: list[dict[str, Any]], gold: list[dict[str, Any]]) -> dict[str, float]:
    """Tool-name accuracy and argument validity over paired (call, gold) tool calls (T6, plan §15.8).

    Args:
        calls: the calls the agent made, each `{'name', 'args'}`
        gold: the gold calls, each `{'name', 'args'}`

    Returns:
        `{'name_accuracy': ..., 'args_valid': ...}`.
    """
    if not gold:
        return {"name_accuracy": 1.0, "args_valid": 1.0}
    name_hits = 0
    arg_hits = 0
    for call, want in zip(calls, gold, strict=False):
        if call.get("name") == want.get("name"):
            name_hits += 1
            if call.get("args") == want.get("args"):
                arg_hits += 1
    return {"name_accuracy": name_hits / len(gold), "args_valid": arg_hits / len(gold)}
