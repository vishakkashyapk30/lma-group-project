"""Input-kind recognition K1-K10 (plan §4.1).

K1-K7 are properties of a page and come from its signals. K8 (bundle) is a property of a file once it is split, K9 and
K10 are properties of the file itself (`source.detect_file_kind`), so `file_kind` combines them.
"""

from __future__ import annotations

from vakeel_sahayak.ingestion.signals import PageSignals, passes_text_layer_check
from vakeel_sahayak.ingestion.source import detect_file_kind
from vakeel_sahayak.ingestion.thresholds import threshold
from vakeel_sahayak.schemas.enums import InputKind

HINDI_SHARE_MIN = 0.2  # Devanagari share of a page's letters from which it counts as Hindi or mixed script (K5)


def classify_input_kind(
    signals: PageSignals, script: str | None = None, thresholds: dict[str, float] | None = None
) -> InputKind:
    """Map signals to K1-K7 for a page (plan §4.1). Pure.

    Order of the rules: legacy font (K6), handwriting (K7), phone photo (K4), Hindi or mixed script (K5), then the
    plain cases: a good text layer is K1, a scan whose OCR (or word-list share) is poor is K3, any other scan is K2.

    Args:
        signals: see behaviour
        script: 'devanagari', 'latin' or 'mixed' once known (from the text layer or a first OCR pass)
        thresholds: dev-tuned values; missing entries use the provisional defaults

    Returns:
        InputKind.
    """
    if signals.has_text_layer and signals.legacy_font_pattern:
        return InputKind.K6_LEGACY_HINDI_FONT
    if signals.handwriting_detected:
        return InputKind.K7_HANDWRITING
    good_layer = passes_text_layer_check(signals, thresholds or {})
    if not good_layer and signals.skew_or_perspective:
        return InputKind.K4_PHONE_PHOTO
    hindi_share = signals.devanagari_share is not None and signals.devanagari_share >= HINDI_SHARE_MIN
    if script in ("devanagari", "mixed") or hindi_share:
        return InputKind.K5_HINDI_MIXED
    if good_layer:
        return InputKind.K1_BORN_DIGITAL
    poor_ocr = signals.mean_ocr_conf is not None and signals.mean_ocr_conf < threshold(thresholds, "ocr_conf_min")
    poor_words = signals.dict_word_share is not None and signals.dict_word_share < threshold(thresholds, "dict_word_share_min")
    if poor_ocr or poor_words:
        return InputKind.K3_DEGRADED
    return InputKind.K2_SCANNED


def kind_label(kind: InputKind, signals: PageSignals | None = None) -> str:
    """The short page kind written in the IngestionReport ('born-digital', 'scanned, handwriting', 'photo', ...)."""
    base = {
        InputKind.K1_BORN_DIGITAL: "born-digital",
        InputKind.K2_SCANNED: "scanned",
        InputKind.K3_DEGRADED: "degraded scan",
        InputKind.K4_PHONE_PHOTO: "photo",
        InputKind.K5_HINDI_MIXED: "hindi or mixed script",
        InputKind.K6_LEGACY_HINDI_FONT: "scanned, legacy hindi font",
        InputKind.K7_HANDWRITING: "scanned, handwriting",
        InputKind.K8_BUNDLE: "bundle",
        InputKind.K9_LOCKED_OR_BROKEN: "locked or broken",
        InputKind.K10_NOT_PDF: "not a pdf",
    }[kind]
    if kind == InputKind.K5_HINDI_MIXED and signals is not None:
        base = "born-digital, hindi" if signals.has_text_layer else "scanned, hindi"
    return base


def file_kind(path: str, n_documents: int | None = None) -> InputKind | None:
    """File-level kind: K9 for a locked or broken file, K10 for a non-PDF, K8 for a PDF holding several documents.

    Args:
        path: the file
        n_documents: how many documents splitting found (None before splitting)

    Returns:
        K9, K10, K8, or None for an ordinary single-document PDF.
    """
    kind, _detail = detect_file_kind(path)
    if kind is not None:
        return kind
    return InputKind.K8_BUNDLE if n_documents and n_documents > 1 else None
