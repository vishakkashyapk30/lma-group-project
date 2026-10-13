"""FastAPI dependencies: config, stores, event log, agent context per case (plan §13.1)."""

from __future__ import annotations

from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.record.event_log import EventLog


def get_config() -> AppConfig:
    """Application config.

    Returns:
        AppConfig.
    """
    raise NotImplementedError


def get_event_log(case_id: str) -> EventLog:
    """Per-case event log.

    Args:
        case_id: see behaviour

    Returns:
        EventLog.
    """
    raise NotImplementedError


def get_gate_guard() -> GateGuard:
    """Gate guard.

    Returns:
        GateGuard.
    """
    raise NotImplementedError
