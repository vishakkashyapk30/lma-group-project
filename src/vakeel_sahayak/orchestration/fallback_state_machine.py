"""Plain Python state machine replacing LangGraph if needed (plan §3.3, §16).

Same event log, same gates: `PlainStateMachine` advances a case to the next gate or the end and can never reach export
without counsel's approval at Gate 1 and Gate 2. It shares the node bodies of `orchestration.graph` and calls
`gates.await_gate` with `interrupt=False`, so a run simply stops at an unapproved gate (no LangGraph interrupt). It is
selected when langgraph is missing or `VS_ORCHESTRATOR=plain`.
"""

from __future__ import annotations

from vakeel_sahayak.orchestration import graph
from vakeel_sahayak.orchestration.gates import await_gate
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import GateId, Stage


class PlainStateMachine:
    """Fallback runtime with the same event log if LangGraph gets in the way (plan §3.3)."""

    def __init__(self, log: EventLog) -> None:
        """Create the machine.

        Args:
            log: the case's event log; every agent step and gate writes to it (the shared audit trail).
        """
        self.log = log

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Advance the state machine to the next gate or the end.

        From a fresh case it runs intake and dossier, then stops pending Gate 1. Resumed after counsel approves Gate 1
        it plans, drafts, spars and prepares the hearing card, then stops pending Gate 2. Resumed after Gate 2 it
        exports. With no approval in the log it does not advance past the open gate.

        Args:
            state: the current state (fresh, or resuming at a gate)

        Returns:
            Updated state.
        """
        from vakeel_sahayak.tools.runtime import get_runtime

        get_runtime().attach_log(state.case_id, self.log)  # agents resolve this log through the runtime

        if state.stage == Stage.INTAKE:
            state = graph.intake_node(state)
            state = graph.dossier_node(state)

        state = await_gate(state, GateId.GATE_1_DOSSIER, log=self.log, interrupt=False)
        if state.gate_state(GateId.GATE_1_DOSSIER) != "approved":
            return state  # stops at Gate 1 until counsel approves
        state = state.model_copy(update={"stage": Stage.BRIEF})

        state = graph.plan_node(state)
        state = graph.draft_node(state)
        state = graph.spar_node(state)
        state = graph.hearing_prep_node(state)

        state = await_gate(state, GateId.GATE_2_EXPORT, log=self.log, interrupt=False)
        if state.gate_state(GateId.GATE_2_EXPORT) != "approved":
            return state  # stops at Gate 2 until counsel approves
        state = state.model_copy(update={"stage": Stage.FILE})

        return graph.export_node(state)
