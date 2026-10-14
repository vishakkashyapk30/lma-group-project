"""Metrics: Unapproved-export attempts, injection success rate, refusal rate, planted-name leak rate (plan §15.8)."""

from __future__ import annotations

from vakeel_sahayak.schemas.events import Event


def export_violations(events: list[Event]) -> int:
    """Exports without Gate 2 approval.

    Args:
        events: see behaviour

    Returns:
        Count.
    """
    raise NotImplementedError


def injection_success_rate(outcomes: list[bool]) -> float:
    """Share of planted instructions followed.

    Args:
        outcomes: see behaviour

    Returns:
        Rate.
    """
    raise NotImplementedError


def refusal_rate(outcomes: list[bool]) -> float:
    """Share of prediction and lay-advice requests that were refused (plan §15.8 Safety).

    Args:
        outcomes: one bool per request, True if the system refused

    Returns:
        Rate in [0, 1].
    """
    raise NotImplementedError


def leak_rate(outbound_texts: list[str], planted_names: list[str]) -> float:
    """Share of planted names that appear in any outbound text (Ada-bound payloads, logs) (plan §15.8 Safety, T7).

    Args:
        outbound_texts: everything that left the laptop or was logged
        planted_names: the Faker names planted in the scenario

    Returns:
        Rate in [0, 1]; 0.0 means no leak.
    """
    raise NotImplementedError
