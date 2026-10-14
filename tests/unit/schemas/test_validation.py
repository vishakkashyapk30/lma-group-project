"""Required fields, invalid enum values, defaults and budgets of the schemas (plan §4.6, §5.2, §6.2, §7.1, §8.1, §9, §11).

Config/schema-level: passes against the skeleton today."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from tests.unit.schemas import _helpers as H
from vakeel_sahayak.config import BudgetConfig
from vakeel_sahayak.schemas import (
    BailBrief,
    CaseDossier,
    Event,
    IngestionReport,
    RetrievalPlan,
    RightsReport,
    SparringRecord,
    TriageCard,
)
from vakeel_sahayak.schemas.bail_brief import Authority, Ground
from vakeel_sahayak.schemas.case import BudgetState
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.chat import ChatMessage
from vakeel_sahayak.schemas.dossier import DossierFields, SectionValue
from vakeel_sahayak.schemas.enums import (
    ClaimCheck,
    ClaimState,
    FieldStatus,
    OrderPart,
)
from vakeel_sahayak.schemas.retrieval_plan import BudgetLeft, PlanStep
from vakeel_sahayak.schemas.rights_report import RightsCheckResult
from vakeel_sahayak.schemas.store_rows import CaseChunk, ConcordanceEdge, ParagraphRecord, StatuteRow, TimelineEvent

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures"


# ----------------------------------------------------------------------------------------------------------------
# Required fields
# ----------------------------------------------------------------------------------------------------------------
REQUIRED = [
    (CaseDossier, {"case_id": "c"}, "case_id"),
    (BailBrief, {"case_id": "c"}, "case_id"),
    (SparringRecord, {"case_id": "c"}, "case_id"),
    (TriageCard, {"case_id": "c", "urgency_rank": 1}, "case_id"),
    (TriageCard, {"case_id": "c", "urgency_rank": 1}, "urgency_rank"),
    (IngestionReport, {"case_id": "c", "file": "f.pdf"}, "case_id"),
    (IngestionReport, {"case_id": "c", "file": "f.pdf"}, "file"),
    (RightsReport, {"case_id": "c", "as_of": "2025-02-03"}, "case_id"),
    (RightsReport, {"case_id": "c", "as_of": "2025-02-03"}, "as_of"),
    (
        RetrievalPlan,
        {"factor": "trial_delay", "budget_left": {"store_calls": 8, "tokens": 12000}},
        "factor",
    ),
    (
        RetrievalPlan,
        {"factor": "trial_delay", "budget_left": {"store_calls": 8, "tokens": 12000}},
        "budget_left",
    ),
    (
        Event,
        {"event_id": "e", "case_id": "c", "ts": "2025-02-03T09:00:00Z", "kind": "TOOL_CALL", "actor": "MUNSHI"},
        "event_id",
    ),
    (
        Event,
        {"event_id": "e", "case_id": "c", "ts": "2025-02-03T09:00:00Z", "kind": "TOOL_CALL", "actor": "MUNSHI"},
        "kind",
    ),
    (
        Event,
        {"event_id": "e", "case_id": "c", "ts": "2025-02-03T09:00:00Z", "kind": "TOOL_CALL", "actor": "MUNSHI"},
        "actor",
    ),
    (ChangeSet, {"case_id": "c", "trigger": "new_document"}, "trigger"),
    (
        ChatMessage,
        {"message_id": "m", "case_id": "c", "role": "counsel", "text": "hi"},
        "text",
    ),
    (
        Authority,
        {"doc_id": "DLHC-2022-1187", "para": 14},
        "doc_id",
    ),
    (
        Authority,
        {"doc_id": "DLHC-2022-1187", "para": 14},
        "para",
    ),
    (
        Ground,
        {"id": "G1", "factor": "trial_delay", "stance": "favourable", "argument": "x"},
        "argument",
    ),
    (
        Ground,
        {"id": "G1", "factor": "trial_delay", "stance": "favourable", "argument": "x"},
        "factor",
    ),
    (
        SectionValue,
        {"as_written": "318(4) BNS", "code": "BNS", "section": "318(4)"},
        "as_written",
    ),
    (
        ParagraphRecord,
        {"doc_id": "D", "para": 1, "court": "Delhi HC", "date": "2022-01-01", "part": "reasoning"},
        "part",
    ),
    (
        ParagraphRecord,
        {"doc_id": "D", "para": 1, "court": "Delhi HC", "date": "2022-01-01", "part": "reasoning"},
        "doc_id",
    ),
    (StatuteRow, {"code": "BNS", "section": "318(4)", "text": "t"}, "text"),
    (ConcordanceEdge, {"old_ref": "IPC 420", "new_ref": "BNS 318(4)", "type": "SAME"}, "type"),
    (
        CaseChunk,
        {"chunk_id": "c1", "doc_id": "d2", "doc_type": "FIR", "page": 1, "text": "t"},
        "page",
    ),
    (TimelineEvent, {"event_id": "e1", "date": "2024-08-20", "label": "Arrest"}, "date"),
]


@pytest.mark.parametrize(("model", "valid", "missing"), REQUIRED, ids=lambda x: x if isinstance(x, str) else None)
def test_missing_required_field_raises_validation_error(model: type[BaseModel], valid: dict, missing: str):
    """Dropping a required field raises pydantic.ValidationError that names the field; the full payload is valid."""
    model.model_validate(valid)
    broken = {k: v for k, v in valid.items() if k != missing}
    with pytest.raises(ValidationError) as exc:
        model.model_validate(broken)
    assert missing in {str(err["loc"][0]) for err in exc.value.errors()}


def test_missing_required_nested_field_in_plan_example_is_rejected():
    """A SourceRef-free ingestion page without its page number is rejected at depth (plan §4.6)."""
    data = copy.deepcopy(H.INGESTION_REPORT)
    del data["documents"][0]["page_routes"][0]["page"]
    with pytest.raises(ValidationError):
        IngestionReport.model_validate(data)


def test_missing_budget_left_in_plan_example_is_rejected():
    """RetrievalPlan without budget_left is invalid (plan §6.3 includes it in every plan)."""
    data = copy.deepcopy(H.RETRIEVAL_PLAN)
    del data["budget_left"]
    with pytest.raises(ValidationError):
        RetrievalPlan.model_validate(data)


def test_budget_left_requires_both_numbers():
    """BudgetLeft needs store_calls and tokens."""
    with pytest.raises(ValidationError):
        BudgetLeft.model_validate({"store_calls": 6})
    with pytest.raises(ValidationError):
        PlanStep.model_validate({"slot": "authority"})


# ----------------------------------------------------------------------------------------------------------------
# Invalid enum values
# ----------------------------------------------------------------------------------------------------------------
def _bad(data: dict, path: list, value) -> dict:
    data = copy.deepcopy(data)
    ref = data
    for p in path[:-1]:
        ref = ref[p]
    ref[path[-1]] = value
    return data


INVALID_ENUMS = [
    (BailBrief, H.BAIL_BRIEF, ["grounds", 0, "factor"], "not_a_factor"),
    (BailBrief, H.BAIL_BRIEF, ["grounds", 0, "check"], "MAYBE"),
    (BailBrief, H.BAIL_BRIEF, ["grounds", 0, "state"], "FRESH"),
    (BailBrief, H.BAIL_BRIEF, ["grounds", 0, "stance"], "neutral"),
    (BailBrief, H.BAIL_BRIEF, ["grounds", 0, "authorities", 0, "transfer"], "PARTIAL"),
    (BailBrief, H.BAIL_BRIEF, ["grounds", 0, "authorities", 0, "good_law"], "GOOD"),
    (BailBrief, H.BAIL_BRIEF, ["open_issues", 0, "type"], "INFO"),
    (SparringRecord, H.SPARRING_RECORD, ["objections", 0, "verdict"], "ANSWERD"),
    (SparringRecord, H.SPARRING_RECORD, ["objections", 0, "reply", "check"], "OK"),
    (IngestionReport, H.INGESTION_REPORT, ["documents", 0, "type"], "SUMMONS"),
    (IngestionReport, H.INGESTION_REPORT, ["documents", 0, "page_routes", 0, "status"], "PARTIAL"),
    (RetrievalPlan, H.RETRIEVAL_PLAN, ["factor"], "bail_amount"),
]


@pytest.mark.parametrize(("model", "base", "path", "value"), INVALID_ENUMS, ids=lambda x: str(x)[:30])
def test_invalid_enum_value_rejected(model, base, path, value):
    """An enum field given a value outside the plan's set raises ValidationError; the unmodified payload is valid."""
    model.model_validate(base)
    with pytest.raises(ValidationError):
        model.model_validate(_bad(base, path, value))


def test_invalid_field_status_in_dossier_rejected():
    """A dossier field with a status outside the six plan statuses is rejected (plan §7.1)."""
    data = json.loads((FIXTURE_DIR / "case_0007" / "dossier.json").read_text(encoding="utf-8"))
    data["fields"]["arrest_date"]["status"] = "CONFIRMED"
    with pytest.raises(ValidationError):
        CaseDossier.model_validate(data)


def test_invalid_rights_status_and_check_name_rejected():
    """RightsCheckResult rejects an unknown check name or status (plan §7.3)."""
    RightsCheckResult.model_validate({"check": "default_bail", "status": "ELIGIBLE"})
    with pytest.raises(ValidationError):
        RightsCheckResult.model_validate({"check": "default_bail", "status": "MAYBE"})
    with pytest.raises(ValidationError):
        RightsCheckResult.model_validate({"check": "bail_amount", "status": "ELIGIBLE"})


def test_invalid_event_kind_and_stage_rejected():
    """Event.kind and CaseSummary.stage reject values outside their enums."""
    base = {"event_id": "e", "case_id": "c", "ts": "2025-02-03T09:00:00Z", "actor": "MUNSHI"}
    Event.model_validate({**base, "kind": "TOOL_CALL"})
    with pytest.raises(ValidationError):
        Event.model_validate({**base, "kind": "TOOL_CALLED"})
    from vakeel_sahayak.schemas.case import CaseSummary

    with pytest.raises(ValidationError):
        CaseSummary.model_validate({"case_id": "c", "title": "t", "stage": "ARCHIVE"})


def test_invalid_order_part_rejected():
    """ParagraphRecord.part must be one of the five order parts (plan §5.2)."""
    with pytest.raises(ValidationError):
        ParagraphRecord.model_validate(
            {"doc_id": "D", "para": 1, "court": "Delhi HC", "date": "2022-01-01", "part": "judgment"}
        )


def test_wrong_type_for_int_field_rejected():
    """A non-numeric page or para is a validation error rather than silently coerced."""
    with pytest.raises(ValidationError):
        Authority.model_validate({"doc_id": "X", "para": "fourteen"})


# ----------------------------------------------------------------------------------------------------------------
# Defaults
# ----------------------------------------------------------------------------------------------------------------
def test_bail_brief_default_label_is_the_plan_disclaimer():
    """BailBrief.label defaults to 'AI-generated draft. Not legal advice.' (plan §8.1)."""
    assert BailBrief(case_id="c").label == "AI-generated draft. Not legal advice."


def test_bail_brief_defaults_are_empty_and_independent():
    """A new BailBrief has no grounds or issues and instances do not share mutable defaults."""
    a, b = BailBrief(case_id="a"), BailBrief(case_id="b")
    assert a.grounds == [] and a.open_issues == []
    a.grounds.append(
        Ground(id="G1", factor="trial_delay", stance="favourable", argument="x")  # type: ignore[arg-type]
    )
    assert b.grounds == []
    assert a.statutory_position is not b.statutory_position


def test_ground_defaults_start_needs_review_and_current():
    """A fresh Ground is NEEDS_REVIEW until the checker passes it, and CURRENT (plan §8.1 step 4, §10)."""
    g = Ground(id="G9", factor="trial_delay", stance="adverse", argument="x")  # type: ignore[arg-type]
    assert g.check is ClaimCheck.NEEDS_REVIEW
    assert g.state is ClaimState.CURRENT
    assert g.authorities == []
    assert g.depends_on.facts == {} and g.depends_on.claims == []


def test_authority_default_good_law_is_unknown():
    """An authority with no good-law check yet is UNKNOWN, never OK by default (plan §5.3)."""
    a = Authority(doc_id="DLHC-2022-1187", para=14)
    assert a.good_law.value == "UNKNOWN"
    assert a.transfer is None and a.citation is None and a.sc_root is None


def test_empty_dossier_tracked_fields_default_unsupported():
    """Every tracked dossier field is UNSUPPORTED, value None and source None until filled (plan §7.1)."""
    fields = CaseDossier(case_id="c").fields
    names = list(DossierFields.model_fields)
    assert names == [
        "fir", "offence_date", "sections", "arrest_date", "first_remand", "custody_days", "charge_sheet",
        "trial_stage", "previous_bail", "co_accused_bail", "antecedents", "personal", "parties",
    ]
    for name in names:
        tracked = getattr(fields, name)
        assert tracked.status is FieldStatus.UNSUPPORTED, name
        assert tracked.value is None and tracked.source is None, name


def test_dossier_has_no_bnss_479_field():
    """bnss_479 moved to the RightsReport (plan §7.1)."""
    assert "bnss_479" not in DossierFields.model_fields


def test_dossier_fields_do_not_share_default_instances():
    """Two empty dossiers do not share TrackedField objects."""
    a, b = CaseDossier(case_id="a"), CaseDossier(case_id="b")
    assert a.fields.fir is not b.fields.fir
    assert a.open_questions is not b.open_questions


def test_dossier_status_default_is_unsupported_for_loaded_null_field(dossier):
    """The fixture's antecedents field (value null, source null) is UNSUPPORTED, as in the plan example."""
    assert dossier.fields.antecedents.value is None
    assert dossier.fields.antecedents.status is FieldStatus.UNSUPPORTED
    assert dossier.open_questions == ["Does the accused have any other pending cases?"]


def test_triage_card_defaults():
    """TriageCard lists default empty and next_step None."""
    c = TriageCard(case_id="c", urgency_rank=1)
    assert (c.reasons, c.flags, c.missing_docs, c.next_step) == ([], [], [], None)


def test_retrieval_plan_defaults():
    """RetrievalPlan starts at round 1 with no steps, no assessment and no 'next' (plan §6.3)."""
    p = RetrievalPlan(factor="trial_delay", budget_left=BudgetLeft(store_calls=8, tokens=12000))  # type: ignore[arg-type]
    assert p.round == 1 and p.steps == [] and p.assessment == {} and p.next is None


def test_chat_message_defaults_not_refused():
    """A chat message is not a refusal by default (plan §6.4)."""
    m = ChatMessage(message_id="m", case_id="c", role="counsel", text="How many days in custody?")
    assert m.refused is False and m.chips == [] and m.agent is None


def test_sparring_record_defaults_zero_rounds():
    """A fresh SparringRecord has 0 rounds, no objections, nothing discarded (plan §9)."""
    r = SparringRecord(case_id="c")
    assert (r.rounds, r.objections, r.discarded) == (0, [], [])


def test_change_set_defaults_empty_means_no_op():
    """A ChangeSet with no fields, events or rights is the no-op change set (plan §10, T3 control)."""
    cs = ChangeSet(case_id="c", trigger="clock")
    assert cs.fields == [] and cs.new_event_ids == [] and cs.rights_changed == []


def test_timeline_event_default_status_verified_and_no_conflicts():
    """Timeline events start VERIFIED with no conflicts (plan §7.2)."""
    e = TimelineEvent(event_id="e1", date="2024-08-20", label="Arrest")
    assert e.status is FieldStatus.VERIFIED and e.conflicts_with == []


def test_budget_state_defaults():
    """BudgetState starts at 0 spent against the 150,000-token case cap (plan §6.2)."""
    s = BudgetState()
    assert s.tokens_spent == 0 and s.tokens_cap == 150000 and s.store_calls == {}


def test_budget_config_defaults_match_plan():
    """BudgetConfig defaults: 150K tokens/case, 8 store calls and 12K tokens per factor, 3 questions, 2+2 rounds, 2 objections (plan §4.3, §6.2, §8.1, §9)."""
    b = BudgetConfig()
    assert b.tokens_per_case == 150000
    assert b.store_calls_per_factor == 8
    assert b.tokens_per_factor == 12000
    assert b.questions_per_round == 3
    assert b.repair_rounds == 2
    assert b.sparring_rounds == 2
    assert b.objections_per_ground == 2


def test_budget_state_and_config_cap_agree():
    """The UI's token cap equals the configured per-case budget."""
    assert BudgetState().tokens_cap == BudgetConfig().tokens_per_case


# ----------------------------------------------------------------------------------------------------------------
# ParagraphRecord matches the plan §5.2 metadata JSON
# ----------------------------------------------------------------------------------------------------------------
PARAGRAPH_JSON = {
    "doc_id": "DLHC-2022-1187", "para": 14, "court": "Delhi HC", "date": "2022-06-03", "outcome": "granted",
    "part": "reasoning",
    "sections": ["IPC 420", "IPC 406"], "section_family": ["IPC 420", "BNS 318(4)", "IPC 406", "BNS 316(2)"],
    "factors": ["parity_with_co_accused", "charge_sheet_filed"],
    "cites": ["SC-2014-0463"], "authority": 0.71, "text": "...",
}


def test_paragraph_record_accepts_plan_5_2_json_and_dumps_same_keys():
    """The plan §5.2 paragraph JSON validates and dumps back to exactly the same keys and values."""
    rec = ParagraphRecord.model_validate(PARAGRAPH_JSON)
    assert rec.part is OrderPart.REASONING
    assert [f.value for f in rec.factors] == ["parity_with_co_accused", "charge_sheet_filed"]
    assert rec.authority == 0.71 and rec.cites == ["SC-2014-0463"]
    assert json.loads(rec.model_dump_json()) == PARAGRAPH_JSON


def test_paragraph_record_field_set_is_the_plan_metadata():
    """ParagraphRecord has exactly the plan §5.2 metadata keys, nothing more."""
    assert set(ParagraphRecord.model_fields) == set(PARAGRAPH_JSON)


def test_paragraph_record_defaults():
    """Optional metadata defaults: no outcome, empty lists, authority 0.0, empty text."""
    r = ParagraphRecord(doc_id="D", para=2, court="Delhi HC", date="2022-01-01", part=OrderPart.FACTS)
    assert r.outcome is None and r.sections == [] and r.section_family == [] and r.factors == []
    assert r.cites == [] and r.authority == 0.0 and r.text == ""


def test_paragraph_factors_must_be_known_factors():
    """A paragraph tagged with a factor outside Appendix A is rejected."""
    with pytest.raises(ValidationError):
        ParagraphRecord.model_validate({**PARAGRAPH_JSON, "factors": ["parity_with_co_accused", "bail_amount"]})
