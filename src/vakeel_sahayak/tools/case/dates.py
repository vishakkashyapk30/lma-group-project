"""Tools in case.dates (plan §5.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.rights.day_count import DateRule, count_days
from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.types import DateCalcResult


def date_calc(start: str, end: str, rule: str = "inclusive_day_1") -> DateCalcResult | ToolError:
    """Deterministic date arithmetic (custody days, 60/90-day windows). (plan §5.1)

    Args:
        start: see behaviour
        end: see behaviour
        rule: see rights/day_count.py

    Returns:
        DateCalcResult.
    """
    try:
        date_rule = DateRule(rule.strip().upper())
        value = count_days(start, end, date_rule)
    except ValueError as exc:
        return ToolError(tool="date_calc", kind="invalid_input", message=str(exc), retryable=True)
    return DateCalcResult(value=value, rule=date_rule.value, start=start, end=end)


DATE_CALC_SPEC = ToolSpec(
    name="date_calc",
    description="Deterministic date arithmetic (custody days, 60/90-day windows).",
    agents=[AgentName.PESHKAR, AgentName.SUTRADHAR, AgentName.VAKEEL],
    stores=[StoreName.CASE_TIMELINE],
    plan_ref="§5.1",
)
