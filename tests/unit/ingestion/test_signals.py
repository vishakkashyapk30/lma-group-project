"""Page quality signals and the text-layer check (plan §4.2 step 1, §4.1 K1/K2/K6).

Encodes: a text layer is good only when it covers the page, at least 85% of its words are in English or Hindi
word lists (boundary 0.85 passes, 0.84 fails), and there is no legacy-font pattern; Kruti Dev-style gibberish is
recognised as K6; cheap signals are computed from real PDFs without running expensive models.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.fixtures import pdfgen
from tests.unit.ingestion._helpers import THRESHOLDS
from vakeel_sahayak.ingestion.signals import PageSignals, compute_signals, detect_legacy_font, passes_text_layer_check


def _good(**kw) -> PageSignals:
    base = dict(has_text_layer=True, text_coverage=0.95, dict_word_share=0.95)
    base.update(kw)
    return PageSignals(**base)


# ---- PageSignals defaults (schema facts: pass today) -------------------------------------------------------------
def test_page_signals_defaults_are_unknown_and_false():
    """A fresh PageSignals knows nothing: numeric signals None, all flags False."""
    s = PageSignals()
    assert (s.text_coverage, s.mean_ocr_conf, s.dict_word_share, s.script_consistency, s.chars_per_area) == (None,) * 5
    assert (s.legacy_font_pattern, s.has_text_layer, s.handwriting_detected, s.skew_or_perspective) == (False,) * 4


def test_page_signals_cover_the_six_plan_signals():
    """Plan §4.2 lists coverage, OCR confidence, dictionary-word share, script consistency, chars per area, legacy font."""
    fields = set(PageSignals.model_fields)
    assert {"text_coverage", "mean_ocr_conf", "dict_word_share", "script_consistency", "chars_per_area",
            "legacy_font_pattern"} <= fields


def test_thresholds_yaml_fixes_only_the_word_share(load_yaml):
    """configs/thresholds.yaml pins text_layer_word_share=0.85 (plan §4.2); the rest is tuned on dev."""
    ing = load_yaml("thresholds.yaml")["ingestion"]
    assert ing["text_layer_word_share"] == 0.85


# ---- passes_text_layer_check -------------------------------------------------------------------------------------
def test_good_text_layer_passes():
    """Full coverage, 95% dictionary words, no legacy pattern: the text layer is accepted."""
    assert passes_text_layer_check(_good(), THRESHOLDS) is True


@pytest.mark.parametrize(
    ("share", "expected"),
    [(0.85, True), (0.851, True), (1.0, True), (0.84, False), (0.849, False), (0.0, False)],
)
def test_dictionary_word_share_boundary_is_085(share, expected):
    """>=85% of words must be in the word lists: 0.85 passes, 0.84 fails."""
    assert passes_text_layer_check(_good(dict_word_share=share), THRESHOLDS) is expected


def test_no_text_layer_fails():
    """A page with no text layer never passes, whatever the other numbers say."""
    assert passes_text_layer_check(PageSignals(has_text_layer=False, text_coverage=0.95, dict_word_share=0.99), THRESHOLDS) is False


def test_legacy_font_pattern_fails_even_with_high_word_share():
    """K6: a legacy-font pattern rejects the text layer even at 99% word share."""
    assert passes_text_layer_check(_good(dict_word_share=0.99, legacy_font_pattern=True), THRESHOLDS) is False


def test_low_text_coverage_fails():
    """A text layer covering only 10% of the page is a thin layer (K2), not a good one."""
    # ASSUMPTION: text_coverage_min = 0.5 in THRESHOLDS; 0.1 is well below any sensible minimum.
    assert passes_text_layer_check(_good(text_coverage=0.1), THRESHOLDS) is False


@given(share=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
def test_word_share_property_matches_threshold(share):
    """Property: with everything else good, the check is exactly `share >= 0.85`."""
    assert passes_text_layer_check(_good(dict_word_share=share), THRESHOLDS) is (share >= 0.85)


# ---- detect_legacy_font ------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        pdfgen.KRUTI_DEV_FIR_HEADER,  # 'izFke lwpuk fjiksVZ'
        "lak[;k 112@2024 fnukad 14-08-2024",
        "izFke lwpuk fjiksVZ\nlak[;k 112@2024 fnukad 14-08-2024",
        "/kkjk 318(4) Hkkjrh; U;k; lafgrk",  # Kruti Dev for 'धारा 318(4) भारतीय न्याय संहिता'
    ],
    ids=["header", "case-number-line", "two-lines", "section-line"],
)
def test_kruti_dev_gibberish_is_detected(text):
    """K6: Latin-looking text produced by Kruti Dev-style fonts is flagged."""
    assert detect_legacy_font(text) is True


@pytest.mark.parametrize(
    "text",
    [
        pdfgen.REMAND_PAGE,
        pdfgen.BAIL_ORDER_PAGE,
        pdfgen.ORDER_SHEET_PAGE,
        "The applicant has been in judicial custody since 21.08.2024 and the charge sheet has been filed before the court.",
        "प्रथम सूचना रिपोर्ट",  # real Unicode Devanagari is a good text layer
        "प्रथम सूचना रिपोर्ट सं. 112/2024 दिनांक 14.08.2024",
        "FIR No. 112/2024 प्रथम सूचना रिपोर्ट",  # English plus real Unicode Hindi
        "",
    ],
    ids=["remand-page", "bail-order-page", "order-sheet-page", "english-paragraph", "unicode-hindi", "unicode-hindi-fir-line",
         "english-plus-unicode-hindi", "empty"],
)
def test_normal_text_is_not_legacy_font(text):
    """English order text, real Unicode Devanagari and the empty string are not legacy-font gibberish."""
    assert detect_legacy_font(text) is False


# ---- compute_signals on generated PDFs (needs PyMuPDF) -----------------------------------------------------------
def test_compute_signals_born_digital_pdf(require_pymupdf, pdfs):
    """K1: a born-digital page has a text layer, >=85% dictionary words and no legacy pattern."""
    pdf = pdfs.text("k1.pdf", [pdfgen.REMAND_PAGE])
    s = compute_signals(str(pdf), 1)
    assert s.has_text_layer is True
    assert s.dict_word_share is not None and s.dict_word_share >= 0.85
    assert s.legacy_font_pattern is False
    assert passes_text_layer_check(s, THRESHOLDS) is True


def test_compute_signals_legacy_font_pdf(require_pymupdf, pdfs):
    """K6: the Kruti Dev PDF has a text layer but is flagged legacy_font_pattern and fails the check."""
    pdf = pdfs.legacy("k6.pdf")
    s = compute_signals(str(pdf), 1)
    assert s.has_text_layer is True
    assert s.legacy_font_pattern is True
    assert passes_text_layer_check(s, THRESHOLDS) is False


def test_compute_signals_image_only_pdf(require_pymupdf, pdfs):
    """K2: an image-only page has no text layer."""
    pdf = pdfs.scanned("k2.pdf", 2)
    for page in (1, 2):
        s = compute_signals(str(pdf), page)
        assert s.has_text_layer is False
        assert passes_text_layer_check(s, THRESHOLDS) is False


def test_compute_signals_mixed_bundle_is_per_page(require_pymupdf, pdfs):
    """Signals are per page: a text page and an image page of the same file differ."""
    pdf = pdfs.mixed("mixed.pdf", [pdfgen.REMAND_PAGE, None])
    assert compute_signals(str(pdf), 1).has_text_layer is True
    assert compute_signals(str(pdf), 2).has_text_layer is False
