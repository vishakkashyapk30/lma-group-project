"""Qwen3-VL transcription only, never summarise (step 4). Plan §4.2."""

from __future__ import annotations

from vakeel_sahayak.ingestion.hindi import lang_of
from vakeel_sahayak.ingestion.ladder import RouteOutcome
from vakeel_sahayak.ingestion.signals import text_quality
from vakeel_sahayak.ingestion.source import open_source
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.models.factory import get_vision
from vakeel_sahayak.schemas.enums import PageStatus, ParseRoute


def vision_route(file_path: str, page: int) -> RouteOutcome:
    """Qwen3-VL transcription only, never summarise (step 4).

    The page image stays on the laptop. The model gives no confidence, so the outcome's `confidence` is the word-list
    share of the transcript, a stand-in that the filing step records as it is.

    Args:
        file_path: see behaviour
        page: page number from 1

    Returns:
        RouteOutcome with the transcript.

    Raises:
        ModelUnavailable: no vision model is installed.
    """
    image = open_source(file_path).render(page)
    if image is None:
        raise ModelUnavailable("this page cannot be rendered to an image for the vision model")
    client = get_vision()
    text = client.transcribe_page(image, None).strip()
    share, _ = text_quality(text)
    return RouteOutcome(
        route=ParseRoute.VISION,
        text=text,
        lang=lang_of(text) if text else None,
        confidence=share,
        status=PageStatus.OK if text else PageStatus.UNREADABLE,
        log=[f"vision: {getattr(client, 'name', 'vision')}"],
    )
