"""Shared runtime for tools: configuration, per-case event logs and the law stores (plan §3.3, §5.5).

Tools are plain functions, so the resources they need (the case's event log, the statute and concordance stores) come
from one process-wide runtime that tests and the API can replace with `set_runtime`. Nothing is opened at import time.
"""

from __future__ import annotations

import threading

from vakeel_sahayak.config import AppConfig, load_config
from vakeel_sahayak.record.event_log import EventLog


class ToolRuntime:
    """Lazily opened resources shared by the tools."""

    def __init__(self, config: AppConfig | None = None) -> None:
        """Create a runtime.

        Args:
            config: defaults to load_config()
        """
        self.config = config or load_config()
        self._lock = threading.RLock()
        self._logs: dict[str, EventLog] = {}
        self._statutes = None
        self._concordance = None
        self.current_case_id: str | None = None  # the case being worked on; tools that take no case id read it (file_item)

    def event_log(self, case_id: str) -> EventLog:
        """The case's event log (one SQLite file per case), opened once."""
        with self._lock:
            if case_id not in self._logs:
                self._logs[case_id] = EventLog.for_case(case_id, self.config.paths.cases_dir)
            return self._logs[case_id]

    def attach_log(self, case_id: str, log: EventLog) -> None:
        """Use an existing log for a case (tests, or a log shared with the API)."""
        with self._lock:
            self._logs[case_id] = log

    def statutes(self):  # noqa: ANN201
        """The law.statutes store (offline seed when the SQLite file is absent)."""
        from vakeel_sahayak.stores.law_statutes import StatuteStore

        with self._lock:
            if self._statutes is None:
                self._statutes = StatuteStore()
                self._statutes.open()
            return self._statutes

    def concordance(self):  # noqa: ANN201
        """The law.concordance store (offline seed when the SQLite file is absent)."""
        from vakeel_sahayak.stores.law_concordance import ConcordanceStore

        with self._lock:
            if self._concordance is None:
                self._concordance = ConcordanceStore()
                self._concordance.open()
            return self._concordance


_runtime: ToolRuntime | None = None


def get_runtime() -> ToolRuntime:
    """The process-wide runtime, created on first use."""
    global _runtime
    if _runtime is None:
        _runtime = ToolRuntime()
    return _runtime


def set_runtime(runtime: ToolRuntime | None) -> None:
    """Replace the process-wide runtime (None resets it so the next call builds a fresh one)."""
    global _runtime
    _runtime = runtime
