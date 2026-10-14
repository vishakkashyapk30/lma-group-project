"""Report results separately for test orders dated after the Qwen3 release (April 2025) (plan §15.9)."""

from __future__ import annotations


def split_by_release_date(case_ids: list[str]) -> tuple[list[str], list[str]]:
    """(before_release, after_release).

    Args:
        case_ids: see behaviour

    Returns:
        Two lists.
    """
    raise NotImplementedError
