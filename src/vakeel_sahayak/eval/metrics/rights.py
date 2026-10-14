"""Metrics: Rights Radar accuracy per rule, false-ELIGIBLE rate, CHECK rate, agreement with G7 (plan §15.8)."""

from __future__ import annotations

from vakeel_sahayak.schemas.rights_report import RightsReport


def rights_accuracy(report: RightsReport, designed: dict[str, str]) -> dict[str, float]:
    """Per-rule accuracy and false-ELIGIBLE rate.

    Args:
        report: see behaviour
        designed: see behaviour

    Returns:
        Metrics.
    """
    raise NotImplementedError
