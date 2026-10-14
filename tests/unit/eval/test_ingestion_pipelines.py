"""RQ2 ingestion pipelines P1-P6 and Munshi (plan §15.5), compared on T2 bundles by input kind K1-K6.

| P1 | text layer only (PyMuPDF) | P4 | the vision model on every page (cost reference) |
| P2 | OCR on every page (Tesseract eng+hin) | P5 | Munshi's ladder, fixed thresholds; no gap check, no re-reading, no questions |
| P3 | Docling's default pipeline | P6 | Munshi without bundle splitting and document labelling |
| Munshi | the full agent, with a scripted counsel answering its questions |

Each `ingest_bundle(pdf_path, ctx=None)` returns an IngestionReport. What distinguishes the pipelines is which backends they touch, so the
tests count backend calls (OCR, vision, layout, the Munshi tools) on a constructed bundle: two text pages, one image-only page, one text page.

P1-P4 read real PDFs and need PyMuPDF (`require_pymupdf`); P5, P6 and Munshi run on the FakeToolbox pages like the Munshi unit tests.
# SKELETON-GAP: how P3 calls Docling and how P1-P4 obtain page images is not specified; the tests patch `routes.layout.parse_layout_page` and
# `models.factory.get_ocr / get_vision`, which every implementation is documented to go through (skeleton.md 'Models').
# SKELETON-GAP: the per-kind breakdown and the escalation / questions metrics of §15.5 have no function yet; the intended interface is
# `eval.metrics.ingestion.by_kind(values)`, `escalation_rate(report)` and `questions_asked(report)`.
"""

from __future__ import annotations

import importlib

import pytest

from tests.fakes.data import build_world
from tests.fakes.toolbox import FakePage, FakeToolbox
from tests.fixtures import pdfgen
from tests.unit.agents.munshi.test_agent import bundle_pages
from tests.unit.ingestion._helpers import patch_attr_everywhere
from tests.unit.tools_intake._helpers import AnyImageOcr, AnyImageVision
from vakeel_sahayak.ingestion.ladder import RouteOutcome
from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.schemas.enums import DocumentType, ParseRoute
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry, IngestionReport, PageRoute

SPEC = [pdfgen.REMAND_PAGE, pdfgen.REMAND_PAGE, None, pdfgen.BAIL_ORDER_PAGE]  # pages 1-2 text, 3 image-only, 4 text
N_PAGES = len(SPEC)
PIPELINES = {"p1": "p1_text_layer_only", "p2": "p2_ocr_every_page", "p3": "p3_docling_default", "p4": "p4_vision_every_page",
             "p5": "p5_fixed_cascade", "p6": "p6_no_split_label", "munshi": "munshi_full"}


def pipeline(pid: str):
    return importlib.import_module(f"vakeel_sahayak.eval.ingestion.{PIPELINES[pid]}")


class Backends:
    def __init__(self, monkeypatch) -> None:
        self.ocr, self.vision, self.layout_pages = AnyImageOcr("OCR TEXT 112/2024", 0.9), AnyImageVision("VISION TEXT 112/2024"), []
        patch_attr_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_ocr", lambda *a, **k: self.ocr)
        patch_attr_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_vision", lambda *a, **k: self.vision)

        def layout(file_path: str, page: int) -> RouteOutcome:
            self.layout_pages.append(page)
            return RouteOutcome(route=ParseRoute.LAYOUT, text="DOCLING TEXT")

        patch_attr_everywhere(monkeypatch, "vakeel_sahayak.ingestion.routes.layout", "parse_layout_page", layout)


@pytest.fixture()
def bundle(pdfs, require_pymupdf, monkeypatch):
    return str(pdfs.mixed("bundle.pdf", SPEC)), Backends(monkeypatch)


def routes_text(report: IngestionReport) -> list[str]:
    return [" | ".join(pr.route).lower() for d in report.documents for pr in d.page_routes]


def covered_pages(report: IngestionReport) -> list[int]:
    return [p for d in report.documents for p in range(d.pages[0], d.pages[1] + 1)]


# ---------------------------------------------------------------- P1-P4: one backend each
@pytest.mark.parametrize("pid", ["p1", "p2", "p3", "p4"])
def test_p1_to_p4_report_every_page_of_the_bundle_exactly_once(bundle, pid):
    """Whatever it uses, a pipeline's report accounts for pages 1..N with no gaps or overlaps."""
    pdf, _ = bundle
    report = pipeline(pid).ingest_bundle(pdf)
    assert isinstance(report, IngestionReport) and report.file.endswith("bundle.pdf")
    assert covered_pages(report) == list(range(1, N_PAGES + 1))


def test_p1_reads_only_the_text_layer(bundle):
    """P1: PyMuPDF text layer only: no OCR, no vision, no layout parser; the image-only page gets no text-layer reading."""
    pdf, be = bundle
    report = pipeline("p1").ingest_bundle(pdf)
    assert be.ocr.calls == [] and be.vision.calls == [] and be.layout_pages == []
    assert all("ocr" not in r and "vision" not in r for r in routes_text(report))


def test_p2_runs_ocr_on_every_page_even_those_with_a_text_layer(bundle):
    """P2: 'OCR on every page': 4 OCR calls for 4 pages, the text-layer rung is never used, and the vision model is not involved."""
    pdf, be = bundle
    report = pipeline("p2").ingest_bundle(pdf)
    assert len(be.ocr.calls) == N_PAGES and be.vision.calls == []
    assert all("ocr" in r and "text_layer" not in r for r in routes_text(report))


def test_p3_uses_docling_for_every_page_and_nothing_else(bundle):
    """P3: Docling's default pipeline: layout parsing on all pages, no vision escalation, no counsel questions."""
    pdf, be = bundle
    report = pipeline("p3").ingest_bundle(pdf)
    assert sorted(be.layout_pages) == list(range(1, N_PAGES + 1)) and be.vision.calls == []
    assert report.questions == []


def test_p4_sends_every_page_to_the_vision_model(bundle):
    """P4: the cost reference: vision on every page (4 calls for 4 pages), and no OCR."""
    pdf, be = bundle
    report = pipeline("p4").ingest_bundle(pdf)
    assert len(be.vision.calls) == N_PAGES and be.ocr.calls == []
    assert all("vision" in r for r in routes_text(report))


def test_p4_is_documented_as_a_1500_page_subset():
    assert "1,500-page subset" in pipeline("p4").__doc__


# ---------------------------------------------------------------- P5, P6 and Munshi on the fake toolbox
def toolbox(answers=None, pages=None):
    return FakeToolbox(build_world(), pages=pages if pages is not None else bundle_pages(), answers=answers or [])


def ingest(pid: str, make_ctx, tb):
    return pipeline(pid).ingest_bundle("bundle_1.pdf", make_ctx(toolbox=tb))


def test_p5_has_no_gap_check_no_questions_and_no_rereading(make_ctx):
    """P5: Munshi's ladder with fixed thresholds but no gap check, no re-reading (search_pages), no questions to counsel."""
    tb = toolbox()
    report = ingest("p5", make_ctx, tb)
    assert tb.count("ask_user") == 0 and tb.count("search_pages") == 0 and tb.questions == []
    assert report.questions == [] and report.gaps == []


def test_p5_still_routes_and_splits_the_bundle(make_ctx):
    """What P5 keeps from Munshi: per-page routing and the split: the five pages become three labelled documents."""
    report = ingest("p5", make_ctx, toolbox())
    assert [d.pages for d in report.documents] == [[1, 2], [3, 4], [5, 5]]
    assert [d.type for d in report.documents] == [DocumentType.REMAND_ORDER, DocumentType.BAIL_ORDER, DocumentType.ORDER_SHEET]


def test_p6_does_not_split_or_label(make_ctx):
    """P6: 'without bundle splitting and document labelling': neither tool is called and the file is one undifferentiated document."""
    tb = toolbox()
    report = ingest("p6", make_ctx, tb)
    assert tb.count("split_bundle") == 0 and tb.count("classify_document") == 0
    assert len(report.documents) == 1 and report.documents[0].pages == [1, 5]
    assert report.documents[0].type == DocumentType.OTHER


def test_p6_still_checks_gaps(make_ctx):
    """P6 only removes splitting and labelling: the gap check still searches or asks."""
    tb = toolbox(answers=["", "", ""])
    ingest("p6", make_ctx, tb)
    assert tb.count("search_pages") + tb.count("ask_user") >= 1


def test_munshi_splits_labels_checks_gaps_and_asks(make_ctx):
    """The full agent: split_bundle once, a label per document, and the gap check acts on the missing custody certificate;
    the scripted counsel (the FakeToolbox's queued answers) answers at most three questions per round (plan §4.3)."""
    tb = toolbox(answers=["Custody certificate not issued yet", "", ""])
    report = ingest("munshi", make_ctx, tb)
    assert tb.count("split_bundle") == 1 and tb.count("classify_document") >= len(report.documents)
    assert tb.count("search_pages") + tb.count("ask_user") >= 1
    assert all(len(q) <= 3 for q in tb.questions)
    assert [d.pages for d in report.documents] == [[1, 2], [3, 4], [5, 5]]


def test_munshi_asks_where_p5_stays_silent(make_ctx):
    """The contrast RQ2 measures: on the same bundle Munshi asks counsel something, P5 asks nothing."""
    full_tb, p5_tb = toolbox(answers=["", "", ""]), toolbox(answers=["", "", ""])
    ingest("munshi", make_ctx, full_tb)
    ingest("p5", make_ctx, p5_tb)
    assert len(full_tb.questions) >= 1 and p5_tb.questions == []


@pytest.mark.parametrize("pid", ["p5", "p6", "munshi"])
def test_munshi_family_reports_every_page_once(make_ctx, pid):
    report = ingest(pid, make_ctx, toolbox(answers=["", "", ""]))
    assert covered_pages(report) == [1, 2, 3, 4, 5]


def test_unreadable_page_escalates_to_vision_under_munshi_and_p5(make_ctx):
    """The ladder (kept by P5) escalates a low-confidence OCR page to the vision model once, with no re-reading afterwards."""
    pages = [FakePage(text="", signals=PageSignals(has_text_layer=False),
                      ocr_text="smudged", ocr_conf=0.3, vision_text="Remand order dated 21.08.2024", doc_type=DocumentType.REMAND_ORDER)]
    for pid in ("p5", "munshi"):
        tb = toolbox(pages=list(pages), answers=["", "", ""])
        ingest(pid, make_ctx, tb)
        assert tb.count("vision_read_page") == 1, pid


# ---------------------------------------------------------------- per-kind breakdown and the RQ2 side metrics (SKELETON-GAP)
def metric(name: str):
    m = importlib.import_module("vakeel_sahayak.eval.metrics.ingestion")
    fn = getattr(m, name, None)
    assert fn is not None, f"SKELETON-GAP: eval.metrics.ingestion.{name} (plan §15.5 'All results are reported by input kind (K1-K6)')"
    return fn


def test_results_are_reported_by_input_kind():
    """by_kind([(kind, score), ...]) -> mean score per kind; a kind with no bundles does not appear."""
    res = metric("by_kind")([("K1", 1.0), ("K1", 0.5), ("K2", 0.2), ("K6", 0.0)])
    assert res == {"K1": pytest.approx(0.75), "K2": pytest.approx(0.2), "K6": pytest.approx(0.0)}
    assert metric("by_kind")([]) == {}


def test_escalation_rate_is_the_share_of_pages_that_reached_the_vision_model():
    """Share of pages escalated to the vision model: 1 of 4."""
    routes = [["text_layer"], ["text_layer"], ["ocr: surya-hi", "vision: qwen3-vl"], ["text_layer"]]
    doc = DocumentEntry(doc_id="d1", type=DocumentType.OTHER, pages=[1, 4], lang="en",
                        page_routes=[PageRoute(page=i + 1, kind="x", route=r) for i, r in enumerate(routes)])
    assert metric("escalation_rate")(IngestionReport(case_id="c", file="f.pdf", documents=[doc])) == pytest.approx(0.25)


def test_questions_asked_counts_the_questions_in_the_report():
    rep = IngestionReport(case_id="c", file="f.pdf", questions=["Page 3 unreadable?", "Charge sheet filed?"])
    assert metric("questions_asked")(rep) == 2
