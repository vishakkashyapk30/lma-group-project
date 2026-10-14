"""Automatic typing of every error into the eleven classes of plan §15.9 and extraction of case-study candidates."""

from __future__ import annotations

from enum import Enum


class ErrorType(str, Enum):
    """Failure classes (plan §15.9)."""

    WRONG_ROUTE_OR_OCR = "WRONG_ROUTE_OR_OCR"
    WRONG_SPLIT_OR_TYPE = "WRONG_SPLIT_OR_TYPE"
    WRONG_SECTION_OR_DATE = "WRONG_SECTION_OR_DATE"
    UNSUPPORTED_FACT = "UNSUPPORTED_FACT"
    MISSED_FACTOR = "MISSED_FACTOR"
    MISGROUNDED_AUTHORITY = "MISGROUNDED_AUTHORITY"
    WRONG_TRANSFER = "WRONG_TRANSFER"
    OVERRULED_CITED = "OVERRULED_CITED"
    STALE_AFTER_UPDATE = "STALE_AFTER_UPDATE"
    MISSED_OBJECTION = "MISSED_OBJECTION"
    WRONG_RIGHTS_FLAG = "WRONG_RIGHTS_FLAG"


def type_errors(run_dir: str) -> dict[str, int]:
    """Count typed errors.

    Args:
        run_dir: see behaviour

    Returns:
        Counts per ErrorType.
    """
    raise NotImplementedError


def pick_case_studies(run_dir: str, n: int = 8) -> list[str]:
    """6-8 case studies incl. a Hindi bundle and a change set.

    Args:
        run_dir: see behaviour
        n: see behaviour

    Returns:
        Case ids.
    """
    raise NotImplementedError
