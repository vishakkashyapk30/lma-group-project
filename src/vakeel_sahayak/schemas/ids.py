"""Identifiers and ISO date/time validators shared by the schemas (plan §3.3, §7.1)."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

CASE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"  # safe as a directory name: no dots, slashes or spaces
_CASE_ID_RE = re.compile(CASE_ID_PATTERN)


def check_case_id(value: str) -> str:
    """Return `value` if it is a valid case id (for example 'case-0007'), else raise ValueError.

    Args:
        value: candidate id

    Returns:
        The same id.
    """
    if not _CASE_ID_RE.match(value):
        raise ValueError(f"invalid case id {value!r}: use letters, digits, '-' and '_' (max 64 chars)")
    return value


def check_iso_date(value: str) -> str:
    """Return `value` if it is a calendar date 'YYYY-MM-DD', else raise ValueError."""
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"not an ISO date (YYYY-MM-DD): {value!r}") from exc
    if len(value) != 10:
        raise ValueError(f"not an ISO date (YYYY-MM-DD): {value!r}")
    return value


def parse_iso_datetime(value: str) -> datetime:
    """`datetime.fromisoformat` that also accepts a trailing 'Z' (UTC), which Python before 3.11 rejects.

    Raises:
        ValueError: when `value` is not an ISO-8601 date-time.
    """
    text = value.strip()
    if text[-1:] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def check_iso_datetime(value: str) -> str:
    """Return `value` if it parses as an ISO-8601 date-time, else raise ValueError."""
    try:
        parse_iso_datetime(value)
    except ValueError as exc:
        raise ValueError(f"not an ISO-8601 timestamp: {value!r}") from exc
    return value


CaseId = Annotated[str, StringConstraints(min_length=1), AfterValidator(check_case_id)]
IsoDate = Annotated[str, AfterValidator(check_iso_date)]
IsoDateTime = Annotated[str, AfterValidator(check_iso_datetime)]


def utc_now() -> str:
    """Current time as an ISO-8601 UTC string with microseconds (plan §3.3 'the time')."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_event_id() -> str:
    """Fresh unique event id, 'evt-' plus 16 hex characters."""
    return f"evt-{uuid.uuid4().hex[:16]}"
