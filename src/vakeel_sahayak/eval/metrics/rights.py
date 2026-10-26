"""Metrics: Rights Radar accuracy per rule, false-ELIGIBLE rate, CHECK rate, agreement with G7 (plan §15.8)."""

from __future__ import annotations

from vakeel_sahayak.schemas.rights_report import RightsReport


def rights_accuracy(report: RightsReport, designed: dict[str, str]) -> dict[str, float]:
    """Per-rule accuracy and false-ELIGIBLE rate.

    Args:
        report: see behaviour
        designed: see behaviour

    Returns:
        Each check name -> 1.0 if its status matches the designed answer else 0.0, plus `false_eligible_rate`: the share
        of checks the report calls ELIGIBLE where the designed answer is not ELIGIBLE (plan §15.8).
    """
    result: dict[str, float] = {}
    false_eligible = 0
    for check in report.checks:
        name = check.check.value
        status = check.status.value
        result[name] = 1.0 if status == designed.get(name) else 0.0
        if status == "ELIGIBLE" and designed.get(name) != "ELIGIBLE":
            false_eligible += 1
    result["false_eligible_rate"] = false_eligible / len(report.checks) if report.checks else 0.0
    return result
