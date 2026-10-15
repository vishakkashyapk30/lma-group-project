"""Page quality signals (plan §4.2).

Cheap, model-free signals per page: text-layer coverage, the share of words found in English or Hindi word lists,
legacy-Hindi-font detection, script consistency, characters per page area and a handwriting flag. Mean OCR confidence
is filled in when a page has been through OCR. Thresholds come from configs/thresholds.yaml (`ingestion.thresholds`).
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from vakeel_sahayak.ingestion.source import open_source
from vakeel_sahayak.ingestion.thresholds import threshold
from vakeel_sahayak.ingestion.wordlists import word_share

MIN_LAYER_CHARS = 20  # fewer characters than this is not a text layer
_AREA_UNIT = 10_000.0  # chars_per_area is characters per 10,000 square points

_LATIN_WORD = re.compile(r"[A-Za-z]+")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")
# Kruti Dev and similar legacy fonts store Devanagari as Latin letters: 'ds' is के, 'esa' is में, 'gS' is है, 'dk' is का.
_KRUTI_MARKERS = frozenset(
    "dk ds dh dks esa gS gSa ls ij vkSj rFkk fd ftl ugha Fkk Fkh gks gksxk dj bl blh bldk vkns'k izFke lwpuk fjiksVZ "
    "fo:) yk;k fn;k tkp lsa uke irk vuqlkj /kkjk fnukad U;k;ky; vfHk;qDr tekur ejk".split()
)
_EN_STOP = frozenset(
    "the of and to in is was on for that this with by as at an be are from it his her he she not or which has had have "
    "been were will would may shall under before after".split()
)
_BROKEN_ENCODING = re.compile(r"\(cid:\d+\)|[-]")
_MID_WORD_SYMBOLS = re.compile(r"[A-Za-z][\[\]{}^~`@;][A-Za-z]|[A-Za-z]\]|\[[A-Za-z]")


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
    devanagari_share: float | None = None  # share of the page's letters in Devanagari (Hindi or mixed script, K5)
    layout_complex: bool = False  # the text looks like columns or a table (plan §4.2 step 2)


def detect_legacy_font(text: str) -> bool:
    """K6: text layer decodes to Latin gibberish from Kruti Dev-style fonts.

    The text is flagged when it is full of Kruti Dev marker words ('ds', 'esa', 'gS') or symbols inside words and has
    almost no English function words, or when it holds unmapped glyphs ('(cid:12)', private-use characters).

    Args:
        text: text layer of a page

    Returns:
        bool.
    """
    stripped = text.strip()
    if not stripped:
        return False
    letters = sum(c.isalpha() for c in stripped) or 1
    if len(_BROKEN_ENCODING.findall(stripped)) / max(1, len(stripped.split())) >= 0.1 and letters:
        return True
    tokens = stripped.split()
    if len(tokens) < 2 or len(_DEVANAGARI.findall(stripped)) / letters > 0.2:
        return False
    words = [t.strip(".,;:!?()\"'") for t in tokens]
    stop_share = sum(w.lower() in _EN_STOP for w in words) / len(words)
    if stop_share >= 0.12:
        return False
    marker_share = sum(w in _KRUTI_MARKERS for w in words) / len(words)
    symbol_share = sum(bool(_MID_WORD_SYMBOLS.search(t)) for t in tokens) / len(tokens)
    if len(tokens) < 8:  # a short line (a header, a number line) needs a clearer pattern
        return marker_share >= 0.25 or symbol_share >= 0.20
    return marker_share >= 0.06 or symbol_share >= 0.10


def _devanagari_share(text: str) -> float | None:
    """Share of the letters that are Devanagari (None without letters)."""
    deva = len(_DEVANAGARI.findall(text))
    letters = deva + len(_LATIN.findall(text))
    return round(deva / letters, 4) if letters else None


def script_consistency(text: str) -> float | None:
    """Share of words that stay in one script (a word mixing Latin and Devanagari letters is a sign of bad OCR).

    Args:
        text: page text

    Returns:
        0 to 1, or None when the text has no letters.
    """
    words = [w for w in text.split() if _LATIN.search(w) or _DEVANAGARI.search(w)]
    if not words:
        return None
    mixed = sum(bool(_LATIN.search(w)) and bool(_DEVANAGARI.search(w)) for w in words)
    return 1.0 - mixed / len(words)


def text_quality(text: str) -> tuple[float | None, float | None]:
    """(word-list share, script consistency) of a transcript, the checks an OCR or vision result must pass."""
    return word_share(text), script_consistency(text)


def signals_from_text(text: str | None, area: float, coverage: float) -> PageSignals:
    """Signals of a page's text layer (no I/O; `compute_signals` feeds it from a source)."""
    clean = (text or "").strip()
    if len(clean) < MIN_LAYER_CHARS:
        return PageSignals(has_text_layer=False, text_coverage=0.0, chars_per_area=0.0)
    return PageSignals(
        has_text_layer=True,
        text_coverage=round(coverage, 4),
        chars_per_area=round(len(clean) / (area / _AREA_UNIT), 3),
        dict_word_share=word_share(clean),
        script_consistency=script_consistency(clean),
        legacy_font_pattern=detect_legacy_font(clean),
        devanagari_share=_devanagari_share(clean),
    )


def compute_signals(file_path: str, page: int) -> PageSignals:
    """Compute the cheap signals for one page without running expensive models.

    Args:
        file_path: see behaviour
        page: page number from 1

    Returns:
        PageSignals.

    Raises:
        SourceError: K9, the file is locked or broken.
        IndexError: for a page outside the file.
    """
    src = open_source(file_path)
    text = src.text_layer(page)
    signals = signals_from_text(text, src.page_area(page), src.text_coverage(page))
    hints = src.hints(page)
    return signals.model_copy(
        update={
            "handwriting_detected": hints.handwriting,
            "skew_or_perspective": hints.skew,
            "layout_complex": hints.layout_complex and signals.has_text_layer,
        }
    )


def text_layer_rejection(signals: PageSignals, thresholds: dict[str, float] | None = None) -> str | None:
    """Why a page's text layer is not good enough, or None when it passes (plan §4.2 step 1). Pure.

    Args:
        signals: see behaviour
        thresholds: see behaviour

    Returns:
        A short reason such as 'legacy font' or 'word share 62% < 85%'; None when the layer is good; 'no text layer'
        when the page has none.
    """
    if not signals.has_text_layer:
        return "no text layer"
    if signals.legacy_font_pattern:
        return "legacy font"
    min_cov = threshold(thresholds, "text_coverage_min")
    if signals.text_coverage is not None and signals.text_coverage < min_cov:
        return f"thin text layer (coverage {signals.text_coverage:.0%} < {min_cov:.0%})"
    min_density = threshold(thresholds, "chars_per_area_min")
    if signals.chars_per_area is not None and signals.chars_per_area < min_density:
        return f"thin text layer ({signals.chars_per_area:.1f} chars per area unit < {min_density:g})"
    need = threshold(thresholds, "text_layer_word_share")
    if signals.dict_word_share is None or signals.dict_word_share < need:
        got = "none" if signals.dict_word_share is None else f"{signals.dict_word_share:.0%}"
        return f"word share {got} < {need:.0%}"
    return None


def passes_text_layer_check(signals: PageSignals, thresholds: dict[str, float]) -> bool:
    """Text layer covers the page, >=85% of words in English or Hindi word lists, and no legacy-font pattern (plan §4.2 step 1).

    Args:
        signals: see behaviour
        thresholds: see behaviour

    Returns:
        bool.
    """
    return text_layer_rejection(signals, thresholds) is None
