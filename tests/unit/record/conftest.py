"""Fixtures for record tests: a factory for a real SQLite EventLog on tmp_path."""

from __future__ import annotations

import pytest

from vakeel_sahayak.record.event_log import EventLog


@pytest.fixture()
def db_path(tmp_path) -> str:
    return str(tmp_path / "case-0007.sqlite")


@pytest.fixture()
def new_log(db_path):
    """`new_log()` opens an EventLog on tmp_path (called inside the test so failures are test failures, not errors)."""
    return lambda: EventLog(db_path)
