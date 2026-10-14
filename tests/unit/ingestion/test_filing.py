"""Filing rules: what goes where in the case shelf (plan §4.4 table)."""

from __future__ import annotations

import pytest

from vakeel_sahayak.ingestion.filing import FILING_RULES, target_stores
from vakeel_sahayak.schemas.enums import InfoKind as I
from vakeel_sahayak.schemas.enums import StoreName as S


def test_filing_rules_match_plan_table_exactly():
    """Plan §4.4: seven kinds of finding, each with its destination."""
    assert FILING_RULES == {
        "document_text": "case.docs",
        "dated_event": "case.timeline",
        "party": "case.facts",
        "section": "case.facts",
        "earlier_outcome": "case.timeline+case.facts",
        "custody_health_personal": "case.facts",
        "unreadable_or_missing": "open_questions",
    }


def test_filing_rules_destinations_are_real_stores_or_open_questions():
    """Every destination is a StoreName on the case shelf, or open questions for counsel."""
    for kind, dest in FILING_RULES.items():
        for part in dest.split("+"):
            assert part == "open_questions" or (S(part).value.startswith("case.")), (kind, part)


def test_only_unreadable_or_missing_goes_to_open_questions():
    """Open questions are used only for unreadable or missing items."""
    assert [k for k, v in FILING_RULES.items() if "open_questions" in v] == ["unreadable_or_missing"]


TARGETS = [
    (I.DATED_EVENT, {S.CASE_TIMELINE}),
    (I.PARTY, {S.CASE_FACTS}),
    (I.SECTION, {S.CASE_FACTS}),
    (I.EARLIER_OUTCOME, {S.CASE_TIMELINE, S.CASE_FACTS}),
    (I.CUSTODY, {S.CASE_FACTS}),
    (I.PERSONAL, {S.CASE_FACTS}),
]


@pytest.mark.parametrize(("kind", "stores"), [pytest.param(k, s, id=k.value) for k, s in TARGETS])
def test_target_stores_follow_the_filing_table(kind, stores):
    """Plan §4.4: each information kind goes to the stated case-shelf store(s); an earlier outcome goes to two."""
    out = target_stores(kind)
    assert set(out) == stores
    assert len(out) == len(set(out)), "no store listed twice"


def test_target_stores_covers_every_info_kind():
    """The table covers all six InfoKinds, so no paragraph kind has nowhere to go."""
    assert {k for k, _ in TARGETS} == set(I)


def test_nothing_is_filed_outside_the_case_shelf():
    """Munshi writes only to the private case shelf, never to shared stores (plan §5.1)."""
    for kind in I:
        assert all(s.value.startswith("case.") for s in target_stores(kind))
