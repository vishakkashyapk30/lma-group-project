"""Fixed filter-relaxation order: factor, then section family, then court (plan §6.2 step 2.4)."""

from __future__ import annotations

from typing import Any

RELAXATION_ORDER: list[str] = ["factor", "section_family", "court"]


def relax(args: dict[str, Any], step: int) -> dict[str, Any]:
    """Drop or widen one filter.

    Args:
        args: see behaviour
        step: see behaviour

    Returns:
        New args.
    """
    raise NotImplementedError
