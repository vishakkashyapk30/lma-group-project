"""`Switches.munshi_keep_weak_text`: a text layer with 60-84% dictionary words is kept as a low-confidence read, not dropped (plan 4.2)."""

from __future__ import annotations

from tests.fixtures import pdfgen
from vakeel_sahayak.ingestion.ladder import WEAK_TEXT_FLOOR, route_page_from, weak_layer_read
from vakeel_sahayak.ingestion.pipeline import read_file
from vakeel_sahayak.ingestion.signals import compute_signals, text_layer_rejection
from vakeel_sahayak.ingestion.thresholds import load_thresholds
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import ParseRoute

TH = load_thresholds()
REAL = "the court heard the application for bail and the accused has been in custody for many days"
ODD = "xqzvbn pqrstv zxcvbm wqzxcv"


def page(real: int, odd: int) -> str:
    words = (REAL.split() * 3)[:real] + (ODD.split() * 6)[:odd]
    return "\n".join(" ".join(words[i : i + 8]) for i in range(0, len(words), 8))


def test_default_is_off():
    assert Switches().munshi_keep_weak_text is False


def test_weak_page_is_dropped_by_default_and_kept_when_asked(require_pymupdf, pdfs):
    pdf = pdfs.text("weak.pdf", [page(30, 10)])  # 75% real words
    s = compute_signals(str(pdf), 1)
    assert WEAK_TEXT_FLOOR <= s.dict_word_share < 0.85, s.dict_word_share
    assert text_layer_rejection(s, TH).startswith("word share")
    base = route_page_from(str(pdf), 1, TH)
    assert base.text == "" and base.route == ParseRoute.ASK_COUNSEL and not base.low_confidence
    kept = route_page_from(str(pdf), 1, TH, keep_weak=True)
    assert kept.low_confidence and kept.text.strip() and kept.route == ParseRoute.TEXT_LAYER
    assert abs(kept.confidence - s.dict_word_share) < 0.01
    assert any("low-confidence read" in step for step in kept.log)


def test_page_below_the_floor_is_not_kept(require_pymupdf, pdfs):
    pdf = pdfs.text("garbled.pdf", [page(12, 24)])  # about a third real words
    out = route_page_from(str(pdf), 1, TH, keep_weak=True)
    assert not out.low_confidence and out.text == ""


def test_good_page_is_unchanged_with_the_switch(require_pymupdf, pdfs):
    pdf = pdfs.text("good.pdf", [pdfgen.REMAND_PAGE])
    a, b = route_page_from(str(pdf), 1, TH), route_page_from(str(pdf), 1, TH, keep_weak=True)
    assert a.model_dump() == b.model_dump() and not b.low_confidence


def test_report_page_route_carries_the_confidence(require_pymupdf, pdfs):
    pdf = pdfs.text("weak2.pdf", [page(30, 10), pdfgen.REMAND_PAGE])
    off = read_file(str(pdf), TH).pages
    on = read_file(str(pdf), TH, keep_weak=True).pages
    assert [p.page_route().confidence for p in off] == [None, None]
    routes = [p.page_route() for p in on]
    assert routes[0].confidence is not None and 0.6 <= routes[0].confidence < 0.85 and routes[1].confidence is None


def test_weak_layer_read_is_pure_and_needs_a_near_miss():
    from vakeel_sahayak.ingestion.signals import PageSignals

    sig = PageSignals(has_text_layer=True, dict_word_share=0.78, text_coverage=1.0, chars_per_area=50.0)
    got = weak_layer_read(sig, TH, "some text", [])
    assert got is not None and got.low_confidence and got.confidence == 0.78
    assert weak_layer_read(sig.model_copy(update={"dict_word_share": 0.4}), TH, "some text", []) is None
    assert weak_layer_read(sig, TH, "   ", []) is None


def test_tooled_ladder_keeps_the_weak_layer_too(require_pymupdf, pdfs):
    from vakeel_sahayak.agents.munshi.toolkit import route_page_with_tools
    from vakeel_sahayak.tools.registry import get_tool

    pdf = pdfs.text("weak3.pdf", [page(30, 10)])

    def call(name, **kw):
        return get_tool(name)(**kw)

    base = route_page_with_tools(call, str(pdf), 1, TH)
    kept = route_page_with_tools(call, str(pdf), 1, TH, keep_weak=True)
    assert base.text == "" and not base.low_confidence
    assert kept.low_confidence and kept.text.strip()
