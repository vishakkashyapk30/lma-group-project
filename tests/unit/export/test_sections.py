"""Names and order of the application sections (plan §8.2)."""

from __future__ import annotations

from vakeel_sahayak.export.sections import APPLICATION_SECTIONS

PLAN_SECTIONS = [
    "cause_title",
    "heading_s483_bnss",
    "synopsis",
    "list_of_dates_and_events",
    "brief_facts",
    "earlier_bail_applications",
    "grounds",
    "statutory_position",
    "prayer",
    "verification_and_affidavit",
    "annexure_index",
]


def test_eleven_sections_in_the_order_of_plan_8_2():
    """Cause title, s.483 BNSS heading, synopsis, List of Dates, brief facts, earlier applications, grounds, statutory position, prayer, verification and affidavit placeholders, annexure index."""
    assert APPLICATION_SECTIONS == PLAN_SECTIONS


def test_no_duplicates():
    assert len(set(APPLICATION_SECTIONS)) == len(APPLICATION_SECTIONS) == 11


def test_list_of_dates_comes_before_the_grounds_and_the_annexure_index_is_last():
    """High Court filings put the List of Dates early and the annexure index at the end."""
    s = APPLICATION_SECTIONS
    assert s.index("list_of_dates_and_events") < s.index("brief_facts") < s.index("grounds")
    assert s[-1] == "annexure_index"
    assert s.index("prayer") < s.index("verification_and_affidavit") < s.index("annexure_index")
