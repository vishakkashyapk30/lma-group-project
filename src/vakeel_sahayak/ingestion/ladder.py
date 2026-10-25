"""The page-level routing ladder (plan §4.2).

Text layer, layout parser, clean-up + OCR, vision model, ask counsel; a page climbs only as far as it needs to.
`plan_routes` and `acceptable` are pure functions of the signals and the thresholds, so the route choice can be
tested without any model. `route_page` runs the plan, logs every step, and never guesses: a page that fails every
route is marked UNREADABLE for counsel (K9 files the same way).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from vakeel_sahayak.ingestion.hindi import detect_script_with_lid
from vakeel_sahayak.ingestion.kinds import classify_input_kind
from vakeel_sahayak.ingestion.signals import (
    PageSignals,
    compute_signals,
    passes_text_layer_check,
    text_layer_rejection,
    text_quality,
)
from vakeel_sahayak.ingestion.source import SourceError, open_source
from vakeel_sahayak.ingestion.thresholds import load_thresholds, threshold
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.schemas.enums import InputKind, PageStatus, ParseRoute

LADDER_ORDER: list[ParseRoute] = [
    ParseRoute.TEXT_LAYER,
    ParseRoute.LAYOUT,
    ParseRoute.OCR,
    ParseRoute.VISION,
    ParseRoute.ASK_COUNSEL,
]


# `Switches.munshi_keep_weak_text` (not a named variant): a text layer whose dictionary-word share is between this floor and the
# 85% bar (court orders full of legal vocabulary and names score 67-84%) is kept as a low-confidence read instead of being thrown
# away when no OCR or vision rung can read the page. Below the floor the layer is more garbled than unusual, and is not kept.
WEAK_TEXT_FLOOR = 0.60


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
    tables: list[list[list[str]]] = Field(default_factory=list)  # from the layout route
    ocr_conf: float | None = None  # mean OCR confidence of the page, kept even when vision gave the final text
    signals: PageSignals | None = None  # the page's signals after routing (badges in the UI)
    kind: InputKind | None = None  # K1-K7, or K9 for a locked or broken file
    low_confidence: bool = False  # a rejected text layer kept as a read (`munshi_keep_weak_text`); `confidence` is its dictionary-word share


def weak_layer_read(signals: PageSignals, th: dict[str, float], text: str, log: list[str]) -> RouteOutcome | None:
    """The page's rejected text layer as a low-confidence read, or None when it is not a near miss (share below the floor, legacy font, thin layer).

    Args:
        signals: the page's signals
        th: thresholds
        text: the text layer's text
        log: the route log so far (the reason the layer was rejected is already in it)

    Returns:
        RouteOutcome (route TEXT_LAYER, confidence = word share, low_confidence True), or None.
    """
    rejection = text_layer_rejection(signals, th)
    share = signals.dict_word_share
    if not text.strip() or not rejection or not rejection.startswith("word share") or share is None or share < WEAK_TEXT_FLOOR:
        return None
    note = f"text_layer: kept as a low-confidence read (word share {share:.0%}); counsel to check it against the original"
    return RouteOutcome(route=ParseRoute.TEXT_LAYER, text=text, confidence=round(share, 3), low_confidence=True, log=[*log, note])


def _rank(route: ParseRoute) -> int:
    return LADDER_ORDER.index(route)


def plan_routes(
    signals: PageSignals,
    thresholds: dict[str, float] | None = None,
    max_route: ParseRoute = ParseRoute.ASK_COUNSEL,
    min_route: ParseRoute | None = None,
) -> list[ParseRoute]:
    """The rungs to try for a page, in order, chosen from its signals alone (plan §4.2). Pure.

    - A good text layer gives [TEXT_LAYER], plus LAYOUT when the page has columns or tables.
    - Anything else gives [OCR, VISION, ASK_COUNSEL]; OCR is followed by vision when it fails the check or when
      handwriting is detected.
    - `min_route` drops weaker rungs (a gap re-read with a stronger route); `max_route` cuts stronger ones (baselines
      P1-P3). A cap below OCR on a page with a text layer reads that layer whatever its quality.

    Args:
        signals: the page's signals
        thresholds: dev-tuned values; missing entries use the provisional defaults
        max_route: strongest rung allowed
        min_route: weakest rung allowed

    Returns:
        Ordered rungs; empty when the cap leaves nothing to try.
    """
    if passes_text_layer_check(signals, thresholds or {}):
        plan = [ParseRoute.TEXT_LAYER] + ([ParseRoute.LAYOUT] if signals.layout_complex else [])
    else:
        plan = [ParseRoute.OCR, ParseRoute.VISION, ParseRoute.ASK_COUNSEL]
    if min_route is not None:
        plan = [r for r in LADDER_ORDER if _rank(r) >= _rank(min_route) and _rank(r) >= _rank(ParseRoute.OCR)]
    plan = [r for r in plan if _rank(r) <= _rank(max_route)]
    if not plan and min_route is None and signals.has_text_layer:
        plan = [ParseRoute.TEXT_LAYER]
    return plan


def acceptable(
    route: ParseRoute, text: str, ocr_conf: float | None, signals: PageSignals, thresholds: dict[str, float] | None = None
) -> tuple[bool, str]:
    """Whether a route's result passes the quality check (plan §4.2 steps 3-5). Pure.

    OCR must reach the confidence threshold and must not be a handwriting page; OCR and vision text must reach the
    word-list share and script consistency. Text-layer and layout results are checked by `plan_routes` beforehand.

    Args:
        route: the route that produced the text
        text: its transcript
        ocr_conf: mean OCR confidence (None for other routes)
        signals: the page's signals
        thresholds: dev-tuned values

    Returns:
        (accepted, reason). The reason is empty when accepted.
    """
    if not text.strip():
        return False, "empty transcript"
    if route in (ParseRoute.TEXT_LAYER, ParseRoute.LAYOUT):
        return True, ""
    if route == ParseRoute.OCR:
        if signals.handwriting_detected:
            return False, "handwriting detected"
        need = threshold(thresholds, "ocr_conf_min")
        if ocr_conf is not None and ocr_conf < need:
            return False, f"ocr confidence {ocr_conf:.2f} < {need:.2f}"
    share, consistency = text_quality(text)
    need_share = threshold(thresholds, "dict_word_share_min")
    if share is not None and share < need_share:
        return False, f"word share {share:.0%} < {need_share:.0%}"
    need_cons = threshold(thresholds, "script_consistency_min")
    if consistency is not None and consistency < need_cons:
        return False, f"script consistency {consistency:.0%} < {need_cons:.0%}"
    return True, ""


def _finish(out: RouteOutcome, log: list[str], signals: PageSignals, th: dict[str, float], ocr_conf: float | None) -> RouteOutcome:
    """Attach the route log, the final signals and the input kind to the outcome."""
    share, consistency = text_quality(out.text) if out.text.strip() else (None, None)
    final = signals.model_copy(
        update={
            "mean_ocr_conf": ocr_conf if ocr_conf is not None else signals.mean_ocr_conf,
            "dict_word_share": share if out.text.strip() else signals.dict_word_share,
            "script_consistency": consistency if out.text.strip() else signals.script_consistency,
        }
    )
    hw_max = threshold(th, "handwriting_conf_max")
    if not final.has_text_layer and final.mean_ocr_conf is not None and final.mean_ocr_conf < hw_max:
        final = final.model_copy(update={"handwriting_detected": True})
    script = detect_script_with_lid(out.text) if out.text.strip() else None  # Sarvam /text-lid breaks ties on mixed text when allowed
    return out.model_copy(
        update={
            "log": log,
            "signals": final,
            "ocr_conf": ocr_conf,
            "kind": classify_input_kind(final, script, th),
            "status": out.status if out.text.strip() or out.route == ParseRoute.ASK_COUNSEL else PageStatus.UNREADABLE,
        }
    )


finish_outcome = _finish  # public name for callers that run the rungs themselves (Munshi, through the intake tools)


def _run(route: ParseRoute, file_path: str, page: int, signals: PageSignals) -> RouteOutcome:
    """Run one rung (the route modules are imported here because they import RouteOutcome from this module)."""
    from vakeel_sahayak.ingestion.routes.layout import parse_layout_page
    from vakeel_sahayak.ingestion.routes.ocr import ocr_page_route
    from vakeel_sahayak.ingestion.routes.text_layer import read_text_layer_page
    from vakeel_sahayak.ingestion.routes.vision import vision_route

    if route == ParseRoute.TEXT_LAYER:
        return read_text_layer_page(file_path, page)
    if route == ParseRoute.LAYOUT:
        return parse_layout_page(file_path, page)
    if route == ParseRoute.OCR:
        return ocr_page_route(file_path, page)
    return vision_route(file_path, page)


def route_page(
    file_path: str,
    page: int,
    thresholds: dict[str, float] | None = None,
    max_route: ParseRoute = ParseRoute.ASK_COUNSEL,
) -> RouteOutcome:
    """Climb the ladder only as far as needed: text layer, layout parser, clean-up + OCR, vision model, ask counsel (plan §4.2). Log the route and signals for UI badges.

    Args:
        file_path: see behaviour
        page: page number from 1
        thresholds: dev-tuned values (default: `load_thresholds()`)
        max_route: cap for baselines such as P1-P3

    Returns:
        RouteOutcome with the full route log. A locked or broken file gives route ASK_COUNSEL, status UNREADABLE, kind K9.

    Raises:
        ModelUnavailable: the file is a PDF and PyMuPDF is not installed (nothing can be read).
    """
    return route_page_from(file_path, page, thresholds, max_route, None)


def route_page_from(
    file_path: str,
    page: int,
    thresholds: dict[str, float] | None = None,
    max_route: ParseRoute = ParseRoute.ASK_COUNSEL,
    min_route: ParseRoute | None = None,
    keep_weak: bool = False,
) -> RouteOutcome:
    """`route_page` that starts no lower than `min_route` (a gap re-read with a stronger route, plan §4.3 step 4).

    `keep_weak` (`munshi_keep_weak_text`): a text layer rejected only for a word share of 60-84% is kept, flagged low-confidence, when the
    ladder would otherwise end in ask-counsel. Default False: unchanged.
    """
    th = thresholds if thresholds is not None else load_thresholds()
    try:
        signals = compute_signals(file_path, page)
    except SourceError as exc:
        return RouteOutcome(
            route=ParseRoute.ASK_COUNSEL,
            status=PageStatus.UNREADABLE,
            kind=InputKind.K9_LOCKED_OR_BROKEN,
            log=[f"open: {exc.kind} ({exc})", "ask_counsel: an unlocked or intact copy is needed"],
        )
    try:
        direct = open_source(file_path).direct
    except SourceError:
        direct = False
    if direct:  # DOCX and typed text are read as they are (K10)
        out = _run(ParseRoute.TEXT_LAYER, file_path, page, signals)
        out = out.model_copy(update={"log": ["direct_read: typed text or Word file"]})
        return _finish(out, out.log, signals, th, None).model_copy(update={"kind": InputKind.K10_NOT_PDF})
    log: list[str] = []
    rejection = text_layer_rejection(signals, th)
    if rejection and rejection != "no text layer" and ParseRoute.TEXT_LAYER != min_route:
        log.append(f"text_layer: rejected ({rejection})")
    plan = plan_routes(signals, th, max_route, min_route)
    last: RouteOutcome | None = None
    ocr_conf: float | None = None
    accepted: RouteOutcome | None = None
    for route in plan:
        if route == ParseRoute.ASK_COUNSEL:
            from vakeel_sahayak.ingestion.routes.ask_counsel import ask_counsel_route

            if keep_weak:
                weak = weak_layer_read(signals, th, _run(ParseRoute.TEXT_LAYER, file_path, page, signals).text, log)
                if weak is not None:
                    return _finish(weak, weak.log, signals, th, ocr_conf)
            out = ask_counsel_route(file_path, page)
            return _finish(out, [*log, *out.log], signals, th, ocr_conf)
        try:
            out = _run(route, file_path, page, signals)
            entries = out.log
        except ModelUnavailable as exc:
            log.append(f"{route.value}: unavailable ({exc})")
            continue
        if route == ParseRoute.OCR:
            ocr_conf = out.ocr_conf if out.ocr_conf is not None else out.confidence
        ok, why = acceptable(route, out.text, ocr_conf if route == ParseRoute.OCR else None, signals, th)
        log.extend(entries)
        last = out
        if ok:
            log.append(f"{route.value}: accepted")
            accepted = out
            if route == ParseRoute.TEXT_LAYER and ParseRoute.LAYOUT in plan:
                continue  # the layout parser refines a good text layer with columns or tables
            break
        log.append(f"{route.value}: rejected ({why})")
    if accepted is not None:
        return _finish(accepted, log, signals, th, ocr_conf)
    if last is not None:  # capped below ask_counsel: report the last rung tried
        return _finish(last, [*log, f"stopped at {max_route.value} (route cap)"], signals, th, ocr_conf)
    return _finish(
        RouteOutcome(route=max_route, status=PageStatus.UNREADABLE),
        [*log, "no route could read this page"],
        signals,
        th,
        ocr_conf,
    )
