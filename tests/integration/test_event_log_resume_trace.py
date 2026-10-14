"""The event log as the one mechanism behind four uses (plan §3.3): audit trail, resuming after an Ada session ends, the live agent
trace, and dependency tracking for incremental redrafting (§10). Here the real SQLite `EventLog`, `CaseState` (views folded from the
log) and `views.audit_trail` meet a real agent run (Munshi on the constructed bundle) and truth maintenance.

Payload shapes of record events: tests/unit/record/_helpers.py. ASSUMPTION: a TOOL_RESULT's `parent_id` is its TOOL_CALL's id and a
STORE_WRITE made by a tool call has the TOOL_RESULT as parent (as in tests/fixtures/case_0007/events.jsonl).
"""

from __future__ import annotations

from tests.fakes.toolbox import leaked_names
from tests.integration import _helpers as h
from tests.unit.record._helpers import dossier_events, gate_approved, gate_opened, make_event, view_write
from vakeel_sahayak.agents.munshi.agent import MunshiAgent
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.record import views
from vakeel_sahayak.record.case_state import CaseState
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.bail_brief import BailBrief, DependsOn, Ground
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.enums import AgentName, EventKind, Factor, FactorStance, GateId, Stage
from vakeel_sahayak.schemas.sparring import SparringRecord
from vakeel_sahayak.truth_maintenance.staleness import mark_stale

CASE = h.CASE_ID
G1 = GateId.GATE_1_DOSSIER.value


def seed(log: EventLog, dossier, rights, brief: BailBrief | None = None, sparring: SparringRecord | None = None) -> None:
    """A case record as the agents leave it: dossier fields, timeline, rights view, Gate 1, then brief and sparring."""
    for e in dossier_events(CASE, dossier):
        log.append(e)
    log.append(view_write(CASE, "rights_report", rights, "PESHKAR"))
    log.append(gate_opened(CASE, G1))
    log.append(gate_approved(CASE, G1, ["antecedents"], "h:0a1b"))
    if brief is not None:
        log.append(view_write(CASE, "brief", brief, "VAKEEL"))
        log.append(view_write(CASE, "sparring", sparring or SparringRecord(case_id=CASE), "ABHIYOJAK"))


def munshi_run(tmp_path, install_stores):
    world = h.fresh_case_world()
    install_stores(world.stores)
    tb = h.ScenarioToolbox(world, pages=h.build_bundle(), boundaries=h.BUNDLE_BOUNDARIES, answers=[""] * 6)
    llm = h.make_llm(where="laptop", events=h.munshi_events_responder(), free="")
    agent, ctx, _ = h.build_agent(MunshiAgent, llm=llm, toolbox=tb, world=world, sqlite_dir=tmp_path)
    agent.run(h.seed_state())
    return ctx.log, tb


# ---- audit trail and the live trace ------------------------------------------------------------------------------
def test_a_real_agent_run_leaves_one_event_pair_per_tool_call(tmp_path, install_stores):
    """Every agent action appends an event (plan §3.3): TOOL_CALL then TOOL_RESULT for each of the toolbox's calls."""
    log, tb = munshi_run(tmp_path, install_stores)
    events = log.read(CASE)
    calls = [e for e in events if e.kind == EventKind.TOOL_CALL]
    assert len(calls) == len(tb.calls) > 10
    assert [e.tool for e in calls] == [c.name for c in tb.calls]
    assert len([e for e in events if e.kind == EventKind.TOOL_RESULT]) == len(calls)


def test_audit_trail_rows_say_who_which_tool_and_when(tmp_path, install_stores):
    """Plan §3.3 use 1: the trail lists every event with actor, tool, sources and time, in order."""
    log, _ = munshi_run(tmp_path, install_stores)
    events = log.read(CASE)
    rows = views.audit_trail(events)
    assert len(rows) == len(events)
    assert [r["time"] for r in rows] == sorted(r["time"] for r in rows)
    assert {str(getattr(r["actor"], "value", r["actor"])) for r in rows if r["tool"]} == {AgentName.MUNSHI.value}
    filed = [r for r in rows if r["tool"] == "file_item"]
    assert filed and all(r["sources"] for r in filed)


def test_children_follow_the_causal_chain_of_a_tool_call(tmp_path, install_stores):
    """Plan §3.3 use 4 and §10: from a call one can reach its result and what was written because of it."""
    log, _ = munshi_run(tmp_path, install_stores)
    events = log.read(CASE)
    call = next(e for e in events if e.kind == EventKind.TOOL_CALL and e.tool == "file_item")
    kids = log.children(call.event_id)
    assert [e.kind for e in kids][:1] == [EventKind.TOOL_RESULT]
    assert all(k.parent_id for k in kids)
    assert call.event_id not in {k.event_id for k in kids}


def test_event_ids_are_unique_and_the_log_is_in_time_order(tmp_path, install_stores):
    log, _ = munshi_run(tmp_path, install_stores)
    events = log.read(CASE)
    assert len({e.event_id for e in events}) == len(events)
    assert [e.ts for e in events] == sorted(e.ts for e in events)


def test_the_log_holds_pseudonymised_text_only(tmp_path, install_stores):
    """Plan §16: no planted name (English or Devanagari) in anything the real SQLite log stored."""
    log, _ = munshi_run(tmp_path, install_stores)
    assert leaked_names([e.model_dump_json() for e in log.read(CASE)], h.PLANTED_NAMES + h.PLANTED_NAMES_HI) == []


# ---- resume ------------------------------------------------------------------------------------------------------
def test_views_survive_a_restart_of_the_process(tmp_path, dossier, expected_rights_report):
    """Plan §3.3 use 2: after the session ends, a new EventLog on the same file gives the same dossier, timeline, brief and record."""
    path = str(tmp_path / "events.sqlite")
    brief = BailBrief(case_id=CASE, grounds=[Ground(id="G1", factor=Factor.PARITY_WITH_CO_ACCUSED, stance=FactorStance.FAVOURABLE, argument=h.G1_TEXT)])
    log = EventLog(path)
    seed(log, dossier, expected_rights_report, brief)
    before = CaseState(CASE, log)
    snapshot = (before.dossier(), before.rights_report(), before.brief(), before.sparring(), before.approved_dossier_hash())
    del log, before
    after = CaseState(CASE, EventLog(path))
    assert (after.dossier(), after.rights_report(), after.brief(), after.sparring(), after.approved_dossier_hash()) == snapshot
    assert after.approved_dossier_hash() == "h:0a1b"


def test_graph_state_can_be_rebuilt_from_the_log_alone(tmp_path, dossier, expected_rights_report):
    """A session cut at 6 h loses nothing: the state the graph needs (dossier, rights, brief, sparring) is a fold of the log."""
    log = EventLog(str(tmp_path / "events.sqlite"))
    seed(log, dossier, expected_rights_report, BailBrief(case_id=CASE), SparringRecord(case_id=CASE, rounds=2))
    cs = CaseState(CASE, EventLog(str(tmp_path / "events.sqlite")))
    state = CaseGraphState(case_id=CASE, stage=Stage.BRIEF, dossier=cs.dossier(), rights=cs.rights_report(), brief=cs.brief(), sparring=cs.sparring())
    assert state.dossier.fields == dossier.fields
    assert state.rights == expected_rights_report
    assert state.sparring.rounds == 2


def test_a_second_case_in_the_same_file_does_not_leak_into_the_first(tmp_path, dossier, expected_rights_report):
    log = EventLog(str(tmp_path / "events.sqlite"))
    seed(log, dossier, expected_rights_report)
    log.append(make_event("case-0008", EventKind.AGENT_MESSAGE, "MUNSHI", outputs={"note": "other case"}))
    assert all(e.case_id == CASE for e in log.read(CASE))
    assert [e.case_id for e in log.read("case-0008")] == ["case-0008"]


# ---- dependencies ------------------------------------------------------------------------------------------------
def test_events_written_after_the_approval_are_what_change_detection_sees(tmp_path, dossier, expected_rights_report):
    """Plan §7.4, §10: the new timeline writes since the Gate 1 approval become `new_event_ids`, and a claim that depends on one of them goes stale."""
    log = EventLog(str(tmp_path / "events.sqlite"))
    seed(log, dossier, expected_rights_report)
    approval = log.read(CASE, kind=EventKind.GATE_APPROVED)[-1]
    call = log.append(make_event(CASE, EventKind.TOOL_CALL, "MUNSHI", tool="file_item", inputs={"file": "order_sheet.pdf", "page": 1}))
    result = log.append(make_event(CASE, EventKind.TOOL_RESULT, "MUNSHI", tool="file_item", parent_id=call.event_id))
    log.append(make_event(CASE, EventKind.STORE_WRITE, "MUNSHI", tool="file_item", parent_id=result.event_id,
                          inputs={"store": "case.timeline"},
                          outputs={"event": {"event_id": "e6b", "date": "2024-11-02", "label": "Charge sheet filed"}}))
    later = [e for e in log.read(CASE, since=approval.ts) if e.event_id != approval.event_id and e.kind == EventKind.STORE_WRITE]
    new_ids = [e.outputs["event"]["event_id"] for e in later if e.inputs.get("store") == "case.timeline"]
    assert new_ids == ["e6b"]
    ground = Ground(id="G2", factor=Factor.CHARGE_SHEET_FILED, stance=FactorStance.FAVOURABLE, argument="Charge sheet pending [F:charge_sheet].",
                    depends_on=DependsOn(events=["e6b"]))
    brief = BailBrief(case_id=CASE, grounds=[ground])
    assert mark_stale(brief, ChangeSet(case_id=CASE, trigger="new_document", new_event_ids=new_ids)) == ["G2"]
    assert [k.kind for k in log.children(call.event_id)] == [EventKind.TOOL_RESULT, EventKind.STORE_WRITE]
