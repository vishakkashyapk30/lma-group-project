"""Enumerations equal the plan exactly (plan §3.1-3.3, §4.1-4.3, §5.1-5.4, §6.2, §7.1, §7.3, §8.1, §9, §13.5,
Appendices A and C). Config-level: these must pass against the skeleton today."""

from __future__ import annotations

from enum import Enum

import pytest

from vakeel_sahayak.schemas import enums as E


def values(enum_cls: type[Enum]) -> list[str]:
    return [m.value for m in enum_cls]


@pytest.mark.parametrize(
    ("enum_cls", "expected"),
    [
        # plan §7.1 statuses
        (E.FieldStatus, {"VERIFIED", "COMPUTED", "UNSUPPORTED", "AMBIGUOUS", "USER_STATED", "USER_EDITED"}),
        # plan §6.2 step 2.3
        (E.SlotStatus, {"FILLED", "WEAK", "MISSING"}),
        # plan §10
        (E.ClaimState, {"CURRENT", "STALE"}),
        # plan §8.1 step 4 / BailBrief example
        (E.ClaimCheck, {"SUPPORTED", "REPAIRED", "NEEDS_REVIEW"}),
        # plan §9 round 2
        (E.SparringVerdict, {"ANSWERED", "PARTLY", "UNANSWERED"}),
        # plan §5.4
        (E.TransferFlag, {"SAME_TEXT", "CHANGED", "NEW"}),
        # plan §5.1 (typed same / split / merged / reworded / new)
        (E.ConcordanceEdgeType, {"SAME", "SPLIT", "MERGED", "REWORDED", "NEW"}),
        # plan §8.1 open_issues example
        (E.OpenIssueType, {"NEEDS_REVIEW", "CHANGED_PROVISION", "MISSING_EVIDENCE"}),
        # plan §3.1 gates
        (E.GateId, {"GATE_1_DOSSIER", "GATE_2_EXPORT"}),
        # plan §5.3: followed, relied on, distinguished, overruled, referred, plus "treatment unknown"
        (E.Treatment, {"FOLLOWED", "RELIED_ON", "DISTINGUISHED", "OVERRULED", "REFERRED", "UNKNOWN"}),
        # plan §5.3 good-law check: overruled blocks, distinguished is shown but does not block
        # ASSUMPTION: OK and UNKNOWN complete the flag set (no flag yet / not enough information)
        (E.GoodLawStatus, {"OK", "OVERRULED", "DISTINGUISHED", "UNKNOWN"}),
        # plan §6.2 step 1: favourable, adverse, not applicable
        (E.FactorStance, {"favourable", "adverse", "not_applicable"}),
        # plan §4.6 page status
        (E.PageStatus, {"OK", "UNREADABLE"}),
    ],
)
def test_enum_value_set_equals_plan(enum_cls, expected):
    """The enum's value set is exactly the set named in the plan."""
    assert set(values(enum_cls)) == expected
    assert len(values(enum_cls)) == len(expected), "no duplicate or aliased members"


def test_rights_status_covers_every_rights_radar_output():
    """RightsStatus is the union of every status in the plan §7.3 table (including Antil A-D and BAR_APPLIES)."""
    plan_outputs = {
        "ELIGIBLE", "NOT_YET", "WINDOW_CLOSED", "CHECK",  # default bail
        "NOT_APPLICABLE",  # undertrial limit, statutory bar
        "FLAG", "OK", "UNKNOWN",  # notice / grounds / production
        "A", "B", "C", "D",  # Antil category
        "BAR_APPLIES",  # statutory bar
    }
    assert set(values(E.RightsStatus)) == plan_outputs


def test_rights_check_name_has_the_seven_checks_in_plan_order():
    """The seven checks of plan §7.3 / Appendix C, in table order."""
    assert values(E.RightsCheckName) == [
        "default_bail",
        "undertrial_limit",
        "notice_of_appearance",
        "grounds_of_arrest",
        "production_24h",
        "antil_category",
        "statutory_bar",
    ]


def test_factor_has_the_twelve_appendix_a_factors_in_order():
    """Factor members follow Appendix A numbering 1..12 (values are contract file stems)."""
    assert values(E.Factor) == [
        "gravity_and_punishment",  # 1
        "custody_period",  # 2
        "charge_sheet_filed",  # 3
        "trial_delay",  # 4
        "parity_with_co_accused",  # 5
        "antecedents",  # 6
        "flight_risk",  # 7
        "witness_tampering",  # 8
        "weak_prima_facie",  # 9
        "health_age_family",  # 10
        "statutory_bar",  # 11
        "undertrial_period",  # 12
    ]


def test_factor_names_plan_mentions_explicitly_are_present():
    """The three factor ids the plan names verbatim exist (plan §6.1, §10, §6.2)."""
    for name in ("parity_with_co_accused", "charge_sheet_filed", "witness_tampering"):
        assert name in values(E.Factor)


def test_factor_values_are_contract_file_stems(contracts_dir):
    """Every Factor value is the stem of exactly one contract YAML and vice versa."""
    stems = {p.stem for p in contracts_dir.glob("*.yaml")}
    assert stems == set(values(E.Factor))


def test_store_name_is_the_ten_stores():
    """StoreName lists the ten dotted store names of plan §5.1."""
    assert set(values(E.StoreName)) == {
        "law.statutes",
        "law.concordance",
        "caselaw.reasoning",
        "caselaw.citations",
        "caselaw.similar",
        "advocacy.arguments",
        "advocacy.objections",
        "case.docs",
        "case.timeline",
        "case.facts",
    }
    assert len(E.StoreName) == 10


def test_shelf_is_the_four_shelves():
    """Four shelves: law, caselaw, advocacy, case (plan §5.1)."""
    assert set(values(E.Shelf)) == {"law", "caselaw", "advocacy", "case"}


@pytest.mark.parametrize(
    ("store", "shelf"),
    [
        (E.StoreName.LAW_STATUTES, E.Shelf.LAW),
        (E.StoreName.LAW_CONCORDANCE, E.Shelf.LAW),
        (E.StoreName.CASELAW_REASONING, E.Shelf.CASELAW),
        (E.StoreName.CASELAW_CITATIONS, E.Shelf.CASELAW),
        (E.StoreName.CASELAW_SIMILAR, E.Shelf.CASELAW),
        (E.StoreName.ADVOCACY_ARGUMENTS, E.Shelf.ADVOCACY),
        (E.StoreName.ADVOCACY_OBJECTIONS, E.Shelf.ADVOCACY),
        (E.StoreName.CASE_DOCS, E.Shelf.CASE),
        (E.StoreName.CASE_TIMELINE, E.Shelf.CASE),
        (E.StoreName.CASE_FACTS, E.Shelf.CASE),
    ],
)
def test_store_name_prefix_is_its_shelf(store, shelf):
    """A store's dotted-name prefix is its shelf, matching the plan §5.1 table (2+3+2+3 stores)."""
    assert store.value.split(".")[0] == shelf.value


def test_agent_name_is_the_six_agents():
    """Six agents of plan §3.2."""
    assert set(values(E.AgentName)) == {"MUNSHI", "PESHKAR", "SUTRADHAR", "VAKEEL", "ABHIYOJAK", "PAIROKAR"}
    assert len(E.AgentName) == 6


def test_gate_id_has_exactly_two_gates():
    """Gate 1 (dossier) and Gate 2 (export) only (plan §3.1)."""
    assert len(E.GateId) == 2


def test_stage_is_seven_stages_in_order():
    """Workspace stages I-VII in order (plan §13.5)."""
    assert values(E.Stage) == ["INTAKE", "DOSSIER", "RIGHTS", "BRIEF", "SPAR", "HEARING_PREP", "FILE"]


def test_document_type_includes_every_munshi_label():
    """Munshi's ten labels of plan §4.3 step 2 are all present (and nothing else)."""
    assert set(values(E.DocumentType)) == {
        "FIR",
        "ARREST_MEMO",
        "REMAND_ORDER",
        "BAIL_ORDER",
        "ORDER_SHEET",
        "CHARGE_SHEET_COVER",
        "CUSTODY_CERTIFICATE",
        "MEDICAL_RECORD",
        "AFFIDAVIT",
        "OTHER",
    }


def test_input_kind_is_k1_to_k10_in_order():
    """Input kinds K1..K10 of plan §4.1, in order."""
    members = values(E.InputKind)
    assert len(members) == 10
    assert [m.split("_")[0] for m in members] == [f"K{i}" for i in range(1, 11)]


@pytest.mark.parametrize(
    ("member", "kind_no"),
    [
        (E.InputKind.K1_BORN_DIGITAL, 1),
        (E.InputKind.K2_SCANNED, 2),
        (E.InputKind.K3_DEGRADED, 3),
        (E.InputKind.K4_PHONE_PHOTO, 4),
        (E.InputKind.K5_HINDI_MIXED, 5),
        (E.InputKind.K6_LEGACY_HINDI_FONT, 6),
        (E.InputKind.K7_HANDWRITING, 7),
        (E.InputKind.K8_BUNDLE, 8),
        (E.InputKind.K9_LOCKED_OR_BROKEN, 9),
        (E.InputKind.K10_NOT_PDF, 10),
    ],
)
def test_input_kind_number_matches_plan_table(member, kind_no):
    """Each K-number maps to the plan §4.1 row of that number."""
    assert member.value.startswith(f"K{kind_no}_")


def test_parse_route_is_the_five_rungs():
    """The routing ladder has five rungs, cheapest first (plan §4.2)."""
    assert values(E.ParseRoute) == ["text_layer", "layout", "ocr", "vision", "ask_counsel"]


def test_order_part_is_the_five_parts():
    """An order has five parts (plan §5.2)."""
    assert values(E.OrderPart) == [
        "facts",
        "defense_submissions",
        "prosecution_submissions",
        "reasoning",
        "operative_order",
    ]


def test_info_kind_is_the_six_paragraph_tags():
    """Paragraph tags of plan §4.3 step 2."""
    assert set(values(E.InfoKind)) == {
        "dated_event",
        "party",
        "section",
        "earlier_outcome",
        "custody",
        "personal_circumstance",
    }


def test_event_kind_covers_plan_and_fixture_kinds():
    """EventKind covers the event kinds the plan (§3.3, §6.2, §10, §3.1) and the case-0007 log use."""
    needed = {
        "TOOL_CALL", "TOOL_RESULT", "AGENT_MESSAGE", "STORE_WRITE",
        "GATE_OPENED", "GATE_APPROVED",  # two approval gates (plan §3.1)
        "BUDGET_HIT",  # "every time a budget is hit it is logged" (plan §6.2)
        "CHANGE_SET_APPROVED", "CLAIM_STALED",  # plan §10
        "ERROR",
    }
    assert needed <= set(values(E.EventKind))


def test_event_kind_has_gate_rejection_and_user_action():
    """Counsel can reject a gate or act directly in the UI (ASSUMPTION: GATE_REJECTED and USER_ACTION kinds, plan §3.1, §13.5)."""
    assert {"GATE_REJECTED", "USER_ACTION"} <= set(values(E.EventKind))


def test_export_format_is_docx_and_pdf():
    """Exports are DOCX and PDF (plan §8.2, §13.1)."""
    assert set(values(E.ExportFormat)) == {"DOCX", "PDF"}


def test_doc_lang_codes():
    """Document languages: English, Hindi, mixed (plan §4.5)."""
    assert set(values(E.DocLang)) == {"en", "hi", "mixed"}


@pytest.mark.parametrize("enum_cls", [c for c in vars(E).values() if isinstance(c, type) and issubclass(c, Enum) and c is not Enum])
def test_every_enum_is_a_str_enum_with_unique_values(enum_cls):
    """Enums are str-valued so they serialise to plain JSON strings and compare equal to their values."""
    assert issubclass(enum_cls, str)
    first = next(iter(enum_cls))
    assert first == first.value
    assert len({m.value for m in enum_cls}) == len(list(enum_cls))
