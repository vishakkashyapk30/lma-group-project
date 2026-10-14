"""User flow 4 (plan §13.6, §7.4, §10, §15.2 T3): the case moves on. The charge sheet is filed, counsel uploads the order, Peshkar highlights
the changed fields, counsel re-approves, and only the affected grounds are redrafted; unchanged claims stay word for word.

Real modules: PeshkarAgent.detect_changes, `mark_stale`, `factors_to_reopen`, SutradharAgent.reopen_after_change, `redraft_incrementally`,
`diff_brief`, GateGuard, the SQLite log. Fakes: models, stores and tools (`Scenario`); the new order's effect is the toolbox's settable
`pending_change` (what `diff_case_state` would return once the order is filed).

The approved brief has G1 (parity) and G2 (charge sheet) where G2 says that no charge sheet has been filed yet; the redraft says it was
filed on 02.11.2024. ASSUMPTIONS: Vakeel fills each ground's `depends_on` (facts with value hashes); re-approval is a second GATE_APPROVED
of Gate 1 whose dossier hash differs from the first (plan §7.4, tests/unit/record/test_case_state.py).
"""

from __future__ import annotations

import pytest

from tests.fakes.models import FakeNli
from tests.system import _helpers as sh
from tests.system import _scripts as ss
from tests.unit.export._helpers import mentions_date
from tests.unit.record._helpers import field_write
from vakeel_sahayak.record.case_state import CaseState
from vakeel_sahayak.schemas.change_set import ChangeSet, FieldChange
from vakeel_sahayak.schemas.common import SourceRef, TrackedField
from vakeel_sahayak.schemas.dossier import ChargeSheetValue
from vakeel_sahayak.schemas.enums import AgentName, ClaimState, DocumentType, EventKind, Factor, FieldStatus
from vakeel_sahayak.truth_maintenance.redraft import diff_brief, redraft_incrementally
from vakeel_sahayak.truth_maintenance.staleness import factors_to_reopen, mark_stale

pytestmark = pytest.mark.system

CASE = sh.CASE_ID
G1, G2 = sh.G1, sh.G2
G2_FILED = sh.GROUNDS["G2"]
G2_UNFILED = sh.ground("G2", Factor.CHARGE_SHEET_FILED, sh.G2_ARGUMENT_UNFILED)
CS_HASHES = {"old_hash": "h:0000", "new_hash": "h:1111"}


def moved_on(tmp_path, monkeypatch, *, noop: bool = False):
    """An approved brief whose G2 says 'not filed'; then counsel uploads the charge-sheet order. Returns (scenario, approved brief)."""
    drafts = {Factor.PARITY_WITH_CO_ACCUSED: sh.GROUNDS["G1"], Factor.CHARGE_SHEET_FILED: G2_UNFILED}
    ada = sh.ada_client()
    ada.by_schema["Ground"] = ss.ground_by_factor(drafts)
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages(), ada=ada)
    sc.through_gate1()
    sc.through_draft()
    sc._patch_everywhere("get_nli", lambda: FakeNli())
    approved = sc.state.brief.model_copy(deep=True)
    drafts[Factor.CHARGE_SHEET_FILED] = G2_FILED  # what the drafter will say once the charge sheet is on record
    sc.toolbox.pages = [sh.page(sh.CHARGE_SHEET_ORDER_TEXT, DocumentType.ORDER_SHEET, new_doc=True)]
    sc.add_upload("order_sheet_2.pdf")
    sc.toolbox.pending_change = (
        ChangeSet(case_id=CASE, trigger="new_document") if noop else
        ChangeSet(case_id=CASE, trigger="new_document", fields=[FieldChange(field="charge_sheet", **CS_HASHES)],
                  rights_changed=["default_bail"]))
    return sc, approved


def by_id(brief) -> dict:
    return {g.id: g for g in brief.grounds}


# ---- the approved starting point ----------------------------------------------------------------------------------------
def test_the_approved_brief_says_no_charge_sheet_yet_and_depends_on_that_field(tmp_path, monkeypatch):
    _, approved = moved_on(tmp_path, monkeypatch)
    g = by_id(approved)
    assert "no charge sheet has been filed" in g["G2"].argument.lower()
    assert "charge_sheet" in g["G2"].depends_on.facts and "charge_sheet" not in g["G1"].depends_on.facts


# ---- steps 1-2: the order arrives, Peshkar highlights, counsel re-approves ------------------------------------------------
def test_peshkar_highlights_the_changed_field_and_the_rights_check(tmp_path, monkeypatch):
    """The order changes `charge_sheet` only, and turns the default-bail check (plan §7.4)."""
    sc, _ = moved_on(tmp_path, monkeypatch)
    change = sc.agent(AgentName.PESHKAR).detect_changes(sc.state)
    assert [f.field for f in change.fields] == ["charge_sheet"] and change.rights_changed == ["default_bail"]
    assert sc.toolbox.count("diff_case_state") == 1


def test_counsel_reapproves_and_the_approved_dossier_hash_moves(tmp_path, monkeypatch):
    """Re-approval is a second counsel GATE_APPROVED of Gate 1 with a new dossier hash; no agent approves (plan §7.4)."""
    sc, _ = moved_on(tmp_path, monkeypatch)
    first = CaseState(CASE, sc.log).approved_dossier_hash()
    new_value = TrackedField[ChargeSheetValue](value=ChargeSheetValue(filed=True, date="2024-11-02"), source=SourceRef(doc="d5 (order sheet)", page=1),
                                               status=FieldStatus.VERIFIED)
    sc.log.append(field_write(CASE, "charge_sheet", new_value, "counsel"))
    sc.clear_and_approve(G1)
    approvals = sc.events(EventKind.GATE_APPROVED)
    assert len(approvals) == 2 and sh.agent_approvals(sc.events()) == []
    assert first is not None and CaseState(CASE, sc.log).approved_dossier_hash() not in (None, first)


# ---- steps 3: only the affected grounds ---------------------------------------------------------------------------------
def test_only_the_ground_that_depends_on_the_charge_sheet_goes_stale(tmp_path, monkeypatch):
    """Plan §10 step 1: G2 depends on `charge_sheet`; G1 does not."""
    sc, approved = moved_on(tmp_path, monkeypatch)
    change = sc.agent(AgentName.PESHKAR).detect_changes(sc.state)
    assert mark_stale(approved, change) == ["G2"]


def test_only_the_charge_sheet_factor_is_reopened(tmp_path, monkeypatch):
    """Plan §10 step 2: 'charge sheet filed -> investigation complete'; parity is not re-planned."""
    sc, approved = moved_on(tmp_path, monkeypatch)
    change = sc.agent(AgentName.PESHKAR).detect_changes(sc.state)
    assert Factor.CHARGE_SHEET_FILED in factors_to_reopen(approved, change)
    reopened = sc.agent(AgentName.SUTRADHAR).reopen_after_change(sc.state, change)
    assert Factor.CHARGE_SHEET_FILED in reopened and Factor.PARITY_WITH_CO_ACCUSED not in reopened


def test_only_the_affected_ground_is_redrafted_and_the_rest_stay_word_for_word(tmp_path, monkeypatch):
    """G2 changes ('filed on 02.11.2024'); G1 is identical to the approved text, dependencies included; one extra drafting call."""
    sc, approved = moved_on(tmp_path, monkeypatch)
    change = sc.agent(AgentName.PESHKAR).detect_changes(sc.state)
    before = len(sc.ada.calls_for("Ground"))
    new = redraft_incrementally(sc.state, change)
    assert len(sc.ada.calls_for("Ground")) - before == 1
    old, cur = by_id(approved), by_id(new)
    assert cur["G1"].model_dump() == old["G1"].model_dump()
    assert cur["G2"].argument != old["G2"].argument and mentions_date(cur["G2"].argument, "2024-11-02")
    assert all(g.state == ClaimState.CURRENT for g in new.grounds)


def test_the_redrafted_ground_depends_on_the_new_value(tmp_path, monkeypatch):
    sc, approved = moved_on(tmp_path, monkeypatch)
    change = sc.agent(AgentName.PESHKAR).detect_changes(sc.state)
    new = redraft_incrementally(sc.state, change)
    assert by_id(new)["G2"].depends_on.facts["charge_sheet"] != by_id(approved)["G2"].depends_on.facts["charge_sheet"]


def test_the_brief_view_highlights_what_changed_and_why(tmp_path, monkeypatch):
    """Plan §10 step 4: one row, for G2, with a reason."""
    sc, approved = moved_on(tmp_path, monkeypatch)
    change = sc.agent(AgentName.PESHKAR).detect_changes(sc.state)
    rows = diff_brief(approved, redraft_incrementally(sc.state, change))
    assert [(r.get("ground_id") or r["id"]) for r in rows] == ["G2"] and rows[0]["reason"].strip()


def test_replanning_is_limited_to_the_reopened_factor(tmp_path, monkeypatch):
    """Sutradhar re-plans only the reopened factor: no retrieval plan after the change mentions another factor."""
    sc, _ = moved_on(tmp_path, monkeypatch)
    change = sc.agent(AgentName.PESHKAR).detect_changes(sc.state)
    plans_before = len(sc.ada.calls_for("RetrievalPlan"))
    redraft_incrementally(sc.state, change)
    new_plans = sc.ada.calls_for("RetrievalPlan")[plans_before:]
    assert all(Factor.PARITY_WITH_CO_ACCUSED.value not in c.prompt for c in new_plans)


# ---- the no-op control ---------------------------------------------------------------------------------------------------
def test_a_duplicate_document_changes_nothing(tmp_path, monkeypatch):
    """T3 control: the same order again is a no-op: empty change set, nothing stale, no model call, brief identical."""
    sc, approved = moved_on(tmp_path, monkeypatch, noop=True)
    change = sc.agent(AgentName.PESHKAR).detect_changes(sc.state)
    assert change.fields == [] and change.rights_changed == [] and mark_stale(approved, change) == []
    before = len(sc.ada.calls)
    new = redraft_incrementally(sc.state, change)
    assert len(sc.ada.calls) == before and new.model_dump() == approved.model_dump()
