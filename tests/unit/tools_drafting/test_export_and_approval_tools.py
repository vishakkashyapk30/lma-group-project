"""`export`, `request_approval` and `assemble_application` (plan §3.1, §8.1, §8.2, §16).

`export` is the only gated tool: it works only after Gate 2 of THIS case, enforced in code through `GateGuard.assert_export_allowed`; there
is no bulk export (each case needs its own approval, plan §11, §16). `request_approval` opens a gate with its checklist and never approves
(approval is counsel's act). `assemble_application` fills the DOCX template and is not an export.

The guard and the writers are replaced by recording stand-ins, so what is under test is the tool's wiring: guard first, one case, one format.
# SKELETON-GAP: how the tool reaches the guard (a `GateGuard()` it builds, or one from the context) is not specified; the stand-in replaces
# `GateGuard.assert_export_allowed` / `status` / `approve` on the class, which covers both. Refusals raise PermissionError or ValueError, or return a ToolError.
"""

from __future__ import annotations

import pytest

from tests.unit.pipelines._helpers import patch_everywhere
from tests.unit.tools_case._helpers import assert_tool_error
from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.schemas.case import GateStatus
from vakeel_sahayak.schemas.enums import AgentName, ExportFormat, GateId
from vakeel_sahayak.tools.drafting.application import ASSEMBLE_APPLICATION_SPEC, assemble_application
from vakeel_sahayak.tools.drafting.approval import REQUEST_APPROVAL_SPEC, request_approval
from vakeel_sahayak.tools.drafting.export_tool import EXPORT_SPEC, export
from vakeel_sahayak.tools.types import ApprovalRequest

CASE = "case-0007"
G1, G2 = GateId.GATE_1_DOSSIER, GateId.GATE_2_EXPORT


class Rig:
    """Gate 2 approved only for `approved_cases`; records guard checks, exports, approvals."""

    def __init__(self, monkeypatch, approved_cases=(CASE,), status: GateStatus | None = None) -> None:
        self.approved_cases = set(approved_cases)
        self.guard_checks: list[str] = []
        self.exports: list[tuple[str, ExportFormat]] = []
        self.approvals: list[tuple[str, GateId]] = []
        self.status = status

        def assert_export_allowed(guard, case_id):
            self.guard_checks.append(case_id)
            if case_id not in self.approved_cases:
                raise PermissionError(f"Gate 2 not approved for {case_id}")

        def status_fn(guard, case_id, gate):
            return self.status or GateStatus(gate=gate, open=False)

        def approve(guard, case_id, gate, acknowledged=None):
            self.approvals.append((case_id, gate))

        def export_case(case_id, format):
            self.exports.append((case_id, ExportFormat(format)))
            return [f"/data/{case_id}/application.docx", f"/data/{case_id}/hearing_card.docx"]

        monkeypatch.setattr(GateGuard, "assert_export_allowed", assert_export_allowed)
        monkeypatch.setattr(GateGuard, "status", status_fn)
        monkeypatch.setattr(GateGuard, "approve", approve)
        patch_everywhere(monkeypatch, "vakeel_sahayak.export.exporter", "export_case", export_case)


# ---------------------------------------------------------------- export
def test_export_before_gate_2_is_refused_and_writes_nothing(monkeypatch):
    rig = Rig(monkeypatch, approved_cases=())
    with pytest.raises((PermissionError, ValueError)):
        export(CASE, ExportFormat.DOCX)
    assert rig.guard_checks == [CASE] and rig.exports == []


def test_export_after_gate_2_returns_the_exported_files(monkeypatch):
    rig = Rig(monkeypatch)
    paths = export(CASE, ExportFormat.DOCX)
    assert paths == [f"/data/{CASE}/application.docx", f"/data/{CASE}/hearing_card.docx"]
    assert rig.exports == [(CASE, ExportFormat.DOCX)] and rig.guard_checks == [CASE]


def test_the_guard_runs_before_any_writer(monkeypatch):
    """Order of events: assert_export_allowed first, then the exporter (a refusal never leaves a partial export)."""
    order: list[str] = []
    rig = Rig(monkeypatch)
    original = GateGuard.assert_export_allowed

    def tracked(guard, case_id):
        order.append("guard")
        return original(guard, case_id)

    monkeypatch.setattr(GateGuard, "assert_export_allowed", tracked)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.exporter", "export_case", lambda c, f: order.append("export") or ["x.docx"])
    export(CASE, ExportFormat.PDF)
    assert order == ["guard", "export"] and rig.exports == []


def test_approval_of_one_case_never_exports_another(monkeypatch):
    """No bulk export: Gate 2 of case-0007 does not let case-0008 through, and the guard is asked about exactly the requested case."""
    rig = Rig(monkeypatch, approved_cases=(CASE,))
    with pytest.raises((PermissionError, ValueError)):
        export("case-0008", ExportFormat.DOCX)
    assert rig.guard_checks == ["case-0008"] and rig.exports == []
    export(CASE, ExportFormat.DOCX)
    assert [c for c, _ in rig.exports] == [CASE]


@pytest.mark.parametrize("case_id", ["", "*", "all", "case-0007,case-0008", ["case-0007", "case-0008"]])
def test_bulk_or_empty_case_ids_are_refused_even_when_a_gate_is_approved(monkeypatch, case_id):
    """Argument validation: exactly one case id. Wildcards, lists and comma-joined ids are refused before the guard or exporter run."""
    rig = Rig(monkeypatch, approved_cases=(CASE, "case-0008", "*", "all"))
    assert_tool_error(lambda: export(case_id, ExportFormat.DOCX))
    assert rig.exports == []


@pytest.mark.parametrize("fmt", ["DOCX", "PDF", ExportFormat.DOCX, ExportFormat.PDF])
def test_export_accepts_both_formats(monkeypatch, fmt):
    rig = Rig(monkeypatch)
    export(CASE, fmt)
    assert rig.exports == [(CASE, ExportFormat(fmt))]


@pytest.mark.parametrize("fmt", ["ZIP", "", None, "docx; rm -rf /"])
def test_unknown_formats_are_refused_before_the_guard(monkeypatch, fmt):
    rig = Rig(monkeypatch)
    assert_tool_error(lambda: export(CASE, fmt))
    assert rig.exports == []


def test_gate_1_approval_alone_does_not_unlock_export(monkeypatch):
    """The guard is asked for Gate 2 specifically (assert_export_allowed), never satisfied by an approved Gate 1."""
    rig = Rig(monkeypatch, approved_cases=())
    rig.approvals.append((CASE, G1))  # Gate 1 approved in some earlier step: the stand-in guard still refuses
    with pytest.raises((PermissionError, ValueError)):
        export(CASE, ExportFormat.DOCX)


def test_export_is_gated_vakeel_only_and_the_only_gated_tool():
    assert EXPORT_SPEC.gated is True and EXPORT_SPEC.agents == [AgentName.VAKEEL]
    for spec in (ASSEMBLE_APPLICATION_SPEC, REQUEST_APPROVAL_SPEC):
        assert spec.gated is False


# ---------------------------------------------------------------- request_approval
def test_request_approval_lists_the_open_checklist_items(monkeypatch):
    """Gate 1 with the case-0007 checklist (antecedents UNSUPPORTED): the request names the gate and the unresolved item."""
    rig = Rig(monkeypatch, status=GateStatus(gate=G1, open=False, unresolved_unsupported=["antecedents"]))
    res = request_approval(CASE, G1)
    assert isinstance(res, ApprovalRequest) and res.gate == G1
    assert res.checklist_open is True and res.unresolved == ["antecedents"]
    assert rig.approvals == []


def test_request_approval_never_approves(monkeypatch):
    """Approval is counsel's act (plan §3.1: gates are graph interrupts): the tool only opens the gate, for either gate."""
    rig = Rig(monkeypatch)
    for gate in (G1, G2):
        request_approval(CASE, gate)
    assert rig.approvals == []


def test_request_approval_for_gate_2_lists_needs_review_and_unanswered(monkeypatch):
    Rig(monkeypatch, status=GateStatus(gate=G2, open=False, unresolved_needs_review=["G3"], unresolved_unanswered=["O3"]))
    res = request_approval(CASE, G2)
    assert res.gate == G2 and sorted(res.unresolved) == ["G3", "O3"]


@pytest.mark.parametrize("args", [("", G1), (CASE, "GATE_3"), (CASE, None)])
def test_request_approval_rejects_bad_arguments(monkeypatch, args):
    Rig(monkeypatch)
    assert_tool_error(lambda: request_approval(*args))


def test_request_approval_is_for_vakeel_and_peshkar():
    assert set(REQUEST_APPROVAL_SPEC.agents) == {AgentName.VAKEEL, AgentName.PESHKAR}


# ---------------------------------------------------------------- assemble_application
def test_assemble_application_builds_the_docx_but_does_not_export(monkeypatch, tmp_path):
    """Assembling a draft is not exporting: no gate check and no exporter call; the result is the path of a DOCX.
    # SKELETON-GAP: the tool's data sources (brief, dossier, timeline from the case record) are not given as arguments."""
    rig = Rig(monkeypatch, approved_cases=())
    out = tmp_path / "application.docx"
    out.write_bytes(b"PK")
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.application", "assemble_application_docx", lambda *a, **k: str(out))
    path = assemble_application(CASE)
    assert isinstance(path, str) and path.endswith(".docx")
    assert rig.guard_checks == [] and rig.exports == []


@pytest.mark.parametrize("case_id", ["", "*"])
def test_assemble_application_rejects_empty_or_wildcard_case_ids(monkeypatch, case_id):
    Rig(monkeypatch)
    assert_tool_error(lambda: assemble_application(case_id))


def test_assemble_application_is_vakeel_only_with_no_store_of_its_own():
    assert ASSEMBLE_APPLICATION_SPEC.agents == [AgentName.VAKEEL] and ASSEMBLE_APPLICATION_SPEC.stores == []

