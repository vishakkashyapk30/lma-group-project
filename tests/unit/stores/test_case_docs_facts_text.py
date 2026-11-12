"""The local case-docs facts-text view used by the c1457 product flow."""

from __future__ import annotations

import pytest

from vakeel_sahayak.schemas.enums import DocumentType
from vakeel_sahayak.schemas.store_rows import CaseChunk
from vakeel_sahayak.stores.case_docs import CaseDocsStore


def _chunk(chunk_id: str, doc_id: str, page: int, text: str) -> CaseChunk:
    return CaseChunk(chunk_id=chunk_id, doc_id=doc_id, doc_type=DocumentType.FIR, page=page, text=text)


def test_facts_text_is_ordered_pseudonymised_case_text_and_bounded():
    """The product reads only its private, already-pseudonymised case shelf."""
    store = CaseDocsStore()
    store.bind_case("case-0007")
    store.open(":memory:")
    try:
        store.add_chunks([
            _chunk("d2-p2-c1", "d2", 2, "Person-1 was remanded."),
            _chunk("d1-p2-c1", "d1", 2, "The FIR records the allegation."),
            _chunk("d1-p1-c1", "d1", 1, "Person-1 was arrested on 04.01.2024."),
        ])
        assert store.facts_text() == (
            "Person-1 was arrested on 04.01.2024.\n"
            "The FIR records the allegation.\n"
            "Person-1 was remanded."
        )
        assert store.facts_text(max_chars=20) == "Person-1 was arreste"
    finally:
        store.close()


@pytest.mark.parametrize("max_chars", [0, -1])
def test_facts_text_rejects_a_nonpositive_bound(max_chars):
    store = CaseDocsStore()
    store.bind_case("case-0007")
    store.open(":memory:")
    try:
        with pytest.raises(ValueError, match="positive"):
            store.facts_text(max_chars)
    finally:
        store.close()
