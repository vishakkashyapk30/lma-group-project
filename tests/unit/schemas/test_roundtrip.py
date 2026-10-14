"""JSON round-trip of every schema (plan §3.3, §4.6, §6.3, §7.1, §7.3, §8.1, §9, §10, §11, §13.5, §5.1).

Each model must survive model_dump_json -> model_validate_json and model_dump(mode='json') -> model_validate unchanged,
and the plan's printed example payloads must validate as written."""

from __future__ import annotations

import json


from tests.unit.schemas import _helpers as H
from vakeel_sahayak.schemas import (
    BailBrief,
    CaseDossier,
    Event,
    IngestionReport,
    RetrievalPlan,
    SparringRecord,
    TriageCard,
)
from vakeel_sahayak.schemas.case import BudgetState, CaseSummary, GateStatus
from vakeel_sahayak.schemas.change_set import ChangeSet, FieldChange
from vakeel_sahayak.schemas.chat import ChatMessage, ToolChip
from vakeel_sahayak.schemas.common import SourceRef, TrackedField
from vakeel_sahayak.schemas.enums import (
    AgentName,
    ClaimCheck,
    ClaimState,
    ConcordanceEdgeType,
    DocumentType,
    EventKind,
    Factor,
    FactorStance,
    FieldStatus,
    GateId,
    OrderPart,
    SlotStatus,
    Stage,
    StoreName,
    Treatment,
)
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack, SlotResult
from vakeel_sahayak.schemas.store_rows import (
    CaseChunk,
    CitationEdge,
    ConcordanceEdge,
    FactSignature,
    ParagraphRecord,
    SimilarOrderRow,
    StatuteRow,
)


def assert_roundtrip(obj):
    """Both JSON text and plain-dict round trips reproduce an equal model."""
    cls = type(obj)
    assert cls.model_validate_json(obj.model_dump_json()) == obj
    assert cls.model_validate(json.loads(json.dumps(obj.model_dump(mode="json")))) == obj


def test_case_dossier_roundtrip_and_status_fidelity(dossier):
    """case-0007 CaseDossier round-trips and keeps every field's status, value and source (plan §7.1)."""
    assert_roundtrip(dossier)
    again = CaseDossier.model_validate_json(dossier.model_dump_json())
    assert again.fields.arrest_date.value == "2024-08-20"
    assert again.fields.custody_days.status is FieldStatus.COMPUTED
    assert again.fields.antecedents.status is FieldStatus.UNSUPPORTED
    assert again.fields.fir.source.quote_en == "FIR No. 112/2024 dated 14.08.2024"
    assert again.fields.fir.source.box == [64, 120, 540, 152]


def test_dossier_enum_serialises_as_plain_string(dossier):
    """Statuses appear in the JSON as the plain strings the plan prints."""
    data = json.loads(dossier.model_dump_json())
    assert data["fields"]["arrest_date"]["status"] == "VERIFIED"
    assert data["fields"]["personal"]["status"] == "USER_STATED"
    assert data["fields"]["custody_days"]["source"]["tool"] == "date_calc"


def test_rights_report_roundtrip_and_fixture_matches_plan(expected_rights_report, case_meta):
    """RightsReport of plan §7.3 round-trips; seven checks with the statuses of case-0007."""
    assert_roundtrip(expected_rights_report)
    got = {c.check.value: c.status.value for c in expected_rights_report.checks}
    assert got == case_meta["expected"]["rights_statuses"]
    assert len(expected_rights_report.checks) == 7


def test_bail_brief_roundtrip_with_grounds_and_depends_on():
    """BailBrief of plan §8.1 (grounds, authorities, depends_on, open issues) round-trips unchanged."""
    brief = BailBrief.model_validate(H.BAIL_BRIEF)
    assert_roundtrip(brief)
    g1, g2 = brief.grounds
    assert g1.factor is Factor.PARITY_WITH_CO_ACCUSED
    assert g1.depends_on.facts == {"co_accused_bail": "h:3f2a", "sections": "h:91c0"}
    assert g1.depends_on.authorities == ["DLHC-2022-1187#14"]
    assert g1.authorities[0].para == 14
    assert g2.depends_on.claims == ["G1"]
    assert (g1.check, g1.state) == (ClaimCheck.SUPPORTED, ClaimState.CURRENT)
    assert (g2.check, g2.state) == (ClaimCheck.REPAIRED, ClaimState.STALE)
    assert [i.type.value for i in brief.open_issues] == ["NEEDS_REVIEW", "CHANGED_PROVISION", "MISSING_EVIDENCE"]


def test_bail_brief_dump_matches_plan_json_keys():
    """BailBrief JSON keeps the plan's keys (so stored briefs stay readable by the frontend types)."""
    data = json.loads(BailBrief.model_validate(H.BAIL_BRIEF).model_dump_json())
    assert set(data) == {"case_id", "statutory_position", "grounds", "open_issues", "label"}
    assert set(data["grounds"][0]) == {
        "id", "factor", "stance", "argument", "authorities", "depends_on", "check", "state"
    }
    assert set(data["grounds"][0]["depends_on"]) == {"facts", "events", "rights", "authorities", "claims"}
    assert set(data["grounds"][0]["authorities"][0]) == {
        "doc_id", "para", "citation", "transfer", "good_law", "sc_root"
    }


def test_sparring_record_roundtrip():
    """SparringRecord of plan §9 round-trips with verdicts, grounds and the discarded log."""
    rec = SparringRecord.model_validate(H.SPARRING_RECORD)
    assert_roundtrip(rec)
    o1, o2 = rec.objections
    assert o1.verdict.value == "ANSWERED" and o1.reply.check is ClaimCheck.SUPPORTED
    assert o1.grounds[0].store == "advocacy.objections" and o1.grounds[0].para == 6
    assert o1.grounds[1].fact == "fir"
    assert o2.reply is None and o2.verdict.value == "UNANSWERED" and o2.against == "general"
    assert rec.discarded == ["Applicant is a flight risk (no grounding found)"]


def test_triage_card_roundtrip():
    """TriageCard of plan §11 round-trips."""
    card = TriageCard.model_validate(H.TRIAGE_CARD)
    assert_roundtrip(card)
    assert card.urgency_rank == 4 and card.missing_docs == ["custody certificate"]


def test_ingestion_report_roundtrip_matches_plan_4_6():
    """IngestionReport of plan §4.6 round-trips with routes, statuses and filed counts."""
    rep = IngestionReport.model_validate(H.INGESTION_REPORT)
    assert_roundtrip(rep)
    d1, d2 = rep.documents
    assert d1.type is DocumentType.FIR and d1.pages == [1, 3] and d1.type_confidence == 0.94
    assert [p.status.value for p in d1.page_routes] == ["OK", "OK", "UNREADABLE"]
    assert d1.page_routes[2].ocr_conf is None
    assert d1.page_routes[0].route[0] == "text_layer: rejected (legacy font)"
    assert d2.type is DocumentType.REMAND_ORDER
    assert rep.filed.model_dump() == {"timeline_events": 6, "parties": 4, "sections": 2, "chunks": 31}
    assert len(rep.questions) == 2


def test_retrieval_plan_roundtrip_with_budget_left():
    """RetrievalPlan of plan §6.3 round-trips, including budget_left and '$slot.field' references."""
    plan = RetrievalPlan.model_validate(H.RETRIEVAL_PLAN)
    assert_roundtrip(plan)
    assert plan.budget_left.store_calls == 6 and plan.budget_left.tokens == 9000
    assert plan.factor is Factor.PARITY_WITH_CO_ACCUSED and plan.round == 1
    assert [s.tool for s in plan.steps] == ["search_case_docs", "search_reasoning", "citations", "search_objections"]
    assert plan.steps[2].args["doc_ids"] == "$authority.top3"
    assert plan.steps[1].args["before"] == "2025-02-03"
    assert plan.assessment["authority"] == "WEAK (1 of 2)"
    assert plan.next.startswith("relax section_family")


def test_evidence_pack_roundtrip():
    """EvidencePack (Sutradhar -> Vakeel, plan §6.2 step 3) round-trips."""
    pack = EvidencePack(
        factor=Factor.CHARGE_SHEET_FILED,
        stance=FactorStance.FAVOURABLE,
        reason="charge sheet filed 2024-11-02",
        slots=[SlotResult(slot="authority", status=SlotStatus.WEAK, items=[{"doc_id": "DLHC-2022-1187", "para": 14}],
                          note="1 of 2")],
        open_issues=["No trial-delay authority in the same section family"],
    )
    assert_roundtrip(pack)


def test_event_roundtrip_for_every_fixture_event(sample_events):
    """Every event of the case-0007 log round-trips (plan §3.3)."""
    assert len(sample_events) == 17
    for ev in sample_events:
        assert_roundtrip(ev)


def test_event_actor_accepts_agent_or_counsel(sample_events):
    """Actor is an AgentName for agent events and the plain string 'counsel' for counsel events."""
    by_id = {e.event_id: e for e in sample_events}
    assert by_id["ev001"].actor == AgentName.MUNSHI
    assert by_id["ev011"].actor == "counsel"
    assert by_id["ev011"].kind is EventKind.GATE_APPROVED


def test_event_with_sources_roundtrip():
    """An event carrying SourceRef list and parent link round-trips."""
    ev = Event(
        event_id="ev100", case_id="case-0007", ts="2025-02-03T10:00:00Z", kind=EventKind.STORE_WRITE,
        actor=AgentName.PESHKAR, tool="extract_dossier", inputs={"store": "case.facts", "field": "arrest_date"},
        outputs={"tracked": {"value": "2024-08-20", "status": "VERIFIED"}},
        sources=[SourceRef(doc="d2 (remand order)", page=4, lang="en", route="text_layer", quote="...arrested...")],
        parent_id="ev003",
    )
    assert_roundtrip(ev)


def test_change_set_roundtrip():
    """ChangeSet (plan §7.4, §10) round-trips with field hashes."""
    cs = ChangeSet(
        case_id="case-0007", trigger="new_document",
        fields=[FieldChange(field="charge_sheet", old_hash="h:0000", new_hash="h:77aa")],
        new_event_ids=["e6"], rights_changed=["default_bail"],
    )
    assert_roundtrip(cs)


def test_chat_message_roundtrip():
    """ChatMessage with tool/store chips and the refusal flag round-trips (plan §6.4, §13.5)."""
    msg = ChatMessage(
        message_id="m1", case_id="case-0007", role="agent", agent=AgentName.SUTRADHAR,
        text="167 days (Day 1 = 21.08.2024).",
        chips=[ToolChip(tool="date_calc"), ToolChip(tool="get_timeline", store=StoreName.CASE_TIMELINE)],
        refused=False,
    )
    assert_roundtrip(msg)
    refusal = ChatMessage(message_id="m2", case_id="case-0007", role="agent", text="I cannot predict outcomes.",
                          refused=True)
    assert_roundtrip(refusal)
    assert json.loads(msg.model_dump_json())["chips"][1]["store"] == "case.timeline"


def test_case_view_models_roundtrip():
    """CaseSummary, GateStatus and BudgetState (plan §13.5) round-trip."""
    assert_roundtrip(CaseSummary(case_id="case-0007", title="State v. Accused-1", stage=Stage.RIGHTS,
                                 rights_chips=["default_bail: WINDOW_CLOSED"], needs_attention=2))
    assert_roundtrip(GateStatus(gate=GateId.GATE_1_DOSSIER, open=True, unresolved_unsupported=["antecedents"]))
    assert_roundtrip(BudgetState(tokens_spent=1200, store_calls={"parity_with_co_accused": 3}))


def test_store_rows_roundtrip(statutes, concordance_edges, paragraphs, timeline):
    """Store row types (plan §5) round-trip: fixture statutes, concordance edges, paragraphs, timeline, and constructed rows."""
    for group in (statutes, concordance_edges, paragraphs, timeline):
        assert group, "fixture is non-empty"
        for row in group:
            assert_roundtrip(row)
    assert_roundtrip(CitationEdge(citing_doc_id="DLHC-2022-1187", cited_doc_id="SC-2014-0463",
                                  treatment=Treatment.RELIED_ON, court_level="HC", sentence="relied upon"))
    assert_roundtrip(SimilarOrderRow(doc_id="DLHC-2022-1187", court="Delhi HC", date="2022-06-03",
                                     signature=FactSignature(sections=["IPC 420"], custody_band="3-6 months",
                                                             charge_sheet_status="filed",
                                                             co_accused_outcome="granted")))
    assert_roundtrip(CaseChunk(chunk_id="c1", doc_id="d2", doc_type=DocumentType.REMAND_ORDER, page=4,
                               box=[10.0, 20.0, 300.0, 40.0], text="...arrested on 20.08.2024...",
                               text_en=None))
    assert_roundtrip(StatuteRow(code="BNS", section="318(4)", text="Whoever cheats ...", max_punishment="7 years",
                                bailable=False, cognisable=True))
    assert_roundtrip(ConcordanceEdge(old_ref="IPC 420", new_ref="BNS 318(4)", type=ConcordanceEdgeType.REWORDED,
                                     text_diff="- cheats\n+ cheats"))


def test_tracked_field_generic_roundtrip():
    """TrackedField[int] keeps value, status and tool source through JSON."""
    tf = TrackedField[int](value=167, source=SourceRef(tool="date_calc"), status=FieldStatus.COMPUTED)
    assert_roundtrip(tf)


def test_empty_dossier_roundtrip():
    """A dossier with nothing filed (all defaults) round-trips."""
    assert_roundtrip(CaseDossier(case_id="case-9999"))


def test_order_part_in_paragraph_serialises_as_plan_string():
    """ParagraphRecord.part serialises as the plan's 'reasoning' / 'defense_submissions' strings."""
    row = ParagraphRecord(doc_id="X", para=1, court="Delhi HC", date="2022-01-01", part=OrderPart.DEFENSE)
    assert json.loads(row.model_dump_json())["part"] == "defense_submissions"
