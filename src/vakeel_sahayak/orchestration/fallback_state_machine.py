"""Plain Python state machine replacing LangGraph if needed (plan §3.3)."""

from __future__ import annotations

from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.record.event_log import EventLog


class PlainStateMachine:
    """Fallback runtime with the same event log if LangGraph gets in the way (plan §3.3)."""

    def __init__(self, log: EventLog) -> None:
        """Create the machine.

        Args:
            log: see behaviour
        """
        raise NotImplementedError

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Advance the state machine to the next gate or the end.

        Args:
            state: see behaviour

        Returns:
            Updated state.
        """
        raise NotImplementedError
