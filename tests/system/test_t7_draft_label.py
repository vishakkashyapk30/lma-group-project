"""T7 safety (plan §8.1, §8.2, §16): every output that counsel could file or hand on carries the label "AI-generated draft. Not legal advice."

Outputs checked: the brief (view and API tab), the hearing-prep card (agent output and API tab), the exported application DOCX (label and the
banner "AI-generated draft: check against your court's rules"), the brief after an incremental redraft, and the brief of a batch case. The label is a
property of the output, not of the model's text: it is there even when the scripted drafter leaves it out and it cannot be dropped by a
change set.

Real modules: VakeelAgent (brief and card), `redraft_incrementally`, the cases and export routes, `export_case`. Fakes: models, stores, tools
(`Scenario`); the DOCX tests need python-docx.

ASSUMPTIONS: the hearing card dict has a `label` key (tests/unit/export/test_hearing_card.py); the label is not part of any scripted ground.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fakes.data import build_world
from tests.fakes.models import FakeNli
from tests.system import _helpers as sh
from tests.unit.export._helpers import docx_text
from vakeel_sahayak.export.hearing_card import build_hearing_card
from vakeel_sahayak.record.case_state import CaseState
from vakeel_sahayak.schemas.change_set import ChangeSet, FieldChange
from vakeel_sahayak.schemas.enums import AgentName, EventKind, Factor
from vakeel_sahayak.truth_maintenance.redraft import redraft_incrementally

pytestmark = pytest.mark.system

CASE = sh.CASE_ID
G2 = sh.G2
LABEL = "AI-generated draft. Not legal advice."


def drafted(tmp_path, monkeypatch, **kw) -> sh.Scenario:
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages(), **kw)
    sc.through_gate1()
    sc.through_draft()
    return sc


def test_the_scripted_drafter_never_writes_the_label_itself():
    """Guard against a vacuous pass: none of the scripted grounds contains the label, so it must come from the output."""
    assert all("not legal advice" not in g.argument.lower() for g in sh.GROUNDS.values())


def test_the_drafted_brief_carries_the_label(tmp_path, monkeypatch):
    sc = drafted(tmp_path, monkeypatch)
    assert sc.state.brief.label == LABEL and CaseState(CASE, sc.log).brief().label == LABEL


def test_the_brief_tab_carries_the_label(tmp_path, monkeypatch):
    body = drafted(tmp_path, monkeypatch).client().get(f"/api/cases/{CASE}/brief").json()
    assert body["label"] == LABEL


def test_the_hearing_card_carries_the_label(tmp_path, monkeypatch):
    sc = drafted(tmp_path, monkeypatch)
    assert "AI-generated draft" in build_hearing_card(sc.state.brief, sc.state.sparring, CASE)["label"]
    assert "AI-generated draft" in sc.client().get(f"/api/cases/{CASE}/prep").json()["label"]


def test_vakeels_own_hearing_card_carries_the_label(tmp_path, monkeypatch):
    sc = drafted(tmp_path, monkeypatch)
    assert "AI-generated draft" in sc.agent(AgentName.VAKEEL).build_hearing_card(sc.state)["label"]


def test_the_exported_application_carries_the_label_and_the_banner(tmp_path, monkeypatch):
    """Needs python-docx: the label of the brief and the banner of plan §8.2 are in the file counsel files."""
    pytest.importorskip("docx")
    sc = drafted(tmp_path, monkeypatch)
    sc.clear_and_approve(G2)
    paths = [Path(p) for p in sc.client().post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).json()]
    text = docx_text(next(p for p in paths if "application" in p.name.lower()))
    assert LABEL in text and "check against your court's rules" in text


def test_every_exported_document_names_itself_a_draft(tmp_path, monkeypatch):
    """Needs python-docx: the objections sheet and the List of Dates are DOCX files too and say 'AI-generated draft'."""
    pytest.importorskip("docx")
    sc = drafted(tmp_path, monkeypatch)
    sc.clear_and_approve(G2)
    paths = [Path(p) for p in sc.client().post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).json()]
    docx_paths = [p for p in paths if p.suffix == ".docx"]
    assert docx_paths
    assert all("ai-generated draft" in docx_text(p).lower() for p in docx_paths)


def test_a_redrafted_brief_keeps_the_label(tmp_path, monkeypatch):
    """The label survives an incremental redraft (plan §10): it is on the new brief, not only on the first one."""
    ada = sh.ada_client(grounds=("G1",), extra_grounds=[sh.ground("G2", Factor.CHARGE_SHEET_FILED, sh.G2_ARGUMENT_UNFILED)], redraft=sh.GROUNDS["G2"])
    sc = drafted(tmp_path, monkeypatch, ada=ada)
    sc._patch_everywhere("get_nli", lambda: FakeNli())
    sc.toolbox.pending_change = ChangeSet(case_id=CASE, trigger="new_document", fields=[FieldChange(field="charge_sheet", old_hash="h:0", new_hash="h:1")],
                                          rights_changed=["default_bail"])
    change = sc.agent(AgentName.PESHKAR).detect_changes(sc.state)
    assert redraft_incrementally(sc.state, change).label == LABEL


def test_a_batch_brief_carries_the_label(tmp_path, monkeypatch):
    """Briefs made overnight by the desk are drafts too."""
    cases = sh.build_batch(n=6, planted_indexes=(3, 5), planted_days_left=(3, 1))
    sc = sh.Scenario(tmp_path, monkeypatch, toolbox=sh.BatchToolbox(build_world(), cases), ada=sh.ada_client())
    files = []
    for c in cases:
        f = sc.data_dir / "batch" / f"{c.case_id}.pdf"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"%PDF-1.4\n% stub\n")
        files.append(str(f))
    agent = sc.agent(AgentName.PAIROKAR)
    done = agent.stage2(agent.decide_next_steps(agent.stage1(files)), 10_000.0)
    assert done and all(CaseState(c, sc.log).brief().label == LABEL for c in done)


def test_the_label_is_a_property_of_the_output_not_of_a_model_call(tmp_path, monkeypatch):
    """The label appears with no model call at all: a brief assembled from the record has it (nothing was asked of Ada here)."""
    sc = sh.Scenario(tmp_path, monkeypatch)
    sc.seed_record(brief=sh.clean_brief(CASE), sparring=sh.clean_sparring(CASE))
    assert CaseState(CASE, sc.log).brief().label == LABEL and sc.ada.calls == []
    assert sc.events(EventKind.TOOL_CALL) == []
