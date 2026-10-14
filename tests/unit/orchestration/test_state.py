"""orchestration/state.CaseGraphState: typed graph state (plan §3.3, §13.5)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.enums import GateId, Stage


def test_defaults_start_at_intake_with_no_gate_pending():
    """A new case starts in INTAKE with no artefacts and no pending gate."""
    s = CaseGraphState(case_id="case-0007")
    assert s.stage == Stage.INTAKE
    assert s.pending_gate is None
    for name in ("ingestion", "dossier", "rights", "brief", "sparring", "pending_change_set"):
        assert getattr(s, name) is None, name


def test_case_id_is_required():
    """case_id has no default."""
    with pytest.raises(ValidationError):
        CaseGraphState()


def test_state_carries_dossier_and_pending_gate(dossier):
    """The state holds the typed dossier and a GateId; JSON round-trip preserves them."""
    s = CaseGraphState(case_id="case-0007", stage=Stage.DOSSIER, dossier=dossier, pending_gate=GateId.GATE_1_DOSSIER)
    again = CaseGraphState.model_validate_json(s.model_dump_json())
    assert again == s
    assert again.pending_gate is GateId.GATE_1_DOSSIER
    assert again.dossier.fields.custody_days.value == 167


def test_invalid_stage_and_gate_rejected():
    """Only Stage and GateId values are accepted."""
    with pytest.raises(ValidationError):
        CaseGraphState(case_id="c", stage="EXPORTED")
    with pytest.raises(ValidationError):
        CaseGraphState(case_id="c", pending_gate="GATE_3")


def test_two_gates_exist():
    """The system has exactly two approval gates: dossier and export (plan §3.1)."""
    assert [g.value for g in GateId] == ["GATE_1_DOSSIER", "GATE_2_EXPORT"]
