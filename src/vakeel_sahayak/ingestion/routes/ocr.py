"""Clean-up (deskew, dewarp, denoise) then Surya OCR; Tesseract fallback (step 3). Plan §4.2."""

from __future__ import annotations

from vakeel_sahayak.ingestion.hindi import lang_of
from vakeel_sahayak.ingestion.imaging import DEFAULT_OPS, STRONG_OPS, clean_image_bytes
from vakeel_sahayak.ingestion.ladder import RouteOutcome
from vakeel_sahayak.ingestion.source import open_source
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.models.factory import get_ocr
from vakeel_sahayak.schemas.enums import PageStatus, ParseRoute

OCR_LANGS = ("eng", "hin", "hin+eng")


def ops_for(skew: bool, strong: bool) -> list[str]:
    """Clean-up operations: a photo is dewarped and deskewed (K4), a retry adds denoising (K3)."""
    if strong:
        return list(STRONG_OPS)
    return ["dewarp", "deskew"] if skew else list(DEFAULT_OPS)


def ocr_page_lang(file_path: str, page: int, lang: str | None = None, strong: bool = False) -> RouteOutcome:
    """Clean-up (deskew, dewarp, denoise) then Surya OCR; Tesseract fallback (step 3).

    Args:
        file_path: see behaviour
        page: page number from 1
        lang: 'eng', 'hin' or 'hin+eng' (default: both, so the first pass also finds the script)
        strong: also denoise and dewarp (the retry for degraded scans, K3)

    Returns:
        RouteOutcome with text, mean confidence, boxes and a log such as ['deskew', 'ocr: surya-hi'].

    Raises:
        ModelUnavailable: no OCR engine is installed, or opencv is missing for a real image.
        ValueError: for an unknown `lang`.
    """
    chosen = lang or "hin+eng"
    if chosen not in OCR_LANGS:
        raise ValueError(f"lang must be one of {list(OCR_LANGS)}, got {chosen!r}")
    src = open_source(file_path)
    image = src.render(page)
    if image is None:
        raise ModelUnavailable("this page cannot be rendered to an image for OCR")
    ops = ops_for(src.hints(page).skew, strong)
    log: list[str] = []
    try:
        image = clean_image_bytes(image, ops)
        log.extend(ops)
    except ModelUnavailable as exc:
        log.append(f"clean_image: skipped ({exc})")
    client = get_ocr()
    text, conf, boxes = client.ocr(image, chosen)
    lang_label = {"hi": "hi", "en": "en", "mixed": "hi"}[lang_of(text)] if text.strip() else chosen[:2]
    log.append(f"ocr: {getattr(client, 'name', 'ocr')}-{lang_label}" + (" (retry)" if strong else ""))
    return RouteOutcome(
        route=ParseRoute.OCR,
        text=text,
        boxes=boxes,
        lang=lang_of(text) if text.strip() else None,
        confidence=conf,
        ocr_conf=conf,
        status=PageStatus.OK if text.strip() else PageStatus.UNREADABLE,
        log=log,
    )


def ocr_page_route(file_path: str, page: int) -> RouteOutcome:
    """The OCR rung of the ladder (step 3): one pass, then one harder clean-up pass (K3) when the first looks poor.

    Args:
        file_path: see behaviour
        page: page number from 1

    Returns:
        RouteOutcome of the better of the two passes, with the best confidence seen in `ocr_conf`.

    Raises:
        ModelUnavailable: no OCR engine is installed, or the page cannot be rendered.
    """
    first = ocr_page_lang(file_path, page)
    from vakeel_sahayak.ingestion.ladder import acceptable
    from vakeel_sahayak.ingestion.signals import compute_signals

    signals = compute_signals(file_path, page)
    ok, why = acceptable(ParseRoute.OCR, first.text, first.ocr_conf, signals)
    if ok or signals.handwriting_detected:  # handwriting goes straight to the vision model
        return first
    retry = ocr_page_lang(file_path, page, strong=True)
    best = retry if (retry.ocr_conf or 0.0) >= (first.ocr_conf or 0.0) else first
    conf = max(first.ocr_conf or 0.0, retry.ocr_conf or 0.0)
    return best.model_copy(update={"ocr_conf": conf, "confidence": conf, "log": [*first.log, f"ocr: rejected ({why})", *retry.log]})
