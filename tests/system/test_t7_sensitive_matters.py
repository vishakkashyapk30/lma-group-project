"""T7 safety (plan §16 'Sensitive matters'): sexual-offence, POCSO and juvenile matters are declined at intake, by section and by document type.

The law protects the identity of victims and children (BNS s.72, POCSO s.23, JJ Act s.74), so Munshi checks sections and document types, declines,
files nothing, asks no model on Ada, opens no gate, and leaves the case out of the evaluation. Ordinary matters (including near-miss section
numbers) are not declined.

Real modules: MunshiAgent, `privacy.sensitive_matters.is_declined_matter`, PairokarAgent (a declined file in a batch), the draft route, the log.
Fakes: models, page back-ends, stores (`Scenario`, `BatchToolbox`).

ASSUMPTIONS: a decline is an AGENT_MESSAGE with outputs {declined: true, reason, excluded_from_evaluation: true}, the reason names the protecting
provision; Munshi reads sections from the page text; one declined page declines the whole matter. SKELETON-GAP: `DocumentType` has no
juvenile-board-order label, so the decline by document type is exercised through page text (a Juvenile Justice Board order) and, directly, through
`is_declined_matter(..., ["JUVENILE_BOARD_ORDER"])`.
"""

from __future__ import annotations

import json

import pytest

from tests.fakes.data import build_world
from tests.system import _helpers as sh
from tests.system import _scripts as ss
from vakeel_sahayak.privacy.sensitive_matters import is_declined_matter
from vakeel_sahayak.schemas.enums import AgentName, DocumentType, EventKind, Stage, StoreName

pytestmark = pytest.mark.system

CASE = sh.CASE_ID

DECLINED = [
    ("english sexual offence, BNS 64", "FIR No. 55/2024 PS-9 under Section 64 BNS. The accused is alleged to have committed the offence.", "72"),
    ("english sexual offence, IPC 376", "FIR No. 56/2024 PS-9 under Section 376 IPC.", "72"),
    ("POCSO", "FIR No. 57/2024 PS-9 under Section 6 of the POCSO Act.", "23"),
    ("juvenile", "FIR No. 58/2024 PS-9. The accused is a juvenile before the Juvenile Justice Board under the JJ Act 74.", "74"),
    ("hindi sexual offence", "प्रथम सूचना रिपोर्ट सं. 59/2024\nधारा 64 बी.एन.एस.", "72"),
] + [(f"page-{label}", text, provision) for label, text, provision in ss.DECLINED_PAGES]
IDS = [d[0] for d in DECLINED]


def intake(tmp_path, monkeypatch, fir_text: str, lang: str = "en", pages=None):
    pages = pages or [sh.page(fir_text, DocumentType.FIR, new_doc=True, lang=lang)]
    sc = sh.Scenario(tmp_path, monkeypatch, pages=pages, answers=[""] * 3)
    sc.add_upload("bundle_1.pdf")
    before = {name: sc.world.stores[name].count() for name in (StoreName.CASE_DOCS, StoreName.CASE_TIMELINE)}
    sc.run(AgentName.MUNSHI)
    return sc, before


def lang_of(label: str) -> str:
    return "hi" if label.startswith("hindi") else "en"


# ---- declined at intake ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(("label", "text", "provision"), DECLINED, ids=IDS)
def test_sensitive_matters_are_declined_at_intake(tmp_path, monkeypatch, label, text, provision):
    """Munshi declines, naming the protecting provision, files nothing, asks no model on Ada, and the case goes no further."""
    sc, before = intake(tmp_path, monkeypatch, text, lang_of(label))
    declined = sh.declined_events(sc.events())
    assert len(declined) == 1
    assert provision in declined[0].outputs["reason"]
    assert declined[0].outputs["excluded_from_evaluation"] is True
    assert sc.toolbox.count("file_item") == 0
    assert {name: sc.world.stores[name].count() for name in before} == before
    assert sc.ada.calls == [] and sc.state.dossier is None and sc.state.stage == Stage.INTAKE


@pytest.mark.parametrize(("label", "text", "provision"), DECLINED, ids=IDS)
def test_a_declined_matter_opens_no_gate_and_cannot_be_drafted(tmp_path, monkeypatch, label, text, provision):
    sc, _ = intake(tmp_path, monkeypatch, text, lang_of(label))
    assert sc.events(EventKind.GATE_OPENED) == [] and sc.events(EventKind.GATE_APPROVED) == []
    assert sc.client().post(f"/api/cases/{CASE}/draft").status_code >= 400
    assert sc.ada.calls == [] and sc.toolbox.exports == []


@pytest.mark.parametrize(("label", "text", "provision"), DECLINED[:3], ids=IDS[:3])
def test_a_declined_matter_is_not_filed_in_any_store(tmp_path, monkeypatch, label, text, provision):
    sc, _ = intake(tmp_path, monkeypatch, text)
    assert sc.toolbox.count("extract_dossier") == 0 and sc.toolbox.count("rights_check") == 0


def test_one_sensitive_page_declines_the_whole_matter(tmp_path, monkeypatch):
    """A POCSO FIR in the middle of an ordinary bundle declines the matter: nothing of the bundle is filed."""
    pages = sh.messy_bundle_pages() + [sh.page("FIR No. 60/2024 PS-9 under Section 6 of the POCSO Act.", DocumentType.FIR, new_doc=True)]
    sc, before = intake(tmp_path, monkeypatch, "", pages=pages)
    assert len(sh.declined_events(sc.events())) == 1
    assert sc.toolbox.count("file_item") == 0 and {n: sc.world.stores[n].count() for n in before} == before


# ---- controls: ordinary matters are not declined ---------------------------------------------------------------------------
def test_an_ordinary_case_is_not_declined(tmp_path, monkeypatch):
    """Cheating under BNS 318(4) is filed normally (no false declines)."""
    sc, _ = intake(tmp_path, monkeypatch, "FIR No. 112/2024 PS-1 under Section 318(4) BNS. Cheating of Rs. 5 lakh.")
    assert sh.declined_events(sc.events()) == []
    assert sc.toolbox.count("file_item") > 0


@pytest.mark.parametrize("section", ["Section 62 BNS", "Section 164 BNS", "Section 363 IPC", "Section 20 NDPS Act", "Section 303(2) BNS"])
def test_near_miss_section_numbers_are_not_declined(tmp_path, monkeypatch, section):
    sc, _ = intake(tmp_path, monkeypatch, f"FIR No. 61/2024 PS-1 under {section}.")
    assert sh.declined_events(sc.events()) == []


def test_the_messy_bundle_of_flow_1_is_not_declined(tmp_path, monkeypatch):
    sc, _ = intake(tmp_path, monkeypatch, "", pages=sh.messy_bundle_pages())
    assert sh.declined_events(sc.events()) == []


# ---- by document type and by section: the rule itself -----------------------------------------------------------------------
def test_a_juvenile_board_order_is_declined_by_document_type():
    """SKELETON-GAP: `DocumentType` has no such label, so the rule is checked with the label name the plan implies."""
    declined, reason = is_declined_matter(["BNS 318(4)"], ["FIR", "JUVENILE_BOARD_ORDER"])
    assert declined is True and "74" in reason and "JJ Act" in reason


@pytest.mark.parametrize(("section", "provision"), [("BNS 64(2)", "72"), ("IPC 376", "72"), ("POCSO 6", "23"), ("JJ Act 15", "74")])
def test_the_rule_names_the_protecting_provision(section, provision):
    declined, reason = is_declined_matter([section], ["FIR"])
    assert declined is True and provision in reason


# ---- left out of the evaluation -----------------------------------------------------------------------------------------
def test_declined_matters_are_excluded_from_the_evaluation_counts(tmp_path, monkeypatch):
    """The decline event carries the exclusion flag, so the evaluation runners can drop the case (plan §16)."""
    sc, _ = intake(tmp_path, monkeypatch, DECLINED[2][1])
    (event,) = sh.declined_events(sc.events())
    assert json.loads(event.model_dump_json())["outputs"]["excluded_from_evaluation"] is True
    assert event.kind == EventKind.AGENT_MESSAGE


# ---- the batch desk ---------------------------------------------------------------------------------------------------
def test_a_sensitive_file_in_a_batch_is_declined_and_the_others_proceed(tmp_path, monkeypatch):
    """Of eight files, one is a POCSO FIR: it gets no triage card and no queue entry, a decline is logged for it, and the other seven are ranked."""
    cases = sh.build_batch(n=8, planted_indexes=(3, 5), planted_days_left=(3, 1))
    cases[1].pages = ss.declined_bundle(DECLINED[2][1])
    sc = sh.Scenario(tmp_path, monkeypatch, toolbox=sh.BatchToolbox(build_world(), cases), ada=sh.ada_client())
    files = []
    for c in cases:
        f = sc.data_dir / "batch" / f"{c.case_id}.pdf"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"%PDF-1.4\n% stub\n")
        files.append(str(f))
    cards = sc.agent(AgentName.PAIROKAR).stage1(files)
    others = {c.case_id for c in cases} - {cases[1].case_id}
    assert {c.case_id for c in cards} == others
    assert len(sh.declined_events(sc.events(case_id=cases[1].case_id))) == 1
