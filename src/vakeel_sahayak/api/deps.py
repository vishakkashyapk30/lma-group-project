"""FastAPI dependencies: config, the shared case record (event log) and the gate guard (plan §13.1).

The whole case record is one SQLite log under `$VS_DATA_DIR` (`record.sqlite`), shared by every case (rows are filtered by
`case_id`). `get_event_log` returns one log per data directory, so the API, the agents it runs and the tests all read and
write the same record; tests override it through `app.dependency_overrides[deps.get_event_log]`.
"""

from __future__ import annotations

import os
from pathlib import Path

from vakeel_sahayak.config import AppConfig, load_config
from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.record.event_log import EventLog


def get_config() -> AppConfig:
    """Application config (honours `VS_CONFIG_DIR`).

    Returns:
        AppConfig.
    """
    return load_config(os.environ.get("VS_CONFIG_DIR"))


def _data_dir() -> Path:
    """The data directory of the current environment (`VS_DATA_DIR`, else the configured one)."""
    return Path(os.environ.get("VS_DATA_DIR") or get_config().paths.data_dir).resolve()


def get_event_log(case_id: str | None = None) -> EventLog:
    """The shared case record for this data directory (one SQLite log for every case).

    Args:
        case_id: the case (the log filters its rows by it; one log holds every case)

    Returns:
        EventLog.
    """
    # One SQLite file per data directory; every connection to it shares the same rows (no in-process cache, so tests
    # with different `VS_DATA_DIR`s never leak into one another).
    return EventLog(str(_data_dir() / "record.sqlite"))


def get_gate_guard() -> GateGuard:
    """Gate guard bound to the shared case record.

    Returns:
        GateGuard.
    """
    return GateGuard(get_event_log())
