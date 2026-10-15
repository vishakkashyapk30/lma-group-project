"""Show the page to counsel with a request for a clearer copy; unreadable pages are grouped into one question (step 5). Plan §4.2."""

from __future__ import annotations

from vakeel_sahayak.ingestion.ladder import RouteOutcome
from vakeel_sahayak.schemas.enums import PageStatus, ParseRoute


def ask_counsel_route(file_path: str, page: int) -> RouteOutcome:
    """Show the page to counsel with a request for a clearer copy; unreadable pages are grouped into one question (step 5).

    This route reads nothing and guesses nothing: it marks the page UNREADABLE. Munshi collects such pages (see
    `ingestion.questions.unreadable_question`) and asks one question for all of them.

    Args:
        file_path: see behaviour
        page: page number from 1

    Returns:
        RouteOutcome with empty text and status UNREADABLE.
    """
    return RouteOutcome(
        route=ParseRoute.ASK_COUNSEL,
        text="",
        status=PageStatus.UNREADABLE,
        log=["ask_counsel: clearer copy requested"],
    )
