"""Run-time leakage rule: every query only sees documents dated before the case's order (plan §2).

Two guards, both enforced in the shared-store search methods (and therefore in the tools built on them):
the `before` date is mandatory and applied as a pre-filter, and authorities are cited from reasoning paragraphs only
(plan §5.2). Test orders and same-FIR orders are excluded earlier, when the stores are built (`pipelines/leakage.py`).
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.enums import OrderPart
from vakeel_sahayak.schemas.ids import check_iso_date


class LeakageError(ValueError):
    """A query or result would break a leakage rule (plan §2)."""


def apply_before_filter(filters: dict[str, Any], before: str) -> dict[str, Any]:
    """Add the date filter to a query's filters; raise if absent.

    Args:
        filters: the query's other filters (not modified)
        before: ISO date of the case's order; only documents dated strictly before it are visible

    Returns:
        A copy of `filters` with `before` set.

    Raises:
        LeakageError: when `before` is missing or empty (the date filter is mandatory).
        ValueError: when `before` is not an ISO date 'YYYY-MM-DD'.
    """
    if not before:
        raise LeakageError("a 'before' date (the case's order date) is required for every shared-store query (plan §2)")
    return {**filters, "before": check_iso_date(before)}


def require_reasoning(part: OrderPart | str) -> OrderPart:
    """Authorities are cited from reasoning paragraphs only (plan §5.2).

    Args:
        part: the part a caller asks the authority store for

    Returns:
        OrderPart.REASONING.

    Raises:
        LeakageError: for any other part.
    """
    if OrderPart(part) != OrderPart.REASONING:
        raise LeakageError("authorities are cited from 'reasoning' paragraphs only; counsel's submissions are never authority")
    return OrderPart.REASONING


def assert_all_before(dates: list[str | None], before: str) -> None:
    """Defence in depth on a result set: every document must be dated strictly before `before`.

    Raises:
        LeakageError: when a result is undated or not earlier than `before`.
    """
    bad = [d for d in dates if not d or d >= before]
    if bad:
        raise LeakageError(f"{len(bad)} result(s) are not dated before {before}")
