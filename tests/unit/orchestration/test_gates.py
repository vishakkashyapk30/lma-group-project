"""orchestration/gates.GateGuard: approval gates and the export guard (plan §3.1, §11, §13.5, §16).

Gate checklist (plan §13.5): every UNSUPPORTED field resolved or acknowledged (Gate 1); every NEEDS_REVIEW ground and
UNANSWERED objection resolved (Gate 2). Export works only after Gate 2 of this very case, enforced in code; there is no
bulk export, so approving case A never lets case B export. The case record is seeded through a real SQLite EventLog
(see _helpers.py for the ASSUMPTION about how GateGuard finds it). Refusals raise ValueError or PermissionError
(ASSUMPTION; NotImplementedError is deliberately not accepted).
"""

from __future__ import annotations

import inspect

import pytest

from tests.unit.orchestration import _helpers as h
from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.case import GateStatus
from vakeel_sahayak.schemas.enums import ClaimCheck, EventKind, GateId, SparringVerdict

CASE = "case-0007"
CASE_B = "case-0008"
G1, G2 = GateId.GATE_1_DOSSIER, GateId.GATE_2_EXPORT
REFUSED = (ValueError, PermissionError)


def test_gate_guard_signatures():
    """GateGuard.status(case_id, gate), approve(case_id, gate, acknowledged=None), assert_export_allowed(case_id)."""
    assert list(inspect.signature(GateGuard.status).parameters) == ["self", "case_id", "gate"]
    p = inspect.signature(GateGuard.approve).parameters
    assert list(p) == ["self", "case_id", "gate", "acknowledged"] and p["acknowledged"].default is None
    assert list(inspect.signature(GateGuard.assert_export_allowed).parameters) == ["self", "case_id"]


def test_gate_status_schema_defaults():
    """A GateStatus lists unresolved UNSUPPORTED, NEEDS_REVIEW and UNANSWERED items, empty by default (plan §13.5)."""
    s = GateStatus(gate=G1, open=True)
    assert (s.unresolved_unsupported, s.unresolved_needs_review, s.unresolved_unanswered) == ([], [], [])


class _Lazy:
    """Builds its target on first attribute access, so a not-yet-implemented EventLog fails inside the test body."""

    def __init__(self, build):
        self._build, self._target = build, None

    def __getattr__(self, name):
        if self._target is None:
            self._target = self._build()
        return getattr(self._target, name)


@pytest.fixture()
def env(tmp_path, monkeypatch, dossier):
    """A case-0007 record with the fixture dossier (antecedents UNSUPPORTED) and Gate 1 open."""

    def build():
        h.point_default_log_at(tmp_path, monkeypatch)
        log = EventLog()
        h.seed_dossier(log, CASE, dossier)
        return type("Env", (), {"log": log, "guard": GateGuard(), "dossier": dossier})

    return _Lazy(build)


# ---------------------------------------------------------------------------------------------------------------------
# Gate 1
# ---------------------------------------------------------------------------------------------------------------------
def test_gate1_status_lists_unsupported_antecedents(env):
    """In case-0007 the only UNSUPPORTED field is antecedents, so the Gate 1 checklist is exactly ['antecedents']."""
    st = env.guard.status(CASE, G1)
    assert isinstance(st, GateStatus)
    assert st.gate == G1
    assert st.unresolved_unsupported == ["antecedents"]
    assert st.unresolved_needs_review == [] and st.unresolved_unanswered == []


def test_gate1_status_empty_when_dossier_is_fully_resolved(tmp_path, monkeypatch, dossier):
    """Once counsel answered antecedents (USER_STATED) nothing is UNSUPPORTED."""
    h.point_default_log_at(tmp_path, monkeypatch)
    log = EventLog()
    h.seed_dossier(log, CASE, h.resolved_dossier(dossier))
    assert GateGuard().status(CASE, G1).unresolved_unsupported == []


def test_gate1_approve_raises_while_unsupported_field_is_unresolved(env):
    """approve() with no acknowledgement raises and records no approval."""
    with pytest.raises(REFUSED):
        env.guard.approve(CASE, G1)
    assert env.log.read(CASE, kind=EventKind.GATE_APPROVED) == []


def test_gate1_approve_raises_when_wrong_field_is_acknowledged(env):
    """Acknowledging a field that is not the unresolved one does not clear the checklist."""
    with pytest.raises(REFUSED):
        env.guard.approve(CASE, G1, acknowledged=["personal"])
    assert env.log.read(CASE, kind=EventKind.GATE_APPROVED) == []


def test_gate1_approve_succeeds_when_antecedents_acknowledged(env):
    """acknowledged=['antecedents'] clears Gate 1 and appends a GATE_APPROVED event by counsel with the dossier hash."""
    env.guard.approve(CASE, G1, acknowledged=["antecedents"])
    (ev,) = env.log.read(CASE, kind=EventKind.GATE_APPROVED)
    assert ev.inputs["gate"] == "GATE_1_DOSSIER"
    assert ev.inputs["acknowledged"] == ["antecedents"]
    assert ev.actor == "counsel"
    assert str(ev.outputs["dossier_hash"]).startswith("h:")


def test_gate1_approve_succeeds_without_ack_when_nothing_unresolved(tmp_path, monkeypatch, dossier):
    """A fully resolved dossier needs no acknowledgement."""
    h.point_default_log_at(tmp_path, monkeypatch)
    log = EventLog()
    h.seed_dossier(log, CASE, h.resolved_dossier(dossier))
    GateGuard().approve(CASE, G1)
    assert len(log.read(CASE, kind=EventKind.GATE_APPROVED)) == 1


def test_gate1_hash_tracks_dossier_content(tmp_path, monkeypatch, dossier):
    """The recorded dossier hash is stable for an unchanged dossier and changes when a field is edited (plan §7.4)."""
    from tests.unit.record._helpers import field_write

    h.point_default_log_at(tmp_path, monkeypatch)
    log, guard = EventLog(), GateGuard()
    h.seed_dossier(log, CASE, h.resolved_dossier(dossier))
    guard.approve(CASE, G1)
    guard.approve(CASE, G1)  # re-approval of an unchanged dossier
    log.append(field_write(CASE, "arrest_date", {"value": "2024-08-19", "source": None, "status": "USER_EDITED"}, "counsel"))
    guard.approve(CASE, G1)
    hashes = [e.outputs["dossier_hash"] for e in log.read(CASE, kind=EventKind.GATE_APPROVED)]
    assert len(hashes) == 3
    assert hashes[0] == hashes[1] != hashes[2]


# ---------------------------------------------------------------------------------------------------------------------
# Gate 2
# ---------------------------------------------------------------------------------------------------------------------
@pytest.fixture()
def env2(env):
    """case-0007 after Gate 1, with a brief (G2 NEEDS_REVIEW) and a sparring record (O2, O3 UNANSWERED)."""

    def build():
        h.approve(env.log, CASE, h.G1, ["antecedents"], "h:0a1b")
        h.seed_brief_and_sparring(
            env.log,
            CASE,
            grounds=[
                h.ground("G1", ClaimCheck.SUPPORTED),
                h.ground("G2", ClaimCheck.NEEDS_REVIEW),
                h.ground("G3", ClaimCheck.REPAIRED),
            ],
            objections=[
                h.objection("O1", SparringVerdict.ANSWERED),
                h.objection("O2", SparringVerdict.UNANSWERED, against="G2"),
                h.objection("O3", SparringVerdict.UNANSWERED, against="G3"),
            ],
        )
        return env

    return _Lazy(build)


def test_gate2_status_lists_needs_review_grounds_and_unanswered_objections(env2):
    """Gate 2 lists NEEDS_REVIEW grounds (SUPPORTED and REPAIRED are fine) and UNANSWERED objections."""
    st = env2.guard.status(CASE, G2)
    assert st.gate == G2
    assert st.unresolved_needs_review == ["G2"]
    assert st.unresolved_unanswered == ["O2", "O3"]


def test_gate2_approve_raises_while_items_unresolved(env2):
    """Gate 2 cannot be approved with a NEEDS_REVIEW ground or an UNANSWERED objection outstanding."""
    with pytest.raises(REFUSED):
        env2.guard.approve(CASE, G2)
    assert env2.log.read(CASE, kind=EventKind.GATE_APPROVED, actor="counsel")[0].inputs["gate"] == "GATE_1_DOSSIER"
    assert len(env2.log.read(CASE, kind=EventKind.GATE_APPROVED)) == 1


def _clean_gate2_case(log: EventLog, case: str) -> None:
    h.seed_brief_and_sparring(
        log,
        case,
        grounds=[h.ground("G1", ClaimCheck.SUPPORTED), h.ground("G3", ClaimCheck.REPAIRED)],
        objections=[h.objection("O1", SparringVerdict.ANSWERED)],
    )


def test_gate2_status_is_empty_for_a_clean_brief(env):
    """No NEEDS_REVIEW ground and no UNANSWERED objection gives an empty Gate 2 checklist."""
    h.approve(env.log, CASE, h.G1, ["antecedents"], "h:0a1b")
    _clean_gate2_case(env.log, CASE)
    st = env.guard.status(CASE, G2)
    assert (st.unresolved_needs_review, st.unresolved_unanswered) == ([], [])


def test_gate2_approve_succeeds_for_a_clean_brief_and_records_event(env):
    """With everything resolved, Gate 2 approval is recorded as a GATE_APPROVED event for GATE_2_EXPORT."""
    h.approve(env.log, CASE, h.G1, ["antecedents"], "h:0a1b")
    _clean_gate2_case(env.log, CASE)
    env.guard.approve(CASE, G2)
    approvals = env.log.read(CASE, kind=EventKind.GATE_APPROVED)
    assert [a.inputs["gate"] for a in approvals] == ["GATE_1_DOSSIER", "GATE_2_EXPORT"]
    assert approvals[-1].actor == "counsel"


# ---------------------------------------------------------------------------------------------------------------------
# export guard
# ---------------------------------------------------------------------------------------------------------------------
def test_export_refused_with_no_approval(env):
    """assert_export_allowed raises before any approval."""
    with pytest.raises(REFUSED):
        env.guard.assert_export_allowed(CASE)


def test_export_refused_after_gate_1_only(env2):
    """Gate 1 approval alone never unlocks export (plan §16: export only after Gate 2)."""
    with pytest.raises(REFUSED):
        env2.guard.assert_export_allowed(CASE)


def test_export_allowed_after_gate_2_approval(env):
    """After Gate 2 is approved for the case, assert_export_allowed returns without raising."""
    h.approve(env.log, CASE, h.G1, ["antecedents"], "h:0a1b")
    _clean_gate2_case(env.log, CASE)
    h.approve(env.log, CASE, h.G2)
    assert env.guard.assert_export_allowed(CASE) is None


def test_approval_of_case_a_does_not_allow_export_of_case_b(env, dossier):
    """No cross-case or bulk export: Gate 2 of case-0007 does not unlock case-0008, even with Gate 1 approved."""
    h.approve(env.log, CASE, h.G1, ["antecedents"], "h:0a1b")
    _clean_gate2_case(env.log, CASE)
    h.approve(env.log, CASE, h.G2)
    h.seed_dossier(env.log, CASE_B, h.resolved_dossier(dossier).model_copy(update={"case_id": CASE_B}))
    h.approve(env.log, CASE_B, h.G1, [], "h:0a1b")
    env.guard.assert_export_allowed(CASE)
    with pytest.raises(REFUSED):
        env.guard.assert_export_allowed(CASE_B)


def test_export_refused_for_unknown_case(env):
    """A case with no record at all cannot export."""
    with pytest.raises(REFUSED):
        env.guard.assert_export_allowed("case-9999")
