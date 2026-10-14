"""Bundle splitting, K8 (plan §4.1 K8, §4.3 step 2, §13.6 flow 1).

A bundle is one PDF holding several documents. Boundaries are found where the document type changes, a new header
starts, or page numbers restart. Ranges are inclusive (first, last), contiguous, non-overlapping and cover all pages.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.unit.ingestion._helpers import default_signals, doc_pages, flow1_bundle_pages
from vakeel_sahayak.ingestion.bundles import split_into_documents

HEADERS = ["ORDER SHEET", "REMAND ORDER", "FIR"]


def split(pages: list[str]) -> list[tuple[int, int]]:
    return split_into_documents(pages, default_signals(len(pages)))


def assert_partition(ranges: list[tuple[int, int]], n_pages: int) -> None:
    assert ranges, "at least one range for a non-empty bundle"
    assert ranges[0][0] == 1 and ranges[-1][1] == n_pages
    for (first, last), nxt in zip(ranges, ranges[1:] + [None]):
        assert first <= last
        if nxt is not None:
            assert nxt[0] == last + 1, f"gap or overlap between {(first, last)} and {nxt}"


def test_empty_bundle_has_no_documents():
    """No pages, no documents."""
    assert split_into_documents([], []) == []


def test_single_page_is_one_range():
    """One page is one document, range (1, 1)."""
    assert split(["ORDER SHEET\nFIR No. 112/2024\nPage 1 of 1"]) == [(1, 1)]


def test_single_document_stays_one_range():
    """Five pages with one header and 'Page i of 5' numbering are one document."""
    assert split(doc_pages("REMAND ORDER", 5)) == [(1, 5)]


def test_header_repeated_on_every_page_is_still_one_document():
    """ASSUMPTION: the same header repeated on each page, with page numbers counting up, is one document, not four."""
    assert split(doc_pages("ORDER SHEET", 4, repeat_header=True)) == [(1, 4)]


@pytest.mark.parametrize(
    ("pages", "expected"),
    [
        pytest.param(["ORDER SHEET\nFIR No. 112/2024", "REMAND ORDER\nFIR No. 112/2024"], [(1, 1), (2, 2)], id="header_change_two_docs"),
        pytest.param(["FIR\nlodged 14.08.2024", "REMAND ORDER\nremanded 21.08.2024", "ORDER SHEET\ncharge sheet filed"],
                     [(1, 1), (2, 2), (3, 3)], id="three_different_headers"),
        pytest.param(doc_pages("FIR", 2) + doc_pages("ORDER SHEET", 3), [(1, 2), (3, 5)], id="header_change_after_numbered_doc"),
        pytest.param(doc_pages("ORDER SHEET", 2) + doc_pages("REMAND ORDER", 2) + doc_pages("FIR", 1),
                     [(1, 2), (3, 4), (5, 5)], id="three_docs_mixed_lengths"),
    ],
)
def test_document_type_header_change_splits(pages, expected):
    """A change of document-type header starts a new document."""
    assert split(pages) == expected


def test_page_numbers_restarting_at_one_split_two_identical_headers():
    """Page numbers restarting at 1 split two consecutive documents that carry the same header."""
    pages = doc_pages("REMAND ORDER", 2) + doc_pages("REMAND ORDER", 3)
    assert split(pages) == [(1, 2), (3, 5)]


def test_flow1_bundle_is_four_documents():
    """Plan §13.6 flow 1: FIR (pp.1-3), two remand orders (4-5, 6-7) and a Sessions bail rejection (8-14)."""
    # ASSUMPTION: the two consecutive remand orders are split because the page number restarts at 'Page 1 of 2'.
    pages = flow1_bundle_pages()
    ranges = split(pages)
    assert ranges == [(1, 3), (4, 5), (6, 7), (8, 14)]
    assert_partition(ranges, 14)


# ---- properties ---------------------------------------------------------------------------------------------------
@given(
    st.lists(st.tuples(st.sampled_from(HEADERS), st.integers(min_value=1, max_value=6)), min_size=1, max_size=8),
    st.booleans(),
)
def test_random_bundles_split_exactly_at_the_constructed_boundaries(docs, repeat_header):
    """Property: a bundle built from random documents (header + 'Page i of n') splits exactly where it was joined."""
    pages: list[str] = []
    expected: list[tuple[int, int]] = []
    for header, n in docs:
        expected.append((len(pages) + 1, len(pages) + n))
        pages += doc_pages(header, n, repeat_header=repeat_header)
    ranges = split(pages)
    assert ranges == expected
    assert_partition(ranges, len(pages))


_noise_line = st.sampled_from(HEADERS + ["Page 1 of 3", "Page 2 of 3", "Page 3 of 3", "Page 1 of 1", "", "Some body text.", "14.08.2024"])


@given(st.lists(st.lists(_noise_line, min_size=0, max_size=3).map("\n".join), min_size=1, max_size=15))
def test_ranges_always_partition_the_pages(pages):
    """Property: whatever the page texts, ranges are contiguous, non-overlapping, ordered and cover every page."""
    assert_partition(split(pages), len(pages))


def test_splitting_is_deterministic():
    """The same bundle always splits the same way."""
    pages = flow1_bundle_pages()
    assert split(pages) == split(pages)
