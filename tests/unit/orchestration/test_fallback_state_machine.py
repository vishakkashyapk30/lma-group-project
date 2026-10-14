"""orchestration/fallback_state_machine.PlainStateMachine: the LangGraph-free runtime (plan §3.3, §16).

Same event log, same gates: it advances to the next gate or the end and can never reach export without counsel's
approval at Gate 1 and Gate 2.
"""

from __future__ import annotations

import inspect

from tests.fakes.log import InMemoryEventLog
from vakeel_sahayak.orchestration.fallback_state_machine import PlainStateMachine
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.enums import EventKind, GateId, Stage

CASE = "case-0007"


def test_signatures():
    """PlainStateMachine(log).run(state) -> CaseGraphState."""
    assert list(inspect.signature(PlainStateMachine.__init__).parameters) == ["self", "log"]
    assert list(inspect.signature(PlainStateMachine.run).parameters) == ["self", "state"]


def test_run_stops_at_the_first_gate():
    """From a new case the machine runs intake and dossier steps, then stops pending Gate 1."""
    log = InMemoryEventLog()
    out = PlainStateMachine(log).run(CaseGraphState(case_id=CASE))
    assert isinstance(out, CaseGraphState)
    assert out.pending_gate == GateId.GATE_1_DOSSIER
    assert out.stage in (Stage.DOSSIER, Stage.RIGHTS)  # ASSUMPTION: Gate 1 follows the dossier / Rights Radar stage


def test_run_never_reaches_export_and_never_drafts_before_gate_1():
    """No brief, sparring record or file stage exists after the first run, and the log has no Gate 2 or export events."""
    log = InMemoryEventLog()
    out = PlainStateMachine(log).run(CaseGraphState(case_id=CASE))
    assert out.brief is None and out.sparring is None
    assert out.stage not in (Stage.BRIEF, Stage.SPAR, Stage.HEARING_PREP, Stage.FILE)
    opened = [e.inputs.get("gate") for e in log.events if e.kind == EventKind.GATE_OPENED]
    assert opened == ["GATE_1_DOSSIER"]
    assert not [e for e in log.events if e.kind == EventKind.GATE_APPROVED]


def test_run_again_without_approval_stays_at_gate_1():
    """Resuming a state that waits at Gate 1, with no approval in the log, does not advance past it."""
    log = InMemoryEventLog()
    machine = PlainStateMachine(log)
    first = machine.run(CaseGraphState(case_id=CASE))
    second = machine.run(first)
    assert second.pending_gate == GateId.GATE_1_DOSSIER
    assert second.stage == first.stage
    assert second.brief is None


def test_run_appends_events_for_what_it_did():
    """Every step appends events to the shared log (audit trail, plan §3.3), all for this case."""
    log = InMemoryEventLog()
    PlainStateMachine(log).run(CaseGraphState(case_id=CASE))
    assert log.events
    assert {e.case_id for e in log.events} == {CASE}
