"""Page quality signals (plan §4.2)."""

from __future__ import annotations

from pydantic import BaseModel


class PageSignals(BaseModel):
    """Cheap per-page quality signals (plan §4.2). Thresholds in configs/thresholds.yaml, tuned on dev."""

    text_coverage: float | None = None
    mean_ocr_conf: float | None = None
    dict_word_share: float | None = None
    script_consistency: float | None = None
    chars_per_area: float | None = None
    legacy_font_pattern: bool = False
    has_text_layer: bool = False
    handwriting_detected: bool = False
    skew_or_perspective: bool = False


def compute_signals(file_path: str, page: int) -> PageSignals:
    """Compute the cheap signals for one page without running expensive models.

    Args:
        file_path: see behaviour
        page: see behaviour

    Returns:
        PageSignals.
    """
    raise NotImplementedError


def passes_text_layer_check(signals: PageSignals, thresholds: dict[str, float]) -> bool:
    """Text layer covers the page, >=85% of words in English or Hindi word lists, and no legacy-font pattern (plan §4.2 step 1).

    Args:
        signals: see behaviour
        thresholds: see behaviour

    Returns:
        bool.
    """
    raise NotImplementedError


def detect_legacy_font(text: str) -> bool:
    """K6: text layer decodes to Latin gibberish from Kruti Dev-style fonts.

    Args:
        text: see behaviour

    Returns:
        bool.
    """
    raise NotImplementedError
