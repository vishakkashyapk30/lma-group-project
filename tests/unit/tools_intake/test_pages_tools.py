"""Page tools: inspect_page, read_text_layer, parse_layout, clean_image (plan §4.2, §4.3).

Argument validation (page < 1, missing file, unknown clean-up op) is checked on every tool; behaviour is checked with the
real PyMuPDF text layer on generated PDFs, or with the route functions patched.
"""

from __future__ import annotations

import pytest

from tests.fixtures import pdfgen
from tests.unit.tools_intake._helpers import assert_rejects, patch_everywhere
from vakeel_sahayak.ingestion.ladder import RouteOutcome
from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.schemas.enums import ParseRoute
from vakeel_sahayak.tools.intake.pages import clean_image, inspect_page, parse_layout, read_text_layer
from vakeel_sahayak.tools.types import LayoutResult, TextLayerResult

PAGE_TOOLS = [inspect_page, read_text_layer, parse_layout]


@pytest.fixture()
def pdf(pdfs):
    return str(pdfs.text("order.pdf", [pdfgen.REMAND_PAGE, pdfgen.BAIL_ORDER_PAGE]))


@pytest.mark.parametrize("tool", PAGE_TOOLS, ids=lambda t: t.__name__)
@pytest.mark.parametrize("page", [0, -1])
def test_page_below_one_is_rejected(tool, pdf, page):
    """Pages are 1-based: page 0 or negative is rejected with ValueError or a ToolError."""
    assert_rejects(tool, pdf, page)


@pytest.mark.parametrize("tool", PAGE_TOOLS, ids=lambda t: t.__name__)
def test_missing_file_is_rejected(tool, tmp_path):
    """A file that does not exist is rejected, not guessed at."""
    assert_rejects(tool, str(tmp_path / "nope.pdf"), 1)


@pytest.mark.parametrize("tool", [inspect_page, read_text_layer], ids=lambda t: t.__name__)
def test_page_beyond_last_is_rejected(tool, pdf, require_pymupdf):
    """Page 3 of a 2-page file is rejected."""
    assert_rejects(tool, pdf, 3)


def test_inspect_page_returns_signals_from_the_signal_module(monkeypatch, pdf):
    """inspect_page is a thin wrapper over ingestion.signals.compute_signals."""
    expected = PageSignals(has_text_layer=True, text_coverage=0.9, dict_word_share=0.93)
    patch_everywhere(monkeypatch, "vakeel_sahayak.ingestion.signals", "compute_signals", lambda f, p: expected)
    assert inspect_page(pdf, 1) == expected


def test_read_text_layer_returns_the_page_text(pdf, require_pymupdf):
    """K1: the text layer of page 1 is the remand order text, page 2 the bail order text."""
    first, second = read_text_layer(pdf, 1), read_text_layer(pdf, 2)
    assert isinstance(first, TextLayerResult)
    assert "REMAND ORDER" in first.text and "BAIL" not in first.text
    assert "ORDER ON BAIL APPLICATION" in second.text


def test_read_text_layer_of_image_page_is_empty(pdfs, require_pymupdf):
    """K2: an image-only page has no text layer, so the text is empty (the ladder then goes to OCR)."""
    scanned = str(pdfs.scanned("scan.pdf", 1))
    assert read_text_layer(scanned, 1).text.strip() == ""


def test_parse_layout_wraps_the_layout_route(monkeypatch, pdf):
    """parse_layout returns a LayoutResult carrying the layout route's text."""
    outcome = RouteOutcome(route=ParseRoute.LAYOUT, text="Custody certificate | days | 167")
    patch_everywhere(monkeypatch, "vakeel_sahayak.ingestion.routes.layout", "parse_layout_page", lambda f, p: outcome)
    result = parse_layout(pdf, 1)
    assert isinstance(result, LayoutResult)
    assert result.text == "Custody certificate | days | 167"


# ---- clean_image -------------------------------------------------------------------------------------------------
def test_clean_image_rejects_unknown_operation():
    """ops must be a subset of deskew, dewarp, denoise; 'rotate' is rejected."""
    assert_rejects(clean_image, b"not-really-an-image", ["rotate"])


def test_clean_image_rejects_empty_image():
    """An empty byte string is not an image."""
    assert_rejects(clean_image, b"", ["deskew"])


@pytest.mark.models
def test_clean_image_default_returns_bytes_for_a_real_image():
    """With real image libraries, clean_image(None ops) returns image bytes (needs OpenCV)."""
    pytest.importorskip("cv2")
    out = clean_image(pdfgen_png())
    assert isinstance(out, bytes) and out


def pdfgen_png() -> bytes:
    """A tiny valid 8x8 grayscale PNG built with zlib (no imaging library)."""
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes((x * 32) % 256 for x in range(8)) for _ in range(8))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
