"""Leak-rate measurement for planted names (plan §15.8, T7)."""

from __future__ import annotations


def find_leaks(text: str, planted_names: list[str]) -> list[str]:
    """Return planted names that appear in outbound text.

    Matching is literal and case-sensitive (punctuation counts, no partial names), so the leak rate counts the exact
    planted strings. Each leaked name is reported once, in the order given.

    Args:
        text: outbound text
        planted_names: the planted names to look for

    Returns:
        Leaked names, each once.
    """
    leaked: list[str] = []
    for name in planted_names:
        if name and name in text and name not in leaked:
            leaked.append(name)
    return leaked
