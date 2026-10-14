"""The page-level routing ladder (plan §4.2): text layer, layout parser, clean-up + OCR, vision model, ask counsel.

Each page climbs only as far as it needs to, so the costly vision model only sees pages that need it. The tests drive
`route_page` with patched `compute_signals` and route functions (see _helpers.patch_ladder) and check the route taken,
the page status and the route log that the UI shows as badges.
"""

from __future__ import annotations

import inspect

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.unit.ingestion._helpers import (
    GIBBERISH_TEXT,
    GOOD_TEXT_SIGNALS,
    HANDWRITING_SIGNALS,
    LEGACY_SIGNALS,
    NO_TEXT_SIGNALS,
    OCR_TEXT,
    TEXT_LAYER_TEXT,
    THRESHOLDS,
    VISION_TEXT,
    patch_ladder,
)
from vakeel_sahayak.ingestion import ladder
from vakeel_sahayak.ingestion.ladder import RouteOutcome, route_page
from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.schemas.enums import PageStatus, ParseRoute

PR = ParseRoute
HEAVY = ("ocr", "vision", "ask_counsel")


def run(monkeypatch, signals, file="bundle.pdf", page=1, max_route=None, thresholds=None, **rig_kw):
    rig = patch_ladder(monkeypatch, signals, **rig_kw)
    kwargs = {} if max_route is None else {"max_route": max_route}
    return route_page(file, page, thresholds or THRESHOLDS, **kwargs), rig


# ---- static facts (pass today) -----------------------------------------------------------------------------------
def test_parse_route_enum_is_the_five_rungs_in_order():
    """Plan §4.2 table: text layer, layout, OCR, vision, ask counsel."""
    assert list(PR) == [PR.TEXT_LAYER, PR.LAYOUT, PR.OCR, PR.VISION, PR.ASK_COUNSEL]
    assert [r.value for r in PR] == ["text_layer", "layout", "ocr", "vision", "ask_counsel"]


def test_route_page_default_cap_is_ask_counsel():
    """Without a cap the ladder may climb all the way to counsel; baselines P1-P3 pass a lower max_route."""
    sig = inspect.signature(route_page)
    assert list(sig.parameters) == ["file_path", "page", "thresholds", "max_route"]
    assert sig.parameters["max_route"].default == PR.ASK_COUNSEL


def test_route_outcome_defaults():
    """A RouteOutcome starts OK with empty text and an empty log (the ladder fills the log)."""
    out = RouteOutcome(route=PR.OCR)
    assert (out.text, out.status, out.log, out.boxes, out.confidence) == ("", PageStatus.OK, [], [], None)


def test_every_route_function_takes_file_and_page():
    """Each rung is a function (file_path, page) -> RouteOutcome, one module per rung (plan §4.2)."""
    import importlib

    for mod, fn in [("text_layer", "read_text_layer_page"), ("layout", "parse_layout_page"), ("ocr", "ocr_page_route"),
                    ("vision", "vision_route"), ("ask_counsel", "ask_counsel_route")]:
        f = getattr(importlib.import_module(f"vakeel_sahayak.ingestion.routes.{mod}"), fn)
        assert list(inspect.signature(f).parameters) == ["file_path", "page"], fn


# ---- the main table: (signals, ocr_conf, vision_ok) -> (final route, status, rungs called) ------------------------
LADDER_TABLE = [
    # id, signals, ocr_conf, vision_ok, final_route, status, must_call, must_not_call
    ("good_text_layer", GOOD_TEXT_SIGNALS, 0.9, True, PR.TEXT_LAYER, PageStatus.OK, ["text_layer"], ["ocr", "vision", "ask_counsel"]),
    ("text_layer_exactly_85pct", GOOD_TEXT_SIGNALS.model_copy(update={"dict_word_share": 0.85}), 0.9, True, PR.TEXT_LAYER, PageStatus.OK, ["text_layer"], ["ocr", "vision", "ask_counsel"]),
    ("text_layer_84pct_falls_to_ocr", GOOD_TEXT_SIGNALS.model_copy(update={"dict_word_share": 0.84}), 0.9, True, PR.OCR, PageStatus.OK, ["ocr"], ["vision", "ask_counsel"]),
    ("legacy_font_to_ocr", LEGACY_SIGNALS, 0.9, True, PR.OCR, PageStatus.OK, ["ocr"], ["vision", "ask_counsel"]),
    ("legacy_font_high_word_share_still_ocr", LEGACY_SIGNALS.model_copy(update={"dict_word_share": 0.99}), 0.9, True, PR.OCR, PageStatus.OK, ["ocr"], ["vision", "ask_counsel"]),
    ("no_text_layer_to_ocr", NO_TEXT_SIGNALS, 0.9, True, PR.OCR, PageStatus.OK, ["ocr"], ["vision", "ask_counsel"]),
    ("ocr_conf_at_threshold_stays_ocr", NO_TEXT_SIGNALS, 0.6, True, PR.OCR, PageStatus.OK, ["ocr"], ["vision", "ask_counsel"]),
    ("ocr_conf_just_below_escalates", NO_TEXT_SIGNALS, 0.59, True, PR.VISION, PageStatus.OK, ["ocr", "vision"], ["ask_counsel"]),
    ("low_ocr_conf_vision_reads", NO_TEXT_SIGNALS, 0.42, True, PR.VISION, PageStatus.OK, ["ocr", "vision"], ["ask_counsel"]),
    ("low_ocr_conf_vision_fails_asks_counsel", NO_TEXT_SIGNALS, 0.42, False, PR.ASK_COUNSEL, PageStatus.UNREADABLE, ["ocr", "vision", "ask_counsel"], []),
    ("handwriting_goes_to_vision", HANDWRITING_SIGNALS, 0.9, True, PR.VISION, PageStatus.OK, ["vision"], ["ask_counsel"]),
    ("handwriting_vision_fails_asks_counsel", HANDWRITING_SIGNALS, 0.9, False, PR.ASK_COUNSEL, PageStatus.UNREADABLE, ["vision", "ask_counsel"], []),
]


@pytest.mark.parametrize(
    ("signals", "ocr_conf", "vision_ok", "final", "status", "must_call", "must_not_call"),
    [pytest.param(*row[1:], id=row[0]) for row in LADDER_TABLE],
)
def test_ladder_table(monkeypatch, signals, ocr_conf, vision_ok, final, status, must_call, must_not_call):
    """Plan §4.2 table: the route taken and the final status for each combination of signals and read quality."""
    out, rig = run(monkeypatch, signals, ocr_conf=ocr_conf, vision_ok=vision_ok)
    assert out.route == final
    assert out.status == status
    for name in must_call:
        assert rig.was_called(name), f"{name} should have run; ran {rig.called}"
    for name in must_not_call:
        assert not rig.was_called(name), f"{name} must not run; ran {rig.called}"


def test_good_text_layer_keeps_the_text_layer_text(monkeypatch):
    """A good text layer page returns its own text untouched (step 1) and never touches OCR or the vision model."""
    out, rig = run(monkeypatch, GOOD_TEXT_SIGNALS)
    assert out.route == PR.TEXT_LAYER
    assert out.text == TEXT_LAYER_TEXT
    assert rig.count("text_layer") == 1
    assert not any(rig.was_called(n) for n in HEAVY)


def test_good_text_layer_with_tables_may_use_layout_but_never_ocr(monkeypatch):
    """Step 2: a good text layer page with columns or tables may go to the layout parser, but not down to OCR or vision."""
    # ASSUMPTION: PageSignals has no 'has_tables' flag, so the ladder decides itself whether to call the layout parser.
    # We only pin what the plan fixes: the route is TEXT_LAYER or LAYOUT, the text layer text is kept, no OCR or vision.
    out, rig = run(monkeypatch, GOOD_TEXT_SIGNALS)
    assert out.route in {PR.TEXT_LAYER, PR.LAYOUT}
    assert TEXT_LAYER_TEXT in out.text
    assert out.status == PageStatus.OK
    assert not any(rig.was_called(n) for n in HEAVY)


def test_layout_rung_is_below_ocr_and_above_text_layer_under_a_cap(monkeypatch):
    """max_route=TEXT_LAYER keeps the layout parser out; the text layer text is returned as is."""
    out, rig = run(monkeypatch, GOOD_TEXT_SIGNALS, max_route=PR.TEXT_LAYER)
    assert out.route == PR.TEXT_LAYER
    assert not rig.was_called("layout")


# ---- legacy font (K6) --------------------------------------------------------------------------------------------
def test_legacy_font_rejects_text_layer_and_logs_it(monkeypatch):
    """K6: the text layer is rejected with a 'legacy font' log entry, and the gibberish never reaches the output."""
    out, rig = run(monkeypatch, LEGACY_SIGNALS, text_layer_text=GIBBERISH_TEXT)
    assert out.route == PR.OCR
    assert any("legacy font" in entry.lower() for entry in out.log), out.log
    assert out.text == OCR_TEXT
    assert "izFke" not in out.text and "lwpuk" not in out.text


def test_legacy_font_text_layer_text_never_used_even_when_ocr_is_poor(monkeypatch):
    """Even if OCR is poor and vision is needed, the Kruti Dev gibberish is never the answer."""
    out, _ = run(monkeypatch, LEGACY_SIGNALS, text_layer_text=GIBBERISH_TEXT, ocr_conf=0.3)
    assert out.route == PR.VISION
    assert out.text == VISION_TEXT
    assert "izFke" not in out.text


# ---- escalation, caps and the costly model -----------------------------------------------------------------------
def test_vision_failure_ends_with_ask_counsel_unreadable_and_no_guess(monkeypatch):
    """Step 5: when the vision transcript also fails, the page goes to counsel as UNREADABLE with no text."""
    out, rig = run(monkeypatch, NO_TEXT_SIGNALS, ocr_conf=0.2, vision_ok=False)
    assert out.route == PR.ASK_COUNSEL
    assert out.status == PageStatus.UNREADABLE
    assert out.text == ""
    assert rig.called.index("ocr") < rig.called.index("vision") < rig.called.index("ask_counsel")


@pytest.mark.parametrize(
    ("cap", "signals", "ocr_conf", "never"),
    [
        pytest.param(PR.TEXT_LAYER, NO_TEXT_SIGNALS, 0.2, ["ocr", "vision", "ask_counsel"], id="P1_text_layer_only"),
        pytest.param(PR.OCR, NO_TEXT_SIGNALS, 0.2, ["vision", "ask_counsel"], id="P2_ocr_cap_low_conf"),
        pytest.param(PR.OCR, HANDWRITING_SIGNALS, 0.9, ["vision", "ask_counsel"], id="P2_ocr_cap_handwriting"),
        pytest.param(PR.VISION, NO_TEXT_SIGNALS, 0.2, ["ask_counsel"], id="vision_cap_stops_before_counsel"),
    ],
)
def test_max_route_caps_escalation(monkeypatch, cap, signals, ocr_conf, never):
    """max_route stops the climb: baselines such as P1-P3 never reach the rungs above their cap."""
    out, rig = run(monkeypatch, signals, ocr_conf=ocr_conf, vision_ok=False, max_route=cap)
    for name in never:
        assert not rig.was_called(name), f"{name} ran despite cap {cap}: {rig.called}"
    assert out.route == cap


@given(
    share=st.floats(min_value=0.85, max_value=1.0, allow_nan=False),
    coverage=st.floats(min_value=0.5, max_value=1.0, allow_nan=False),
)
def test_vision_model_never_sees_a_good_text_layer_page(share, coverage):
    """Property: for any page whose text layer passes the check, OCR, vision and ask-counsel are never called."""
    mp = pytest.MonkeyPatch()
    try:
        out, rig = run(mp, PageSignals(has_text_layer=True, text_coverage=coverage, dict_word_share=share))
    finally:
        mp.undo()
    assert out.route in {PR.TEXT_LAYER, PR.LAYOUT}
    assert not any(rig.was_called(n) for n in HEAVY)


def test_route_log_lists_each_rung_tried_in_order(monkeypatch):
    """The log shows the rungs tried, in order: text layer (rejected), then OCR, then vision (plan §4.6 example)."""
    out, _ = run(monkeypatch, LEGACY_SIGNALS, ocr_conf=0.4)
    log = [e.lower() for e in out.log]
    idx = {name: next(i for i, e in enumerate(log) if name in e) for name in ("text_layer", "ocr", "vision")}
    assert idx["text_layer"] < idx["ocr"] < idx["vision"], out.log


def test_route_log_of_a_good_page_names_only_the_text_layer(monkeypatch):
    """A good text layer page's log mentions the text layer and none of the costly rungs."""
    out, _ = run(monkeypatch, GOOD_TEXT_SIGNALS)
    joined = " ".join(out.log).lower()
    assert "text_layer" in joined
    assert "ocr" not in joined and "vision" not in joined


def test_page_and_file_are_passed_through_to_the_routes(monkeypatch):
    """The ladder hands the same file path and page number to every rung it calls."""
    _, rig = run(monkeypatch, NO_TEXT_SIGNALS, file="/cases/bundle_1.pdf", page=7, ocr_conf=0.2, vision_ok=False)
    routed = [(f, p) for name, f, p in rig.calls if name != "signals"]
    assert routed and set(routed) == {("/cases/bundle_1.pdf", 7)}


def test_ladder_module_exposes_route_page_and_outcome():
    """`vakeel_sahayak.ingestion.ladder` is where RouteOutcome and route_page live (routes import RouteOutcome from it)."""
    assert ladder.RouteOutcome is RouteOutcome and callable(ladder.route_page)


# ---- ask_counsel route (never guess) -----------------------------------------------------------------------------
def test_ask_counsel_route_returns_unreadable_without_text():
    """Plan §4.2 step 5: the page is shown to counsel; the route itself returns no text and marks the page UNREADABLE."""
    # ASSUMPTION: the route does not open the file; the question is raised by the agent (grouped, see test_gaps_report).
    from vakeel_sahayak.ingestion.routes.ask_counsel import ask_counsel_route

    out = ask_counsel_route("bundle.pdf", 3)
    assert out.route == PR.ASK_COUNSEL
    assert out.status == PageStatus.UNREADABLE
    assert out.text == ""
