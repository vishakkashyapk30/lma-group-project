"""F5 and F6 payloads (plan §15.6): what each arm's `run` measures, checked on case-0007 and small hand-made inputs.

F5 reads the application DOCX back (sections, List of Dates rows and their sources); F6 maps condition texts to the G6 condition types with the
G6 rules and scores G6 only where it applies (a grant).
"""

from __future__ import annotations

import pytest

from tests.unit.export._helpers import make_brief, uploaded_docs
from vakeel_sahayak.eval.features import f5_application as f5
from vakeel_sahayak.eval.features import f6_hearing_card as f6

CASE_0007_DATES = ["2024-08-10", "2024-08-14", "2024-08-20", "2024-08-21", "2024-09-30", "2024-11-02", "2024-12-05"]


def t1_case(g3=None, g5=None, g6=None, g6_applicable=True) -> dict:
    return {"case_id": "c1", "gold": {"G3": {"labels": g3 or []}, "G5": {"labels": g5 or []},
                                      "G6": {"labels": g6 or [], "applicable": g6_applicable}}}  # fmt: skip


def test_gold_dates_are_the_g3_event_labels():
    case = t1_case(g3=["sections=IPC 302", "event=2024-02-16", "event=2023-02-03", "trial_stage=charges_framed_or_trial_started"])
    assert f5.gold_dates(case) == ["2023-02-03", "2024-02-16"]


def test_application_payload_reads_the_docx_of_case_0007(tmp_path, dossier, timeline):
    """All eleven sections carry content; every timeline date is in the List of Dates with its source."""
    pytest.importorskip("docx")
    from vakeel_sahayak.export.application import assemble_application_docx

    path = assemble_application_docx(make_brief(), dossier, timeline, uploaded_docs(), str(tmp_path / "a.docx"))
    payload = f5.application_payload(path, t1_case(g3=["event=2024-08-20", "event=2025-01-01"]))
    assert payload["required_sections_present"] == payload["required_sections_total"] == 11
    assert payload["lod_dates"] == CASE_0007_DATES
    assert payload["dates_total"] == 7 and payload["dates_without_source"] == 0
    assert payload["gold_dates"] == ["2024-08-20", "2025-01-01"]


def test_empty_record_sections_do_not_count_as_present(tmp_path):
    """A case with nothing on record: the List of Dates, brief facts and earlier applications hold only fixed lines or placeholders."""
    pytest.importorskip("docx")
    from vakeel_sahayak.export.application import assemble_application_docx
    from vakeel_sahayak.schemas.bail_brief import BailBrief
    from vakeel_sahayak.schemas.dossier import CaseDossier

    path = assemble_application_docx(BailBrief(case_id="c1"), CaseDossier(case_id="c1"), [], [], str(tmp_path / "a.docx"))
    payload = f5.application_payload(path, t1_case())
    missing = 11 - payload["required_sections_present"]
    assert missing >= 4  # List of Dates, brief facts, earlier applications, grounds, statutory position have nothing of the case
    assert payload["dates_total"] == 0 and payload["lod_dates"] == []


def test_one_call_payload_counts_filled_fields_and_unsourced_dates():
    value = f5.OneCallApplication(
        heading="Application under Section 483 BNSS", synopsis="[APPLICANT] is in custody.", prayer="[COUNSEL]",
        list_of_dates=[f5.OneCallDate(date="20.08.2024", event="Arrest", source="facts, para 2"), f5.OneCallDate(date="2024-11-02", event="Charge sheet"),
                       f5.OneCallDate(date="not a date")],
    )  # fmt: skip
    payload = f5.one_call_payload(value, t1_case(g3=["event=2024-08-20"]))
    assert payload["required_sections_present"] == 3  # heading, synopsis, List of Dates; a prayer that is only a placeholder is missing
    assert payload["lod_dates"] == ["2024-08-20", "2024-11-02"]
    assert payload["dates_total"] == 2 and payload["dates_without_source"] == 1


def test_condition_texts_map_to_g6_types():
    texts = ["Surrender of passport", "Not to leave the city or country without the court's permission", "Personal bond of Rs 50,000",
             "Not to influence witnesses or tamper with evidence", "reporting"]
    assert f6.condition_types(texts) == ["no_contact_witnesses", "no_tamper_evidence", "passport", "personal_bond", "reporting", "travel_restriction"]


def test_card_payload_uses_concern_factors_and_scores_g6_only_for_grants():
    card = {"bench_concerns": [{"factor": "parity_with_co_accused"}, {"factor": "custody_period"}], "conditions": ["Surrender of passport"]}
    grant = f6.card_payload(card, t1_case(g5=["parity_with_co_accused"], g6=["passport"]))
    assert grant["predicted_factors"] == ["custody_period", "parity_with_co_accused"]
    assert grant["predicted_conditions"] == ["passport"] and grant["gold_g6"] == ["passport"]
    refusal = f6.card_payload(card, t1_case(g5=["parity_with_co_accused"], g6_applicable=False))
    assert "gold_g6" not in refusal


def test_one_call_card_drops_factors_outside_the_checklist():
    value = f6.OneCallCard(concerns=[f6.BenchConcern(factor="flight_risk"), f6.BenchConcern(factor="weather")], conditions=["surety"])
    payload = f6.one_call_payload(value, t1_case(g5=["flight_risk"]))
    assert payload["predicted_factors"] == ["flight_risk"] and payload["predicted_conditions"] == ["surety"]
