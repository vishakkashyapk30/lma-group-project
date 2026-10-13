"""The page-level routing ladder (plan §4.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.enums import PageStatus, ParseRoute


class RouteOutcome(BaseModel):
    """Result of running a route on a page."""

    route: ParseRoute
    text: str = ""
    text_en: str | None = None
    lang: str | None = None
    confidence: float | None = None
    boxes: list[list[float]] = Field(default_factory=list)
    status: PageStatus = PageStatus.OK
    log: list[str] = Field(default_factory=list)  # e.g. 'text_layer: rejected (legacy font)'


def route_page(
    file_path: str, page: int, thresholds: dict[str, float], max_route: ParseRoute = ParseRoute.ASK_COUNSEL
) -> RouteOutcome:
    """Climb the ladder only as far as needed: text layer, layout parser, clean-up + OCR, vision model, ask counsel (plan §4.2). Log the route and signals for UI badges.

    Args:
        file_path: see behaviour
        page: see behaviour
        thresholds: see behaviour
        max_route: cap for baselines such as P1-P3

    Returns:
        RouteOutcome with the full route log.
    """
    raise NotImplementedError
