"""Pipeline P2: OCR on every page, Tesseract eng+hin (plan §15.5).

Every page is rendered to an image and sent to the configured OCR client once (plain OCR: no clean-up, no retry, no text layer, no vision model, no
questions). When only the offline stand-in is configured and a Tesseract binary exists, Tesseract is called through its command line; if the machine has
no Hindi data it reads with English only and the run record says so. The bundle is one undifferentiated document.
"""

from __future__ import annotations

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.eval.ingestion.common import (
    ArmUnavailable,
    BundleResult,
    ocr_client,
    page_count,
    single_document_report,
    tesseract_languages,
)
from vakeel_sahayak.ingestion.hindi import lang_of
from vakeel_sahayak.ingestion.source import open_source
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.schemas.enums import PageStatus
from vakeel_sahayak.schemas.ingestion_report import IngestionReport, PageRoute

PIPELINE = "P2"


def availability() -> tuple[bool, str]:
    """(runnable, note): an OCR client other than the stand-in, or a Tesseract binary."""
    from vakeel_sahayak.eval.ingestion.common import TesseractCliOcr
    from vakeel_sahayak.models import factory
    from vakeel_sahayak.models.offline import OfflineOcrClient

    client = factory.get_ocr()
    if not isinstance(client, OfflineOcrClient):
        return True, f"ocr client {getattr(client, 'name', type(client).__name__)}"
    langs = tesseract_languages()
    if not langs:
        return False, "no OCR engine (Surya, pytesseract or the tesseract binary) is installed"
    note = "" if {"eng", "hin"} <= langs else f"tesseract has {sorted(langs)}: no Hindi data, so Hindi pages are read with English only"
    return True, f"{TesseractCliOcr.name}; {note}".rstrip("; ")


def run_bundle(pdf_path: str, ctx: AgentContext | None = None, lang: str = "hin+eng") -> BundleResult:
    """OCR every page of a bundle under P2 (`lang` 'eng' gives the English-only comparison of F8); returns the report and the page texts."""
    src = open_source(pdf_path)
    client = ocr_client()
    texts, routes, notes = [], [], []
    for page in range(1, page_count(pdf_path) + 1):
        image = src.render(page)
        if image is None:
            raise ArmUnavailable("this page cannot be rendered to an image for OCR (PyMuPDF missing?)")
        try:
            text, conf, _ = client.ocr(image, lang)
        except ModelUnavailable as exc:
            raise ArmUnavailable(str(exc)) from exc
        if getattr(client, "last_note", ""):
            notes.append(client.last_note)
        label = f"ocr: {getattr(client, 'name', 'ocr')}-{lang_of(text) if text.strip() else 'en'}"
        texts.append(text)
        routes.append(PageRoute(page=page, kind="unclassified", route=[label], ocr_conf=round(conf, 2),
                                status=PageStatus.OK if text.strip() else PageStatus.UNREADABLE))
    return BundleResult(single_document_report(pdf_path, routes, texts), texts, notes=sorted(set(notes)))


def ingest_bundle(pdf_path: str, ctx: AgentContext | None = None) -> IngestionReport:
    """Ingest one T2 bundle under P2.

    Args:
        pdf_path: the bundle PDF
        ctx: unused (P2 has no agent)

    Returns:
        IngestionReport with one document covering every page.

    Raises:
        ArmUnavailable: no OCR engine is installed.
    """
    return run_bundle(pdf_path, ctx).report
