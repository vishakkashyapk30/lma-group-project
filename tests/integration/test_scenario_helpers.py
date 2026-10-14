"""Self-check of the integration scenario helpers (fakes only, so these pass today; plan §4.6, §6.3, §9).

They guard the inputs the other integration tests build on: a wrong bundle or plan script would make every
scenario fail for the wrong reason.
"""

from __future__ import annotations

import json

import pytest

from tests.fakes.data import PLANTED_NAMES, PLANTED_NAMES_HI
from tests.integration import _helpers as h
from vakeel_sahayak.schemas.enums import DocumentType, Factor, StoreName
from vakeel_sahayak.schemas.retrieval_plan import RetrievalPlan


def test_bundle_has_14_pages_with_the_planned_shape():
    """Plan §13.6 flow 1: 14 pages; FIR 1-3 scanned, p2 handwriting, p3 unreadable; two remand orders; bail rejection."""
    pages = h.build_bundle()
    assert len(pages) == 14
    assert [p.signals.has_text_layer for p in pages[:3]] == [False, False, False]
    assert pages[0].ocr_conf == 0.81 and pages[1].signals.handwriting_detected
    assert pages[2].vision_text == "" and pages[2].ocr_conf < 0.3
    assert all(p.signals.has_text_layer for p in pages[3:])
    assert [b[:2] for b in h.BUNDLE_BOUNDARIES] == [(1, 3), (4, 5), (6, 7), (8, 14)]
    assert "arrested on 20.08.2024" in pages[3].text and "remanded to judicial custody on 21.08.2024" in pages[3].text
    assert "30.09.2024" in pages[12].text and "Charge sheet filed on 02.11.2024. Charges not framed." in pages[13].text


def test_bundle_plants_names_in_text_and_the_conflict_variant_changes_only_the_second_order():
    """Names are planted in English and Devanagari pages; the conflict variant only changes page 6."""
    plain, conflict = h.build_bundle(), h.build_bundle("22.08.2024")
    alltext = " ".join(p.text for p in plain)
    assert all(n in alltext for n in (PLANTED_NAMES[0], PLANTED_NAMES[1], PLANTED_NAMES[2], PLANTED_NAMES[3]))
    assert PLANTED_NAMES_HI[0] in alltext
    diff = [i + 1 for i, (a, b) in enumerate(zip(plain, conflict)) if a.text != b.text]
    assert diff == [6] and "arrested on 22.08.2024" in conflict[5].text


def test_scenario_toolbox_split_pseudonymise_and_span_check_fakes():
    """The fake back-ends: explicit boundaries, Hindi alias table, and the lenient NLI over dd.mm.yyyy quotes."""
    tb = h.ScenarioToolbox(h.fresh_case_world(), h.build_bundle(), boundaries=h.BUNDLE_BOUNDARIES)
    docs = tb.tools["split_bundle"]("bundle_1.pdf")
    assert [(d.doc_id, d.type, d.pages) for d in docs] == [
        ("d1", DocumentType.FIR, [1, 3]), ("d2", DocumentType.REMAND_ORDER, [4, 5]),
        ("d3", DocumentType.REMAND_ORDER, [6, 7]), ("d4", DocumentType.BAIL_ORDER, [8, 14]),
    ]
    out = tb.tools["pseudonymise"](f"{h.NAME_ACCUSED} and {h.HI_ACCUSED}", "case-0007")
    assert out == "Accused-1 and Accused-1"
    ok = tb.tools["span_check"]("2024-08-20", "...arrested on 20.08.2024...")
    bad = tb.tools["span_check"]("2024-08-22", "...arrested on 20.08.2024...")
    assert ok.supported and not bad.supported


def test_extractor_fake_reads_the_charge_sheet_from_the_shelf():
    """The fake extractor derives charge_sheet from the timeline shelf; antecedents never; personal only from chat."""
    from vakeel_sahayak.schemas.common import SourceRef

    tb = h.ScenarioToolbox(h.fresh_case_world(), h.build_bundle())
    d0 = tb.tools["extract_dossier"]("case-0007")
    assert d0.fields.charge_sheet.value.filed is False
    assert d0.fields.antecedents.value is None and d0.fields.personal.value is None
    tb.tools["file_item"](StoreName.CASE_TIMELINE, {"event_id": "e6", "date": "2024-11-02", "label": "Charge sheet filed"},
                          SourceRef(doc="d4", page=14))
    d1 = tb.tools["extract_dossier"]("case-0007")
    assert d1.fields.charge_sheet.value.filed is True and d1.fields.charge_sheet.value.date == "2024-11-02"
    tb2 = h.ScenarioToolbox(h.fresh_case_world(), chat_facts=["sole earning member"])
    assert tb2.tools["extract_dossier"]("case-0007").fields.personal.source.chat == "turn 3"


@pytest.mark.parametrize("factor", list(Factor))
def test_contract_steps_use_only_slots_and_stores_of_the_contract(factor):
    """Scripted plans cover every slot of the factor's contract and nothing else (plan §6.1)."""
    steps = h.contract_steps(factor)
    assert [s["slot"] for s in steps] == h.contract_slots(factor)
    assert all(s["tool"] and isinstance(s["args"], dict) for s in steps)


def test_plan_responder_returns_a_valid_retrieval_plan_for_the_factor_in_the_prompt():
    """The scripted plan validates against the RetrievalPlan schema and follows the factor named in the prompt."""
    raw = h.plan_responder()("Plan retrieval for charge_sheet_filed now", {"title": "RetrievalPlan"})
    plan = RetrievalPlan.model_validate(raw)
    assert plan.factor == Factor.CHARGE_SHEET_FILED
    assert {s.slot for s in plan.steps} == set(h.contract_slots(Factor.CHARGE_SHEET_FILED))


def test_dispatch_routes_titles_by_keyword_and_records_unrouted():
    """Schema titles route by keyword; unknown titles answer '{}' and are recorded, free text uses the 'free' handler."""
    llm = h.make_llm(plan="PLAN", objections="OBJ", judge="JUDGE", free="TEXT")
    assert llm.generate("p", json_schema={"title": "RetrievalPlan"}) == "PLAN"
    assert llm.generate("p", json_schema={"title": "ObjectionList"}) == "OBJ"
    assert llm.generate("p", json_schema={"title": "VerdictsRound2"}) == "JUDGE"
    assert llm.generate("plain prompt") == "TEXT"
    assert llm.generate("p", json_schema={"title": "Mystery"}) == "{}"
    assert llm.dispatch.unrouted == ["Mystery"]
    assert [h.kind_of_call(c) for c in llm.calls] == ["plan", "objections", "judge", "free", "other"]


def test_fat_responses_carry_the_payload_under_every_wrapper_key():
    """A fat JSON answer validates against any wrapper that uses one of the documented keys."""
    raw = json.loads(h.make_llm(objections=h.objections_responder()).generate("x", json_schema={"title": "Objections"}))
    assert [o["id"] for o in raw["objections"]] == [o["id"] for o in raw["items"]] == ["O1", "O2", "O3", "O4", "O5"]


def test_worlds_are_local_copies_and_keep_the_forbidden_orders_out(world):
    """The extra parity paragraph lives in a local copy; the forbidden orders are in no default store."""
    base = h.case_0007_world()
    extra = h.case_0007_world(second_parity=True)
    assert "DLHC-2020-0777" not in {r.doc_id for r in base.stores[StoreName.CASELAW_REASONING].rows}
    assert "DLHC-2020-0777" in {r.doc_id for r in extra.stores[StoreName.CASELAW_REASONING].rows}
    ids = {r.doc_id for r in extra.stores[StoreName.CASELAW_REASONING].rows}
    assert ids & {"TESTORD-2024-0001", "SAMEFIR-2024-0002"} == set()
    assert h.fresh_case_world().stores[StoreName.CASE_TIMELINE].count() == 0
    assert world.stores[StoreName.CASE_TIMELINE].count() == 7
