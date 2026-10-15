"""Input-kind recognition K1-K10 (plan §4.1).

Page-level signals map to K1-K7; K8 (bundle), K9 (locked or broken file) and K10 (not a PDF) are file-level and are
handled by the bundle splitter and the ladder (a file that fails to open is routed to 'ask counsel', never guessed).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.unit.ingestion._helpers import THRESHOLDS
from vakeel_sahayak.ingestion.kinds import classify_input_kind
from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.schemas.enums import InputKind, PageStatus, ParseRoute

K = InputKind


def test_input_kind_enum_is_k1_to_k10_in_plan_order():
    """Plan §4.1 defines exactly ten input kinds, K1..K10."""
    assert [k.name.split("_")[0] for k in InputKind] == [f"K{i}" for i in range(1, 11)]
    assert K.K1_BORN_DIGITAL.value == "K1_BORN_DIGITAL" and K.K9_LOCKED_OR_BROKEN.value == "K9_LOCKED_OR_BROKEN"


# (case id, signals, expected kind). ASSUMPTIONS are marked inline.
CASES = [
    # K1: the text layer covers the page and passes the quality check
    ("born_digital", PageSignals(has_text_layer=True, text_coverage=0.95, dict_word_share=0.95), K.K1_BORN_DIGITAL),
    # K2: no text layer, or a thin one
    ("no_text_layer", PageSignals(has_text_layer=False), K.K2_SCANNED),
    ("no_text_layer_good_ocr", PageSignals(has_text_layer=False, mean_ocr_conf=0.9), K.K2_SCANNED),
    ("thin_text_layer", PageSignals(has_text_layer=True, text_coverage=0.05, dict_word_share=0.9), K.K2_SCANNED),  # ASSUMPTION: 0.05 coverage is 'thin'
    # K3: low OCR confidence or few dictionary words
    ("low_ocr_conf", PageSignals(has_text_layer=False, mean_ocr_conf=0.45), K.K3_DEGRADED),  # ASSUMPTION: 0.45 is below the OCR threshold
    ("few_dictionary_words", PageSignals(has_text_layer=True, text_coverage=0.9, dict_word_share=0.5), K.K3_DEGRADED),
    # K4: perspective skew, page edges visible; ASSUMPTION: skew wins over K2/K3
    ("skew_no_text", PageSignals(has_text_layer=False, skew_or_perspective=True), K.K4_PHONE_PHOTO),
    ("skew_low_conf", PageSignals(has_text_layer=False, skew_or_perspective=True, mean_ocr_conf=0.45), K.K4_PHONE_PHOTO),
    # K5: Hindi or mixed script.
    # RECONCILED: the tests read `script_consistency` as the Devanagari share, but plan §4.2 lists script consistency as a
    # quality signal (do words stay in one script), so 0.9 means a clean page. The Devanagari share is its own field.
    ("hindi_unicode_text_layer", PageSignals(has_text_layer=True, text_coverage=0.95, dict_word_share=0.95, devanagari_share=0.9), K.K5_HINDI_MIXED),
    ("english_text_layer_low_devanagari", PageSignals(has_text_layer=True, text_coverage=0.95, dict_word_share=0.95, devanagari_share=0.02), K.K1_BORN_DIGITAL),
    # K6: a text layer exists but decodes to Latin gibberish; wins over K3 (the gibberish also has a low word share)
    ("legacy_font", PageSignals(has_text_layer=True, text_coverage=0.9, dict_word_share=0.1, legacy_font_pattern=True), K.K6_LEGACY_HINDI_FONT),
    # K7: handwriting regions; wins over K3 (very low OCR confidence)
    ("handwriting", PageSignals(has_text_layer=False, handwriting_detected=True, mean_ocr_conf=0.3), K.K7_HANDWRITING),
]


@pytest.mark.parametrize(("signals", "expected"), [pytest.param(s, e, id=i) for i, s, e in CASES])
def test_signals_map_to_input_kind(signals, expected):
    """Plan §4.1 'How Munshi recognises it' column, one row per case."""
    assert classify_input_kind(signals) == expected


def test_every_page_level_kind_is_reachable():
    """The table above exercises each of K1-K7 at least once."""
    assert {e for _, _, e in CASES} == {K.K1_BORN_DIGITAL, K.K2_SCANNED, K.K3_DEGRADED, K.K4_PHONE_PHOTO,
                                         K.K5_HINDI_MIXED, K.K6_LEGACY_HINDI_FONT, K.K7_HANDWRITING}


_floats = st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
_signals = st.builds(
    PageSignals,
    text_coverage=_floats, mean_ocr_conf=_floats, dict_word_share=_floats, script_consistency=_floats,
    chars_per_area=_floats, legacy_font_pattern=st.booleans(), has_text_layer=st.booleans(),
    handwriting_detected=st.booleans(), skew_or_perspective=st.booleans(),
)


@given(_signals)
def test_page_signals_only_ever_give_page_level_kinds(signals):
    """K8-K10 are file-level, so classifying a single page never returns them."""
    assert classify_input_kind(signals) in {K.K1_BORN_DIGITAL, K.K2_SCANNED, K.K3_DEGRADED, K.K4_PHONE_PHOTO,
                                            K.K5_HINDI_MIXED, K.K6_LEGACY_HINDI_FONT, K.K7_HANDWRITING}


# ---- K9: a file that fails to open is sent to counsel, never guessed (plan §4.1 K9) --------------------------------
def test_corrupt_pdf_routes_to_ask_counsel(require_pymupdf, pdfs):
    """K9: a corrupt PDF cannot be opened, so the ladder asks counsel for an unlocked copy and returns no text."""
    from vakeel_sahayak.ingestion.ladder import route_page

    bad = pdfs.corrupt("broken.pdf")
    out = route_page(str(bad), 1, THRESHOLDS)
    assert out.route == ParseRoute.ASK_COUNSEL
    assert out.status == PageStatus.UNREADABLE
    assert out.text == ""
