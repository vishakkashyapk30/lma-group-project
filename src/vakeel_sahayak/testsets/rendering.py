"""Render text into PDFs of kinds K1-K6 (born-digital, scanned, degraded, photo, Hindi, legacy-font) (plan §15.2 T2).

Everything is drawn with PyMuPDF (AGPL-3.0, so it stays an optional extra for the test-set builders; see NOTICE) and Pillow and NumPy for the raster effects.

* K1 born-digital: a text-layer PDF (Times, the PDF base-14 face, so the files stay small).
* K2 scanned: the same pages rasterised (grey, 100 dpi) into an image-only PDF; no text layer.
* K3 degraded scan: K2 pages passed through `degrade.degrade_page` (blur, grain, skew, fading, stamps, JPEG artefacts).
* K4 phone photo: pages on a dark desk with perspective skew, uneven light, a shadow, blur and noise; image-only.
* K5 Hindi born-digital: Devanagari with a Unicode text layer (Noto Serif Devanagari, SIL Open Font Licence; MuPDF shapes the conjuncts and the text layer stays the exact Unicode).
* K6 legacy-font Hindi: the page looks like Hindi (rasterised, shaped), but the text layer is what a Kruti Dev-type font gives an extractor: ASCII
  gibberish (`legacy_encode`, a Kruti-Dev-style mapping, not the exact font table). Real legacy-font PDFs draw vector glyphs; here the visible page is a raster and
  the gibberish layer is invisible, which gives extractors and OCR the same two signals.

Page text is exact by construction: `paginate` fixes what is on each page, and the truth rows of T2 store those strings. Latin text is normalised to
what the base-14 face can draw (`normalise_text`), so the truth is the normalised text. Fonts are looked up on this machine (`VS_FONT_DEVANAGARI` overrides).
"""

from __future__ import annotations

import functools
import io
import os
import unicodedata
from pathlib import Path
from typing import Any

PAGE_W, PAGE_H = 595.0, 842.0
MARGIN = 56.0
DPI = 100
FONT_SIZE_EN, LEADING_EN = 11.0, 14.5
FONT_SIZE_HI, LEADING_HI = 12.0, 19.0
LINES_PER_PAGE_EN, LINES_PER_PAGE_HI = 50, 36
DEVANAGARI_FONTS = [
    "/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSerifDevanagari-Regular.ttf",
]
_QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...", " ": " ", "•": "*", "·": "*"}

# Kruti-Dev-style ASCII mapping (an approximation of the real table: enough for a text layer of Latin gibberish)
LEGACY_MAP = {
    "क": "d", "ख": "[k", "ग": "x", "घ": "?k", "च": "p", "छ": "N", "ज": "t", "झ": ">", "ट": "V", "ठ": "B", "ड": "M", "ढ": "<", "ण": ".k",
    "त": "r", "थ": "Fk", "द": "n", "ध": "/k", "न": "u", "प": "i", "फ": "Q", "ब": "c", "भ": "Hk", "म": "e", "य": ";", "र": "j", "ल": "y",
    "व": "o", "श": "'k", "ष": '"k', "स": "l", "ह": "g", "अ": "v", "आ": "vk", "इ": "b", "ई": "bZ", "उ": "m", "ऊ": "mQ", "ए": ",", "ऐ": ",s",
    "ओ": "vks", "औ": "vkS", "ा": "k", "ि": "f", "ी": "h", "ु": "q", "ू": "w", "े": "s", "ै": "S", "ो": "ks", "ौ": "kS", "ं": "a", "ः": "%",
    "्": "~", "।": ".", "ृ": "`",
}  # fmt: skip


def require_fitz() -> Any:
    """Import PyMuPDF or fail with an installation hint (it is an optional, AGPL extra)."""
    try:
        try:
            import pymupdf as fitz
        except ImportError:  # PyMuPDF before 1.24.3 only has the old name
            import fitz
    except ImportError as exc:  # pragma: no cover
        raise ImportError("PyMuPDF is needed to render test-set PDFs: pip install pymupdf (AGPL-3.0, optional extra 'testsets')") from exc
    return fitz


def devanagari_font() -> str:
    """Path of a Devanagari font on this machine (an OFL Noto face), or FileNotFoundError."""
    candidates = [os.environ.get("VS_FONT_DEVANAGARI", ""), *DEVANAGARI_FONTS]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    raise FileNotFoundError("no Devanagari font found; install fonts-noto-core or set VS_FONT_DEVANAGARI to a .ttf path")


def normalise_text(text: str, lang: str = "en") -> str:
    """Text the renderer can draw: smart punctuation to ASCII, Latin-1 only for English, NFC for Hindi; control characters other than newline dropped."""
    out = []
    for raw in unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")):
        for ch in _QUOTES.get(raw, raw):
            if (ch == "\n" or (ch >= " " and ord(ch) != 127)) and (lang == "hi" or ord(ch) < 256):
                out.append(ch)
    return "".join(out)


def legacy_encode(text: str) -> str:
    """The text layer a Kruti-Dev-type font leaves: every Devanagari character replaced by its ASCII code(s) (digits become ASCII digits), other characters kept."""
    out = []
    for ch in text:
        if "\u0966" <= ch <= "\u096f":
            out.append(str(ord(ch) - 0x0966))
        elif "\u0900" <= ch <= "\u097f":
            out.append(LEGACY_MAP.get(ch, "z"))
        else:
            out.append(ch)
    return "".join(out)


def _measure(text: str, lang: str) -> float:
    """Width in points of `text` as it is drawn (Times for Latin letters, the Devanagari font for the rest)."""
    dev, times = _fonts()
    if lang != "hi":
        return float(times.text_length(text, fontsize=FONT_SIZE_EN))
    return float(sum((times if latin else dev).text_length(t, fontsize=FONT_SIZE_HI) for t, latin in _runs(text)))


def _wrap(paragraph: str, lang: str) -> list[str]:
    limit = PAGE_W - 2 * MARGIN - 4
    lines: list[str] = []
    cur = ""
    for w in paragraph.split():
        trial = f"{cur} {w}".strip()
        if cur and _measure(trial, lang) > limit:
            lines.append(cur)
            cur = w
        else:
            cur = trial
        while _measure(cur, lang) > limit:  # one very long token: cut it where it stops fitting
            k = len(cur)
            while k > 1 and _measure(cur[:k], lang) > limit:
                k -= 1
            lines.append(cur[:k])
            cur = cur[k:]
    return [*lines, cur] if cur or not lines else lines


def paginate(text: str, lang: str = "en") -> list[str]:
    """The page strings of `text` (normalised, wrapped, 50 English or 36 Hindi lines a page); an empty text gives one empty page.

    Args:
        text: see behaviour
        lang: "en" or "hi"

    Returns:
        One string per page, lines joined by newlines.
    """
    per_page = LINES_PER_PAGE_HI if lang == "hi" else LINES_PER_PAGE_EN
    lines: list[str] = []
    for para in normalise_text(text, lang).split("\n"):
        lines.extend(_wrap(para, lang) if para.strip() else [""])
    while lines and not lines[-1]:
        lines.pop()
    pages = ["\n".join(lines[i : i + per_page]) for i in range(0, len(lines), per_page)]
    return pages or [""]


def _runs(line: str) -> list[tuple[str, bool]]:
    """Split a Hindi line into (text, is_latin) runs: Latin letters are drawn with Times because the Devanagari font has no Latin letters."""
    runs: list[tuple[str, bool]] = []
    for ch in line:
        latin = ("A" <= ch <= "Z") or ("a" <= ch <= "z")
        if runs and runs[-1][1] == latin:
            runs[-1] = (runs[-1][0] + ch, latin)
        else:
            runs.append((ch, latin))
    return runs


@functools.lru_cache(maxsize=1)
def _fonts() -> tuple[Any, Any]:
    fitz = require_fitz()
    return fitz.Font(fontfile=devanagari_font()), fitz.Font("tiro")


def _draw_hindi_line(page: Any, fitz: Any, y: float, line: str, invisible: bool) -> None:
    dev, times = _fonts()
    x = MARGIN
    for text, latin in _runs(line):
        name, font = ("tiro", times) if latin else ("vsdev", dev)
        page.insert_text((x, y), text, fontname=name, fontsize=FONT_SIZE_HI, render_mode=3 if invisible else 0)
        x += font.text_length(text, fontsize=FONT_SIZE_HI)


def _draw_text_page(page: Any, text: str, lang: str, *, invisible: bool = False) -> None:
    lines = text.split("\n")
    if lang == "hi":
        fitz = require_fitz()
        page.insert_font(fontname="vsdev", fontfile=devanagari_font())
        y = MARGIN + FONT_SIZE_HI
        for line in lines:
            if line:
                _draw_hindi_line(page, fitz, y, line, invisible)
            y += LEADING_HI
        return
    y = MARGIN + FONT_SIZE_EN
    for line in lines:
        if line:
            page.insert_text((MARGIN, y), line, fontname="tiro", fontsize=FONT_SIZE_EN, render_mode=3 if invisible else 0)
        y += LEADING_EN


def _page_png(text: str, lang: str) -> bytes:
    """One page drawn (vector) and rasterised to a grey PNG at DPI."""
    fitz = require_fitz()
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    _draw_text_page(page, text, lang)
    data = page.get_pixmap(dpi=DPI, colorspace=fitz.csGRAY, alpha=False).tobytes("png")
    doc.close()
    return data


def _finish(doc: Any, out_pdf: str) -> None:
    doc.set_metadata({"producer": "vakeel-sahayak testsets", "creator": "", "title": "", "author": "", "creationDate": "", "modDate": ""})
    Path(out_pdf).parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_pdf, deflate=True, garbage=3)
    doc.close()


def _image_pdf(images: list[bytes], out_pdf: str, hidden_text: list[str] | None = None) -> None:
    fitz = require_fitz()
    doc = fitz.open()
    for i, data in enumerate(images):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        page.insert_image(page.rect, stream=data)
        if hidden_text:
            _draw_text_page(page, hidden_text[i], "en", invisible=True)
    _finish(doc, out_pdf)


def _jpeg(png: bytes, quality: int = 60) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("L").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _perspective_coeffs(src: list[tuple[float, float]], dst: list[tuple[float, float]]) -> list[float]:
    import numpy as np

    a, b = [], []
    for (x, y), (u, v) in zip(src, dst, strict=True):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.extend([u, v])
    return [float(c) for c in np.linalg.solve(np.array(a, dtype=float), np.array(b, dtype=float))]


def _phone_photo(png: bytes, seed: int) -> bytes:
    """A page photographed on a desk: perspective, uneven light, shadow, blur, noise, JPEG."""
    import numpy as np
    from PIL import Image, ImageFilter

    rng = np.random.default_rng(seed)
    page = Image.open(io.BytesIO(png)).convert("L")
    w, h = page.size
    pad = int(0.08 * w)
    canvas = Image.new("L", (w + 2 * pad, h + 2 * pad), int(rng.integers(70, 120)))
    canvas.paste(page, (pad, pad))
    cw, ch = canvas.size
    j = lambda s: float(rng.uniform(-s, s))  # noqa: E731
    dst = [(j(0.03) * cw, j(0.03) * ch), (cw + j(0.03) * cw, j(0.03) * ch), (cw + j(0.03) * cw, ch + j(0.03) * ch), (j(0.03) * cw, ch + j(0.03) * ch)]
    coeffs = _perspective_coeffs(dst, [(0, 0), (cw, 0), (cw, ch), (0, ch)])
    img = canvas.transform((cw, ch), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=90).filter(ImageFilter.GaussianBlur(radius=0.9))
    arr = np.asarray(img, dtype=np.float32)
    yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
    angle = rng.uniform(0, 2 * np.pi)
    ramp = (xx / cw) * np.cos(angle) + (yy / ch) * np.sin(angle)
    light = 0.78 + 0.3 * (ramp - ramp.min()) / (ramp.max() - ramp.min() + 1e-6)
    cx, cy = rng.uniform(0.2, 0.8) * cw, rng.uniform(0.2, 0.8) * ch
    shadow = 1.0 - 0.25 * np.exp(-(((xx - cx) / (0.35 * cw)) ** 2 + ((yy - cy) / (0.2 * ch)) ** 2))
    arr = arr * light * shadow + rng.normal(0, 6.0, size=arr.shape)
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="L")
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=62)
    return buf.getvalue()


def render_pages(pages: list[str], out_pdf: str, kind: str, lang: str = "en", seed: int = 0) -> None:
    """Render page strings as one PDF of kind K1-K6 (the bundle builder's entry point).

    Args:
        pages: page strings (from `paginate`, one document after another)
        out_pdf: output path
        kind: "K1" to "K6"
        lang: "en" or "hi" (K5 and K6 are Hindi)
        seed: seed of the K3 and K4 effects
    """
    from vakeel_sahayak.testsets.degrade import degrade_page

    fitz = require_fitz()
    if kind == "K1" or kind == "K5":
        doc = fitz.open()
        for text in pages:
            _draw_text_page(doc.new_page(width=PAGE_W, height=PAGE_H), text, "hi" if kind == "K5" else lang)
        _finish(doc, out_pdf)
    elif kind == "K2":
        _image_pdf([_jpeg(_page_png(t, lang)) for t in pages], out_pdf)
    elif kind == "K3":
        _image_pdf([degrade_page(_page_png(t, lang), "medium", seed=seed + i) for i, t in enumerate(pages)], out_pdf)
    elif kind == "K4":
        _image_pdf([_phone_photo(_page_png(t, lang), seed + i) for i, t in enumerate(pages)], out_pdf)
    elif kind == "K6":
        _image_pdf([_jpeg(_page_png(t, "hi")) for t in pages], out_pdf, hidden_text=[legacy_encode(t) for t in pages])
    else:
        raise ValueError(f"unknown kind {kind!r}")


def render_born_digital(text: str, out_pdf: str, lang: str = "en") -> None:
    """K1: text-layer PDF (K5 when lang is "hi").

    Args:
        text: see behaviour
        out_pdf: see behaviour
        lang: see behaviour
    """
    render_pages(paginate(text, lang), out_pdf, "K5" if lang == "hi" else "K1", lang)


def render_scanned(text: str, out_pdf: str, lang: str = "en") -> None:
    """K2: image-only PDF.

    Args:
        text: see behaviour
        out_pdf: see behaviour
        lang: see behaviour
    """
    render_pages(paginate(text, lang), out_pdf, "K2", lang)


def render_degraded_scan(text: str, out_pdf: str, lang: str = "en", seed: int = 0) -> None:
    """K3: a scan with blur, grain, skew, fading, stamps and JPEG artefacts.

    Args:
        text: see behaviour
        out_pdf: see behaviour
        lang: see behaviour
        seed: see behaviour
    """
    render_pages(paginate(text, lang), out_pdf, "K3", lang, seed)


def render_legacy_font(text: str, out_pdf: str) -> None:
    """K6: Hindi typed in a Kruti Dev-style font so the text layer decodes to Latin gibberish.

    Args:
        text: see behaviour
        out_pdf: see behaviour
    """
    render_pages(paginate(text, "hi"), out_pdf, "K6", "hi")


def render_phone_photo(text: str, out_pdf: str, seed: int = 0) -> None:
    """K4: perspective skew and uneven light.

    Args:
        text: see behaviour
        out_pdf: see behaviour
        seed: see behaviour
    """
    render_pages(paginate(text, "en"), out_pdf, "K4", "en", seed)
