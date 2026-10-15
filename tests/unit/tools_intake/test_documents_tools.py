"""Document tools: split_bundle, classify_document, file_item, search_pages (plan §4.1 K8, §4.3, §4.4)."""

from __future__ import annotations

import pytest

from tests.fakes.toolbox import leaked_names
from tests.fixtures import pdfgen
from tests.unit.ingestion._helpers import flow1_bundle_pages
from tests.unit.tools_intake._helpers import assert_rejects, patch_everywhere
from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.enums import DocumentType, StoreName
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry
from vakeel_sahayak.tools.intake.documents import classify_document, file_item, search_pages, split_bundle
from vakeel_sahayak.tools.types import FileItemResult


# ---- split_bundle ------------------------------------------------------------------------------------------------
def test_split_bundle_flow1_gives_four_labelled_documents(pdfs, require_pymupdf):
    """Plan §13.6 flow 1: a 14-page file splits into FIR, two remand orders and a bail order with their page ranges."""
    pdf = str(pdfs.text("bundle_1.pdf", flow1_bundle_pages()))
    docs = split_bundle(pdf)
    assert all(isinstance(d, DocumentEntry) for d in docs)
    assert [d.pages for d in docs] == [[1, 3], [4, 5], [6, 7], [8, 14]]
    assert [d.type for d in docs] == [DocumentType.FIR, DocumentType.REMAND_ORDER, DocumentType.REMAND_ORDER, DocumentType.BAIL_ORDER]
    assert len({d.doc_id for d in docs}) == 4, "document ids are unique"


def test_split_bundle_single_document(pdfs, require_pymupdf):
    """A one-document file gives one DocumentEntry covering all pages."""
    pdf = str(pdfs.text("single.pdf", [pdfgen.REMAND_PAGE + "\nPage 1 of 2", "More.\nPage 2 of 2"]))
    docs = split_bundle(pdf)
    assert [d.pages for d in docs] == [[1, 2]]


def test_split_bundle_missing_file(tmp_path):
    """A missing file is rejected."""
    assert_rejects(split_bundle, str(tmp_path / "nope.pdf"))


def test_split_bundle_corrupt_file_is_rejected_or_empty_not_guessed(pdfs, require_pymupdf):
    """K9: a corrupt PDF gives a ToolError/ValueError, never a made-up split."""
    assert_rejects(split_bundle, str(pdfs.corrupt("bad.pdf")))


# ---- classify_document -------------------------------------------------------------------------------------------
def test_classify_document_labels_a_remand_order(pdfs, require_pymupdf):
    """classify_document reads the given pages and returns (type, confidence)."""
    pdf = str(pdfs.text("remand.pdf", [pdfgen.REMAND_PAGE]))
    doc_type, conf = classify_document(pdf, [1])
    assert doc_type == DocumentType.REMAND_ORDER
    assert 0.0 <= conf <= 1.0


def test_classify_document_rejects_empty_page_list(pdfs):
    """A document needs at least one page."""
    assert_rejects(classify_document, str(pdfs.text("a.pdf", ["x"])), [])


def test_classify_document_rejects_page_below_one(pdfs):
    """Pages are 1-based; page 0 is rejected."""
    assert_rejects(classify_document, str(pdfs.text("a.pdf", ["x"])), [0])


# ---- file_item ---------------------------------------------------------------------------------------------------
SRC = SourceRef(doc="d2", page=4, lang="en", route="text_layer", quote="arrested on 20.08.2024")


def test_file_item_timeline_event_lands_in_case_timeline(world, install_stores):
    """A dated event is filed into case.timeline and the result names the store and the item id."""
    install_stores()
    # RECONCILED: the plan's file_item(store, item, source) has no case argument, so the case comes from the item's
    # 'case_id' key (or the runtime's current case); the test names it.
    item = {"case_id": "case-0007", "event_id": "e20", "date": "2024-08-20", "label": "Arrest"}
    result = file_item(StoreName.CASE_TIMELINE, item, SRC)
    assert isinstance(result, FileItemResult)
    assert result.store == StoreName.CASE_TIMELINE
    assert result.item_id == "e20"  # ASSUMPTION: the item id of a timeline event is its event_id
    stored = {e.event_id: e for e in world.stores[StoreName.CASE_TIMELINE].events}
    assert stored["e20"].date == "2024-08-20"
    assert stored["e20"].source is not None and stored["e20"].source.page == 4 and stored["e20"].source.doc == "d2"


def test_file_item_document_chunk_lands_in_case_docs(world, install_stores):
    """Document text is filed into case.docs as a structure-aware chunk with page and box."""
    install_stores()
    item = {"case_id": "case-0007", "chunk_id": "c77", "doc_id": "d2", "doc_type": "REMAND_ORDER", "page": 4, "box": [10.0, 20.0, 300.0, 40.0],
            "text": "The accused was remanded to judicial custody."}
    before = len(world.stores[StoreName.CASE_DOCS].chunks)
    result = file_item(StoreName.CASE_DOCS, item, SRC)
    assert result.store == StoreName.CASE_DOCS and result.item_id == "c77"
    assert len(world.stores[StoreName.CASE_DOCS].chunks) == before + 1


@pytest.mark.parametrize("store", [StoreName.LAW_STATUTES, StoreName.CASELAW_REASONING, StoreName.ADVOCACY_ARGUMENTS])
def test_file_item_refuses_shared_stores(store, install_stores):
    """Munshi writes only to the private case shelf; shared stores are rejected."""
    install_stores()
    assert_rejects(file_item, store, {"event_id": "x", "date": "2024-01-01", "label": "x"}, SRC)


def test_file_item_pseudonymises_names_before_filing(world, install_stores, monkeypatch, planted_names):
    """Plan §4.3 step 3: names are pseudonymised before filing, so no planted name reaches the store."""
    install_stores()

    def fake_pseudonymise(text, case_id, mapping=None):
        for name in planted_names:
            text = text.replace(name, "Accused-1")
        return text, None

    patch_everywhere(monkeypatch, "vakeel_sahayak.privacy.pseudonymise", "pseudonymise_text", fake_pseudonymise)
    item = {"case_id": "case-0007", "event_id": "e21", "date": "2024-08-20", "label": f"{planted_names[0]} arrested"}
    file_item(StoreName.CASE_TIMELINE, item, SRC)
    texts = [e.model_dump_json() for e in world.stores[StoreName.CASE_TIMELINE].events]
    assert leaked_names(texts, planted_names) == []


# ---- search_pages ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("k", [0, -1])
def test_search_pages_rejects_non_positive_k(k):
    """k is a result count and must be at least 1."""
    assert_rejects(search_pages, "case-0007", "charge sheet", k)


def test_search_pages_rejects_empty_query():
    """An empty query is rejected."""
    assert_rejects(search_pages, "case-0007", "   ")
