"""The two approval gates as interrupts, and export blocked before Gate 2 (plan §3.1, §3.3, §16).

Real modules: `PlainStateMachine` (the LangGraph-free runtime with the same event log and gates), the real gate nodes and
`route_after_gate`, `GateGuard`, the SQLite `EventLog`, `export_case`. The agent nodes (intake, dossier, plan, draft, spar, hearing
prep) are replaced by fakes that leave exactly the record the agents leave (dossier field writes, rights view, brief and sparring
views); the document writers are recording stubs. The LangGraph variants are skipped when `langgraph` is not installed.

ASSUMPTIONS: nodes are looked up in `orchestration.graph` (`h.patch_nodes`); the machine decides whether a gate was passed from
the case record (a GATE_APPROVED event by counsel for that gate), not from the state it is handed; node names are the function
names without the `_node` suffix (tests/unit/orchestration/test_graph.py); GateGuard finds the log through `$VS_DATA_DIR`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.integration import _helpers as h
from tests.system._helpers import GROUNDS, clean_brief, clean_sparring
from tests.unit.export._helpers import Spy
from tests.unit.orchestration import _helpers as oh
from tests.unit.pipelines._helpers import patch_everywhere
from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.orchestration import graph
from vakeel_sahayak.orchestration.fallback_state_machine import PlainStateMachine
from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import ClaimCheck, EventKind, GateId, Stage
from vakeel_sahayak.schemas.ingestion_report import IngestionReport

CASE = h.CASE_ID
G1, G2 = GateId.GATE_1_DOSSIER, GateId.GATE_2_EXPORT
REFUSED = (ValueError, PermissionError)


def setup(tmp_path, monkeypatch, world, *, brief=None, sparring=None):
    """A case on a real SQLite log with fake agent nodes; returns the handles a test needs."""
    oh.point_default_log_at(tmp_path, monkeypatch)
    log, counts = EventLog(), {}
    brief = brief or clean_brief(CASE)

    def count(name: str) -> None:
        counts[name] = counts.get(name, 0) + 1

    def intake_node(state):
        count("intake")
        return state.model_copy(update={"stage": Stage.DOSSIER, "ingestion": IngestionReport(case_id=CASE, file="bundle_1.pdf")})

    def dossier_node(state):
        count("dossier")
        for e in h.dossier_events(CASE, world.dossier):
            log.append(e)
        log.append(h.view_write(CASE, "rights_report", world.rights, "PESHKAR"))
        return state.model_copy(update={"dossier": world.dossier, "rights": world.rights, "stage": Stage.RIGHTS})

    def plan_node(state):
        count("plan")
        return state.model_copy(update={"stage": Stage.BRIEF})

    def draft_node(state):
        count("draft")
        log.append(h.view_write(CASE, "brief", brief, "VAKEEL"))
        return state.model_copy(update={"brief": brief})

    def spar_node(state):
        count("spar")
        record = sparring or clean_sparring(CASE)
        log.append(h.view_write(CASE, "sparring", record, "ABHIYOJAK"))
        return state.model_copy(update={"sparring": record, "stage": Stage.SPAR})

    def hearing_prep_node(state):
        count("hearing_prep")
        return state.model_copy(update={"stage": Stage.HEARING_PREP})

    h.patch_nodes(monkeypatch, intake_node=intake_node, dossier_node=dossier_node, plan_node=plan_node, draft_node=draft_node,
                  spar_node=spar_node, hearing_prep_node=hearing_prep_node)
    spy = Spy()
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.application", "assemble_application_docx", spy.application)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.hearing_card", "build_hearing_card", spy.card)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.pdf", "docx_to_pdf", spy.pdf)
    return SimpleNamespace(log=log, guard=GateGuard(), machine=PlainStateMachine(log), counts=counts, spy=spy, world=world,
                           state=CaseGraphState(case_id=CASE))


def approved_gate_ids(env) -> list[str]:
    return [e.inputs["gate"] for e in env.log.read(CASE, kind=EventKind.GATE_APPROVED)]


# ---- Gate 1 ------------------------------------------------------------------------------------------------------
def test_the_graph_stops_at_gate_1_and_waits_for_counsel(tmp_path, monkeypatch, world):
    """Plan §3.1: intake and the dossier run, then the graph waits at Gate 1. Nothing is drafted, nothing is approved by an agent."""
    env = setup(tmp_path, monkeypatch, world)
    env.state = env.machine.run(env.state)
    assert env.state.pending_gate == G1
    assert env.counts == {"intake": 1, "dossier": 1}
    assert [e.inputs.get("gate") for e in env.log.read(CASE, kind=EventKind.GATE_OPENED)] == [G1.value]
    assert approved_gate_ids(env) == []
    assert env.state.brief is None


def test_running_again_without_approval_does_not_pass_gate_1(tmp_path, monkeypatch, world):
    env = setup(tmp_path, monkeypatch, world)
    first = env.machine.run(env.state)
    second = env.machine.run(first)
    assert second.pending_gate == G1 and "plan" not in env.counts and env.counts["intake"] == 1


def test_gate_1_cannot_be_approved_until_the_checklist_is_cleared(tmp_path, monkeypatch, world):
    """antecedents is UNSUPPORTED in case-0007, so approval needs counsel's acknowledgement (plan §13.5)."""
    env = setup(tmp_path, monkeypatch, world)
    env.state = env.machine.run(env.state)
    with pytest.raises(REFUSED):
        env.guard.approve(CASE, G1)
    assert env.machine.run(env.state).pending_gate == G1


def test_after_counsel_approves_gate_1_drafting_runs_up_to_gate_2(tmp_path, monkeypatch, world):
    """Plan §3.1: plan, draft, spar, hearing prep run after Gate 1; then the graph waits at Gate 2. Export has not run."""
    env = setup(tmp_path, monkeypatch, world)
    env.state = env.machine.run(env.state)
    env.guard.approve(CASE, G1, acknowledged=["antecedents"])
    env.state = env.machine.run(env.state)
    assert env.state.pending_gate == G2
    assert {k: env.counts[k] for k in ("plan", "draft", "spar", "hearing_prep")} == {"plan": 1, "draft": 1, "spar": 1, "hearing_prep": 1}
    assert env.counts["intake"] == 1 and env.counts["dossier"] == 1  # nothing earlier is redone
    assert env.spy.calls == []


# ---- export blocked before Gate 2 --------------------------------------------------------------------------------
def test_export_is_blocked_before_gate_2(tmp_path, monkeypatch, world):
    """Plan §16: the graph never reaches export while Gate 2 is pending, and the export node itself refuses to run."""
    env = setup(tmp_path, monkeypatch, world)
    env.state = env.machine.run(env.state)
    env.guard.approve(CASE, G1, acknowledged=["antecedents"])
    env.state = env.machine.run(env.state)
    assert env.state.pending_gate == G2
    with pytest.raises(REFUSED):
        graph.export_node(env.state)
    assert env.machine.run(env.state).pending_gate == G2
    assert env.spy.calls == []
    assert not [p for p in tmp_path.rglob("*") if p.suffix in (".docx", ".pdf")]


def test_gate_2_with_open_items_cannot_be_approved_and_export_stays_blocked(tmp_path, monkeypatch, world):
    """A NEEDS_REVIEW ground must be resolved first (plan §13.5); until then Gate 2 stays pending and nothing is exported."""
    brief = clean_brief(CASE).model_copy(update={"grounds": [GROUNDS["G2"]]})  # check defaults to NEEDS_REVIEW
    assert brief.grounds[0].check == ClaimCheck.NEEDS_REVIEW
    env = setup(tmp_path, monkeypatch, world, brief=brief)
    env.state = env.machine.run(env.state)
    env.guard.approve(CASE, G1, acknowledged=["antecedents"])
    env.state = env.machine.run(env.state)
    with pytest.raises(REFUSED):
        env.guard.approve(CASE, G2)
    assert env.machine.run(env.state).pending_gate == G2
    assert env.spy.calls == []


def test_after_gate_2_the_graph_exports_exactly_once(tmp_path, monkeypatch, world):
    """Plan §3.1: Gate 2 approved by counsel, then export: the writers run once; the stage becomes FILE."""
    env = setup(tmp_path, monkeypatch, world)
    env.state = env.machine.run(env.state)
    env.guard.approve(CASE, G1, acknowledged=["antecedents"])
    env.state = env.machine.run(env.state)
    env.guard.approve(CASE, G2)
    env.state = env.machine.run(env.state)
    assert env.state.stage == Stage.FILE and env.state.pending_gate is None
    assert env.spy.calls.count("application") == 1
    assert approved_gate_ids(env) == [G1.value, G2.value]


def test_only_counsel_ever_approves(tmp_path, monkeypatch, world):
    """No agent node approves a gate: every GATE_APPROVED event in the record is by counsel (plan §3.1, §16)."""
    env = setup(tmp_path, monkeypatch, world)
    env.state = env.machine.run(env.state)
    env.guard.approve(CASE, G1, acknowledged=["antecedents"])
    env.machine.run(env.state)
    approvals = env.log.read(CASE, kind=EventKind.GATE_APPROVED)
    assert approvals and all(str(getattr(e.actor, "value", e.actor)).lower() == "counsel" for e in approvals)


def test_a_second_case_cannot_ride_on_the_first_cases_approval(tmp_path, monkeypatch, world):
    """No bulk export: Gate 2 of case-0007 does nothing for case-0008 (plan §11, §16)."""
    env = setup(tmp_path, monkeypatch, world)
    env.state = env.machine.run(env.state)
    env.guard.approve(CASE, G1, acknowledged=["antecedents"])
    env.state = env.machine.run(env.state)
    env.guard.approve(CASE, G2)
    other = CaseGraphState(case_id="case-0008", stage=Stage.FILE, brief=env.state.brief, sparring=env.state.sparring)
    with pytest.raises(REFUSED):
        graph.export_node(other)


# ---- LangGraph ---------------------------------------------------------------------------------------------------
def thread(case: str = CASE) -> dict:
    return {"configurable": {"thread_id": case}}


def test_langgraph_interrupts_at_gate_1_and_resumes_after_approval(tmp_path, monkeypatch, world):
    """Gates are interrupts that wait for counsel (plan §3.3): the compiled graph pauses before gate1's decision and continues
    only after counsel's approval, from the saved checkpoint. ASSUMPTION: the thread id is the case id."""
    pytest.importorskip("langgraph")
    env = setup(tmp_path, monkeypatch, world)
    compiled = graph.build_graph(AppConfig())
    compiled.invoke(env.state, thread())
    assert compiled.get_state(thread()).next, "the graph must be waiting at a gate"
    assert approved_gate_ids(env) == []
    env.guard.approve(CASE, G1, acknowledged=["antecedents"])
    compiled.invoke(None, thread())
    snapshot = compiled.get_state(thread())
    assert snapshot.values["pending_gate"] == G2 or snapshot.next
    assert env.spy.calls == []


def test_langgraph_waiting_state_survives_a_new_process(tmp_path, monkeypatch, world):
    """Plan §3.3 'resuming after an Ada session ends': a freshly built graph on the same SQLite checkpointer still waits at the same gate."""
    pytest.importorskip("langgraph")
    env = setup(tmp_path, monkeypatch, world)
    first = graph.build_graph(AppConfig())
    first.invoke(env.state, thread())
    waiting = first.get_state(thread()).next
    again = graph.build_graph(AppConfig())
    assert again.get_state(thread()).next == waiting
