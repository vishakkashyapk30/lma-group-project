"""record/case_state.CaseState: typed container for the case's views, folded from the event log (plan §3.3, §7.4).

Uses the in-memory log mirror (tests/fakes/log.py) so only CaseState's own logic is under test. Payload shapes: see
tests/unit/record/_helpers.py (ASSUMPTION for the whole-object views; dossier/timeline shapes come from the fixture).
"""

from __future__ import annotations

import inspect


from tests.fakes.log import InMemoryEventLog
from tests.unit.record._helpers import gate_approved, gate_opened, view_write
from vakeel_sahayak.record.case_state import CaseState
from vakeel_sahayak.schemas.bail_brief import BailBrief, Ground
from vakeel_sahayak.schemas.enums import ClaimCheck, Factor, FactorStance, FieldStatus, GateId, SparringVerdict
from vakeel_sahayak.schemas.ingestion_report import FiledCounts, IngestionReport
from vakeel_sahayak.schemas.sparring import Objection, SparringRecord

CASE = "case-0007"


def _log(events) -> InMemoryEventLog:
    log = InMemoryEventLog()
    for e in events:
        log.append(e)
    return log


def test_case_state_exposes_the_documented_views():
    """CaseState has dossier, timeline, ingestion_report, rights_report, brief, sparring and approved_dossier_hash."""
    names = {"dossier", "timeline", "ingestion_report", "rights_report", "brief", "sparring", "approved_dossier_hash"}
    assert names <= {n for n, _ in inspect.getmembers(CaseState, inspect.isfunction)}
    assert list(inspect.signature(CaseState.__init__).parameters) == ["self", "case_id", "log"]


def test_dossier_view_is_folded_from_events(sample_events):
    """dossier() gives arrest_date 2024-08-20 VERIFIED and custody_days 167 COMPUTED from the fixture log."""
    d = CaseState(CASE, _log(sample_events)).dossier()
    assert d.case_id == CASE
    assert (d.fields.arrest_date.value, d.fields.arrest_date.status) == ("2024-08-20", FieldStatus.VERIFIED)
    assert (d.fields.custody_days.value, d.fields.custody_days.status) == (167, FieldStatus.COMPUTED)


def test_dossier_view_updates_when_new_events_are_appended(sample_events):
    """Views are not stored truth: appending an event changes the next call's result."""
    log = _log(sample_events[:6])  # up to ev006 (arrest_date written, first_remand not yet)
    state = CaseState(CASE, log)
    assert state.dossier().fields.first_remand.value is None
    log.append(sample_events[6])  # ev007 first_remand
    assert state.dossier().fields.first_remand.value == "2024-08-21"


def test_timeline_view_sorted(sample_events):
    """timeline() returns the three filed events sorted by date."""
    tl = CaseState(CASE, _log(sample_events)).timeline()
    assert [e.date for e in tl] == ["2024-08-20", "2024-08-21", "2024-11-02"]


def test_view_ignores_other_cases(sample_events):
    """Events of another case never leak into this case's views."""
    other = [e.model_copy(update={"case_id": "case-0008", "event_id": ""}) for e in sample_events]
    log = _log([*sample_events, *other])
    assert [e.event_id for e in CaseState(CASE, log).timeline()] == ["e3", "e4", "e6"]
    assert CaseState("case-0099", log).timeline() == []


def test_rights_report_view_is_the_latest_written(expected_rights_report):
    """rights_report() returns the most recent RightsReport view event."""
    older = expected_rights_report.model_copy(update={"as_of": "2025-01-01"})
    log = _log([view_write(CASE, "rights_report", older), view_write(CASE, "rights_report", expected_rights_report)])
    got = CaseState(CASE, log).rights_report()
    assert got == expected_rights_report
    assert got.as_of == "2025-02-03"


def test_ingestion_report_view_is_the_latest_written():
    """ingestion_report() returns the latest IngestionReport."""
    first = IngestionReport(case_id=CASE, file="bundle_1.pdf", questions=["page 3 unreadable"])
    second = IngestionReport(case_id=CASE, file="bundle_1.pdf", filed=FiledCounts(timeline_events=3), questions=[])
    log = _log([view_write(CASE, "ingestion_report", first, "MUNSHI"), view_write(CASE, "ingestion_report", second, "MUNSHI")])
    got = CaseState(CASE, log).ingestion_report()
    assert got == second and got.filed.timeline_events == 3


def test_brief_view_keeps_grounds_and_claim_state():
    """brief() returns the BailBrief with its grounds and their check results."""
    brief = BailBrief(
        case_id=CASE,
        grounds=[
            Ground(id="G1", factor=Factor.PARITY_WITH_CO_ACCUSED, stance=FactorStance.FAVOURABLE, argument="a", check=ClaimCheck.SUPPORTED),
            Ground(id="G2", factor=Factor.CUSTODY_PERIOD, stance=FactorStance.FAVOURABLE, argument="b", check=ClaimCheck.NEEDS_REVIEW),
        ],
    )
    got = CaseState(CASE, _log([view_write(CASE, "brief", brief)])).brief()
    assert got == brief
    assert [g.check for g in got.grounds] == [ClaimCheck.SUPPORTED, ClaimCheck.NEEDS_REVIEW]


def test_sparring_view():
    """sparring() returns the SparringRecord including verdicts."""
    rec = SparringRecord(
        case_id=CASE,
        rounds=2,
        objections=[Objection(id="O1", against="G1", factor="parity_with_co_accused", objection="x", verdict=SparringVerdict.UNANSWERED)],
    )
    got = CaseState(CASE, _log([view_write(CASE, "sparring", rec, "ABHIYOJAK")])).sparring()
    assert got == rec and got.objections[0].verdict == SparringVerdict.UNANSWERED


def test_approved_dossier_hash_is_none_before_gate_1_approval(sample_events):
    """No GATE_APPROVED yet means no approved hash (the fixture's events up to GATE_OPENED, ev010)."""
    before = [e for e in sample_events if e.event_id <= "ev010"]
    assert CaseState(CASE, _log(before)).approved_dossier_hash() is None


def test_approved_dossier_hash_is_none_for_empty_log():
    """A case with no events has no approved hash."""
    assert CaseState(CASE, _log([])).approved_dossier_hash() is None


def test_approved_dossier_hash_after_gate_1_approval(sample_events):
    """After the fixture's Gate-1 approval (ev011) the hash is 'h:0a1b'."""
    assert CaseState(CASE, _log(sample_events)).approved_dossier_hash() == "h:0a1b"


def test_approved_dossier_hash_is_the_last_gate_1_approval():
    """With a re-approval after a change set (plan §7.4) the newest Gate-1 hash wins."""
    g1 = GateId.GATE_1_DOSSIER.value
    log = _log([
        gate_opened(CASE, g1), gate_approved(CASE, g1, ["antecedents"], "h:0a1b"),
        gate_opened(CASE, g1), gate_approved(CASE, g1, [], "h:7777"),
    ])
    assert CaseState(CASE, log).approved_dossier_hash() == "h:7777"


def test_gate_2_approval_does_not_change_the_dossier_hash():
    """Only Gate-1 approvals define the change-detection baseline."""
    g1, g2 = GateId.GATE_1_DOSSIER.value, GateId.GATE_2_EXPORT.value
    log = _log([gate_approved(CASE, g1, [], "h:0a1b"), gate_approved(CASE, g2, [], "h:9999")])
    assert CaseState(CASE, log).approved_dossier_hash() == "h:0a1b"
