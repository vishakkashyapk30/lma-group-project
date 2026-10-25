"""Pipeline P4: the vision model on every page (plan §15.5), the cost reference.

Every page is rendered and transcribed by the vision model once: no text layer, no OCR, no questions. It is run on a 1,500-page subset of T2 (the
runner takes whole bundles until the page budget is reached), so its cost is a reference, not a full arm. Without a
vision model installed (Qwen3-VL, or Sarvam Vision under its consent gate) the runner records the arm as unavailable.
"""

from __future__ import annotations

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.eval.ingestion.common import (
    ArmUnavailable,
    BundleResult,
    page_count,
    page_route_of,
    single_document_report,
)
from vakeel_sahayak.ingestion.hindi import lang_of
from vakeel_sahayak.ingestion.ladder import RouteOutcome
from vakeel_sahayak.ingestion.signals import text_quality
from vakeel_sahayak.ingestion.source import open_source
from vakeel_sahayak.models import factory
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.schemas.enums import PageStatus, ParseRoute
from vakeel_sahayak.schemas.ingestion_report import IngestionReport

PIPELINE = "P4"
PAGE_BUDGET = 1500


def availability() -> tuple[bool, str]:
    """(runnable, note): a vision client other than the offline stand-in (which reads only synthetic stand-in images)."""
    from vakeel_sahayak.models import factory
    from vakeel_sahayak.models.offline import OfflineVisionClient

    client = factory.get_vision()
    if isinstance(client, OfflineVisionClient):
        return False, "no vision model is installed or enabled (Qwen3-VL missing; VS_SARVAM is not 'pseudonymised'/'consented')"
    return True, f"vision client {getattr(client, 'name', type(client).__name__)}"


def transcribe(pdf_path: str, page: int) -> RouteOutcome:
    """One page through the configured vision client (looked up at call time, so a swapped client is honoured); transcription only.

    Raises:
        ModelUnavailable: the page cannot be rendered, or no vision model is installed.
    """
    image = open_source(pdf_path).render(page)
    if image is None:
        raise ModelUnavailable("this page cannot be rendered to an image for the vision model")
    client = factory.get_vision()
    text = client.transcribe_page(image, None).strip()
    share, _ = text_quality(text)
    return RouteOutcome(route=ParseRoute.VISION, text=text, lang=lang_of(text) if text else None, confidence=share,
                        status=PageStatus.OK if text else PageStatus.UNREADABLE, log=[f"vision: {getattr(client, 'name', 'vision')}"])


def run_bundle(pdf_path: str, ctx: AgentContext | None = None) -> BundleResult:
    """Transcribe every page of a bundle under P4; returns the report and the page texts."""
    texts, routes = [], []
    for page in range(1, page_count(pdf_path) + 1):
        try:
            out = transcribe(pdf_path, page)
        except ModelUnavailable as exc:
            raise ArmUnavailable(str(exc)) from exc
        texts.append(out.text)
        routes.append(page_route_of(page, out))
    return BundleResult(single_document_report(pdf_path, routes, texts), texts)


def ingest_bundle(pdf_path: str, ctx: AgentContext | None = None) -> IngestionReport:
    """Ingest one T2 bundle under P4 (the 1,500-page subset is the intended use: the cost reference).

    Args:
        pdf_path: the bundle PDF
        ctx: unused (P4 has no agent)

    Returns:
        IngestionReport with one document covering every page.

    Raises:
        ArmUnavailable: no vision model.
    """
    return run_bundle(pdf_path, ctx).report
