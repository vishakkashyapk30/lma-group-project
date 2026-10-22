"""Hierarchy-ranked gap re-reading (S7 / A11a): the ranking, `resolve_gap` under both policies, and the signals (pages re-read, resolved per page, oracle regret)."""

from __future__ import annotations

import pytest

from vakeel_sahayak.ingestion.gaps import GAP_CUES, LIKELY_TYPES, MAX_REREAD_PAGES, resolve_gap
from vakeel_sahayak.ingestion.hierarchy import MIN_SCORE, oracle_regret, rank_pages, summarise
from vakeel_sahayak.ingestion.pageindex import IndexedPage, PageIndex


def weak(page: int, doc_type: str | None, text: str, doc_id: str = "d1", route: str = "ocr", conf: float = 0.6) -> IndexedPage:
    return IndexedPage(file="b.pdf", page=page, doc_id=doc_id, doc_type=doc_type, route=route, ocr_conf=conf, text=text)


def rank(item: str, pages: list[IndexedPage]):
    return rank_pages(item, PageIndex(pages), LIKELY_TYPES[item], GAP_CUES[item])


REMAND = "REMAND_ORDER"


def test_a_heading_that_shows_the_item_outranks_file_order():
    pages = [weak(1, REMAND, "Copy supplied to the accused"), weak(2, REMAND, "Copy supplied to the counsel"), weak(3, REMAND, "Remand order of the court")]
    assert [r.page.page for r in rank("first_remand", pages)] == [3, 1, 2]


def test_document_type_outranks_a_weaker_page_of_another_type():
    pages = [weak(1, "FIR", "Remanded to judicial custody", doc_id="d1"), weak(2, REMAND, "Annexure", doc_id="d2")]
    assert rank("first_remand", pages)[0].page.page == 2


def test_a_page_of_a_document_with_no_type_is_reachable_through_its_heading_only():
    pages = [weak(1, "OTHER", "Annexure list", doc_id="d1"), weak(2, "OTHER", "Order of remand to judicial custody", doc_id="d2")]
    assert [r.page.page for r in rank("first_remand", pages)] == [2]


def test_pages_under_the_minimum_score_are_not_offered():
    ranked = rank("first_remand", [weak(1, "FIR", "Annexure list"), weak(2, "BAIL_ORDER", "Other text")])
    assert ranked == [] and MIN_SCORE > 0


def test_only_weak_pages_are_candidates():
    pages = [weak(1, REMAND, "Remand order", route="vision"), weak(2, REMAND, "Remand order", conf=0.9), weak(3, REMAND, "Remand order")]
    assert [r.page.page for r in rank("first_remand", pages)] == [3]


def test_ranking_is_deterministic_and_ties_break_by_page():
    pages = [weak(p, REMAND, "Copy supplied", doc_id=f"d{p}") for p in (3, 1, 2)]
    first = [r.page.page for r in rank("first_remand", pages)]
    assert first == [r.page.page for r in rank("first_remand", list(reversed(pages)))] == [1, 2, 3]


def reread_with(found_on: set[int], seen: list[int]):
    def reread(page: IndexedPage) -> str | None:
        seen.append(page.page)
        return "remanded to judicial custody" if page.page in found_on else "nothing relevant"

    return reread


def run_policy(policy: str, pages: list[IndexedPage], found_on: set[int], item: str = "first_remand"):
    seen: list[int] = []
    signals: list[dict] = []
    gap = resolve_gap(item, "case-0007", index=PageIndex(pages), reread=reread_with(found_on, seen), ask=lambda i, q: True, policy=policy, signals=signals)
    return gap, seen, signals[0]


def five_weak_remand_pages() -> list[IndexedPage]:
    return [weak(p, REMAND, "Remand order of the court" if p == 5 else "Copy supplied to the accused") for p in range(1, 6)]


def test_sequential_reads_in_file_order_and_stops_at_the_cap():
    gap, seen, rec = run_policy("sequential", five_weak_remand_pages(), found_on={5})
    assert seen == [1, 2, 3] and len(seen) == MAX_REREAD_PAGES and rec["resolved_by"] is None and rec["reads"] == 3
    assert "not found" in gap.action


def test_hierarchy_reads_the_best_page_first_and_stops_when_it_is_found():
    gap, seen, rec = run_policy("hierarchy", five_weak_remand_pages(), found_on={5})
    assert seen == [5] and rec["resolved_by"] == "reread" and rec["reads"] == 1
    assert gap.action.endswith("found") and rec["candidates"][0] == {"file": "b.pdf", "page": 5, "score": rec["candidates"][0]["score"]}
    assert rec["policy"] == "hierarchy" and [c["page"] for c in rec["candidates"]][0] == 5


def test_hierarchy_never_re_reads_more_than_the_cap():
    _, seen, rec = run_policy("hierarchy", five_weak_remand_pages(), found_on=set())
    assert len(seen) == MAX_REREAD_PAGES == rec["reads"] and rec["resolved_by"] is None


def test_hierarchy_reaches_a_mislabelled_page_that_sequential_never_reads():
    pages = [weak(1, "OTHER", "Order of remand to judicial custody", doc_id="d9"), weak(2, "FIR", "Annexure", doc_id="d1")]
    _, seq_seen, seq = run_policy("sequential", pages, found_on={1})
    _, hier_seen, hier = run_policy("hierarchy", pages, found_on={1})
    assert seq_seen == [] and seq["reads"] == 0 and hier_seen == [1] and hier["resolved_by"] == "reread"


def test_without_a_reread_callback_neither_policy_reads_and_both_ask():
    for policy in ("sequential", "hierarchy"):
        signals: list[dict] = []
        gap = resolve_gap("first_remand", "case-0007", index=PageIndex(five_weak_remand_pages()), ask=lambda i, q: True, policy=policy, signals=signals)
        assert signals[0]["reads"] == 0 and "asked counsel" in gap.action


def test_sequential_candidates_and_default_arguments_are_unchanged():
    seen: list[int] = []
    gap = resolve_gap("first_remand", "case-0007", index=PageIndex(five_weak_remand_pages()), reread=reread_with(set(), seen), ask=lambda i, q: True)
    assert seen == [1, 2, 3] and gap.action.startswith("re-read pages 1-3 with a stronger route; not found")


def test_summary_and_oracle_regret():
    records = [
        {"policy": "hierarchy", "reads": 1, "resolved_by": "reread"},
        {"policy": "hierarchy", "reads": 3, "resolved_by": None},
        {"policy": "hierarchy", "reads": 0, "resolved_by": "search"},
        {"policy": "hierarchy", "reads": 0, "resolved_by": "earlier_reread"},
    ]
    assert [oracle_regret(r) for r in records] == [0, 3, 0, 0]
    s = summarise(records)
    assert (s["pages_reread"], s["gaps_resolved_by_reread"], s["gaps_resolved"], s["resolved_per_page_read"], s["oracle_regret"]) == (4, 1, 3, 0.25, 3)
    empty = summarise([])
    assert empty["policy"] is None and empty["resolved_per_page_read"] is None and empty["pages_reread"] == 0


@pytest.mark.parametrize("item", sorted(GAP_CUES))
def test_every_checklist_item_has_a_ranking(item):
    assert isinstance(rank(item, five_weak_remand_pages()), list)
