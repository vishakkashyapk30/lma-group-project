"""The court-ready application DOCX (plan §8.2): cause title with placeholders, "Application under Section 483 BNSS for grant of
regular bail", synopsis, List of Dates and Events, brief facts, earlier bail applications (disclosure), numbered grounds,
statutory position, prayer, verification and affidavit placeholders, annexure index (one entry and page range per uploaded
document); banner "AI-generated draft: check against your court's rules". The List of Dates comes from `case.timeline`.

python-docx is needed to read the result, so these tests are skipped when it is missing. Wording ASSUMPTIONS: `_helpers.py`.
"""

from __future__ import annotations

import re

import pytest

from tests.fakes.data import PLANTED_NAMES
from tests.unit.export._helpers import (
    CITATION_G1,
    CITATION_G2,
    CITATION_G3,
    docx_text,
    make_brief,
    mentions_date,
    position_of,
    uploaded_docs,
)
from vakeel_sahayak.export.application import assemble_application_docx
from vakeel_sahayak.export.sections import APPLICATION_SECTIONS
from vakeel_sahayak.schemas.bail_brief import Ground
from vakeel_sahayak.schemas.enums import ClaimCheck, Factor, FactorStance
from vakeel_sahayak.schemas.store_rows import TimelineEvent

HEADING_WORDS = {
    "synopsis": ("synopsis",),
    "list_of_dates_and_events": ("list of dates",),
    "brief_facts": ("brief facts",),
    "earlier_bail_applications": ("earlier bail",),
    "grounds": ("grounds",),
    "statutory_position": ("statutory position",),
    "prayer": ("prayer",),
    "verification_and_affidavit": ("verification",),
    "annexure_index": ("annexure",),
}


@pytest.fixture()
def application(tmp_path, dossier, timeline):
    pytest.importorskip("docx")
    out = tmp_path / "application.docx"
    path = assemble_application_docx(make_brief(), dossier, timeline, uploaded_docs(), str(out))
    return path, docx_text(path)


def test_returns_the_path_of_an_existing_docx(application, tmp_path):
    path, _ = application
    assert path == str(tmp_path / "application.docx")
    assert (tmp_path / "application.docx").stat().st_size > 0


def test_heading_is_the_section_483_bnss_application(application):
    """Plan §8.2: 'Application under Section 483 BNSS for grant of regular bail'."""
    assert "Application under Section 483 BNSS for grant of regular bail" in application[1]


def test_ai_generated_draft_banner_is_present(application):
    """The banner of plan §8.2: AI-generated draft: check against your court's rules."""
    text = application[1]
    assert "AI-generated draft" in text
    assert "check against your court's rules" in text


def test_brief_label_is_carried_over(application):
    """The brief's own label, 'AI-generated draft. Not legal advice.', appears too (plan §8.1)."""
    assert "Not legal advice" in application[1]


@pytest.mark.parametrize("section", [s for s in APPLICATION_SECTIONS if s in HEADING_WORDS])
def test_every_section_has_a_heading(application, section):
    assert position_of(application[1], *HEADING_WORDS[section]) >= 0, section


def test_sections_appear_in_the_order_of_the_plan(application):
    """Synopsis < List of Dates < brief facts < earlier applications < grounds < statutory position < prayer < verification < annexure."""
    text = application[1]
    order = [s for s in APPLICATION_SECTIONS if s in HEADING_WORDS]
    positions = [position_of(text, *HEADING_WORDS[s]) for s in order]
    assert positions == sorted(positions), dict(zip(order, positions))


def test_cause_title_uses_placeholders_not_names(application):
    """Real names are filled in only on counsel's machine: the cause title carries bracketed placeholders (plan §8.2)."""
    text = application[1]
    head = text[: text.lower().find("synopsis")]
    assert re.search(r"\[[A-Z][A-Z ./-]+\]", head), head
    for name in PLANTED_NAMES:
        assert name not in text


def test_verification_and_affidavit_are_placeholders(application):
    text = application[1]
    assert "verification" in text.lower() and "affidavit" in text.lower()
    tail = text[text.lower().find("verification"):]
    assert re.search(r"\[[A-Z][A-Z ./-]+\]", tail)


def test_grounds_are_numbered_and_carry_their_rendered_citations(application):
    """Three grounds, numbered 1-3, each with the citation text rendered from corpus metadata, and no raw [A:...] tags left."""
    text = application[1]
    for cite in (CITATION_G1, CITATION_G2, CITATION_G3):
        assert cite in text
    assert "[A:" not in text
    grounds = text[text.lower().find("grounds"):]
    assert [grounds.find(f"{n}.") for n in (1, 2, 3)] == sorted(grounds.find(f"{n}.") for n in (1, 2, 3))
    assert all(grounds.find(f"{n}.") >= 0 for n in (1, 2, 3))


def test_ground_text_is_the_brief_text_word_for_word(application):
    """The model writes only the synopsis, the brief facts and the prayer; grounds are copied from the brief."""
    text = application[1]
    assert "Co-accused-1, with an identical role, was granted bail on 05.12.2024" in text
    assert "custodial interrogation is no longer required" in text


def test_needs_review_ground_is_not_dropped_silently(tmp_path, dossier, timeline):
    """Plan §8.1: nothing is ever dropped silently. A NEEDS_REVIEW ground still appears in the draft (and is marked)."""
    pytest.importorskip("docx")
    path = assemble_application_docx(make_brief(third_needs_review=True), dossier, timeline, uploaded_docs(), str(tmp_path / "a.docx"))
    text = docx_text(path)
    assert "167 days" in text
    assert re.search(r"needs[ _-]review", text, re.I)


def test_list_of_dates_section_has_every_timeline_date_with_source(application, timeline):
    """Every event of case-0007's timeline is in the List of Dates, with its document."""
    text = application[1]
    start = text.lower().find("list of dates")
    end = text.lower().find("brief facts", start)
    section = text[start:end]
    for ev in timeline:
        assert mentions_date(section, ev.date), ev
        assert ev.label in section
    assert "d2 (remand order)" in section


def test_list_of_dates_takes_dates_only_from_the_timeline(tmp_path, dossier):
    """With a timeline of one event the List of Dates has that date and no other: dates are never model-written (plan §8.2)."""
    pytest.importorskip("docx")
    brief = make_brief().model_copy(update={"grounds": [Ground(id="G1", factor=Factor.CUSTODY_PERIOD, stance=FactorStance.FAVOURABLE,
                                                                argument="Custody is long.", check=ClaimCheck.SUPPORTED)]})
    one = [TimelineEvent(event_id="e3", date="2024-08-20", label="Arrest")]
    text = docx_text(assemble_application_docx(brief, dossier, one, uploaded_docs(), str(tmp_path / "a.docx")))
    section = text[text.lower().find("list of dates"): text.lower().find("brief facts", text.lower().find("list of dates"))]
    assert mentions_date(section, "2024-08-20")
    for other in ("2024-08-21", "2024-09-30", "2024-11-02", "2024-12-05"):
        assert not mentions_date(section, other)


def test_annexure_index_has_one_entry_per_uploaded_document_with_page_range(application):
    """Plan §8.2: one entry and page range per uploaded document (F5: matches the uploaded files)."""
    text = application[1]
    index = text[text.lower().rfind("annexure"):]
    lines = [ln for ln in index.splitlines() if re.search(r"\d", ln)]
    ranges = [r"1\s*(?:-|–|to)\s*3", r"4\s*(?:-|–|to)\s*5", r"6\s*(?:-|–|to)\s*7", r"8\s*(?:-|–|to)\s*14"]
    for pat in ranges:
        assert sum(bool(re.search(pat, ln)) for ln in lines) == 1, pat
    assert len(lines) >= 4


def test_annexure_index_names_the_document_types(application):
    text = application[1].lower()
    index = text[text.rfind("annexure"):]
    assert "fir" in index and "remand" in index and "bail" in index


def test_statutory_position_is_taken_from_the_brief(application):
    text = application[1]
    pos = text[text.lower().rfind("statutory position"):]
    assert "318(4)" in pos and "7 years" in pos


def test_earlier_bail_applications_are_disclosed_from_the_dossier(application):
    """The Sessions Court rejection of 30.09.2024 (dossier field previous_bail) is disclosed."""
    text = application[1]
    start = text.lower().find("earlier bail")
    section = text[start: start + 600]
    assert "Sessions Court" in section and mentions_date(section, "2024-09-30")


def test_prayer_asks_for_regular_bail(application):
    text = application[1]
    prayer = text[text.lower().find("prayer"):]
    assert "bail" in prayer.lower()


def test_empty_annexure_list_still_builds(tmp_path, dossier, timeline):
    """No uploaded documents (a dictated case): the application still builds and the annexure index says there are none."""
    pytest.importorskip("docx")
    path = assemble_application_docx(make_brief(), dossier, timeline, [], str(tmp_path / "a.docx"))
    assert "annexure" in docx_text(path).lower()
