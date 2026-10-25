"""Page sources: one abstraction over PDFs, DOCX, images and the offline plain-text stand-in (plan §4.1 K9, K10, §4.2).

Everything in `ingestion/` reads pages through `PageSource`, so the heavy backends stay optional:

- `PdfSource` uses PyMuPDF, imported lazily. Without it a PDF that looks fine raises `ModelUnavailable`.
- `DocxSource` uses python-docx (lazy). `ImageSource` reads JPG/PNG/HEIC files as one page without a text layer.
- `PlainTextSource` is the deterministic offline stand-in for a PDF: a text file (any extension, no `%PDF` header) whose
  pages are separated by a form feed. A page may start with `#!page layer=off conf=0.8 hw skew vision=off` to say what
  a scan looks like; text after a `#!pixels` line is what OCR would read from the page image. See `render`.

A locked or broken file raises `SourceError` (K9): Munshi asks counsel and never guesses.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.pipelines.text_utils import paragraph_blocks
from vakeel_sahayak.schemas.enums import InputKind

A4_AREA = 595.0 * 842.0  # points squared
FIXTURE_MAGIC = b"VSIMG1\n"  # header of the offline stand-in for page images
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".webm"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".heic", ".heif"}
PHOTO_SUFFIXES = {".jpg", ".jpeg", ".heic", ".heif"}  # camera formats: treated as phone photos (K4)
DIRECT_TEXT_SUFFIXES = {".txt", ".md"}  # typed text read directly (K10)


class SourceError(Exception):
    """The file cannot be opened as pages.

    Attributes:
        kind: 'locked' (password), 'broken' (corrupt, empty or missing) or 'unsupported'.
    """

    def __init__(self, kind: str, message: str) -> None:
        """Remember the failure kind."""
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class PageHints:
    """Cheap per-page hints a source can give without OCR."""

    handwriting: bool = False
    skew: bool = False
    layout_complex: bool = False


class PageSource(ABC):
    """Pages of one file (page numbers start at 1)."""

    kind: str = "pdf"
    direct: bool = False  # True for DOCX and typed text: read directly, no quality ladder (plan §4.1 K10)

    def __init__(self, path: str) -> None:
        """Remember the path."""
        self.path = path

    @property
    @abstractmethod
    def page_count(self) -> int:
        """Number of pages."""

    @abstractmethod
    def text_layer(self, page: int) -> str | None:
        """The embedded text of a page, or None when the page has no text layer."""

    def text_boxes(self, page: int) -> list[list[float]]:
        """One [x0, y0, x1, y1] box per text block in reading order (empty when unknown)."""
        return []

    def text_coverage(self, page: int) -> float:
        """Share of the page area covered by text blocks, 0 to 1."""
        return 0.0

    def page_area(self, page: int) -> float:
        """Page area in points squared."""
        return A4_AREA

    def render(self, page: int, dpi: int = 200) -> bytes | None:
        """The page as an image for OCR and the vision model, or None when it cannot be rendered."""
        return None

    def hints(self, page: int) -> PageHints:
        """Handwriting, skew and layout hints."""
        return PageHints()

    def close(self) -> None:
        """Release file handles."""

    def check_page(self, page: int) -> None:
        """Raise IndexError for a page outside 1..page_count."""
        if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= self.page_count:
            raise IndexError(f"page {page!r} is outside 1..{self.page_count}")


_TABLE_ROW = re.compile(r"\S(?:\s{3,}|\t|\s\|\s)\S")


def looks_tabular(text: str) -> bool:
    """True when at least three lines look like table rows (columns separated by wide gaps, tabs or bars)."""
    return sum(1 for line in text.splitlines() if _TABLE_ROW.search(line)) >= 3


# ---------------------------------------------------------------- plain-text stand-in


@dataclass
class _FixturePage:
    layer: str | None
    pixels: str
    conf: float = 0.9
    handwriting: bool = False
    skew: bool = False
    vision_ok: bool = True


def _parse_fixture_page(block: str) -> _FixturePage:
    """Read one form-feed separated page of the plain-text format (see the module docstring)."""
    lines = block.split("\n")
    opts: dict[str, str] = {}
    if lines and lines[0].startswith("#!page"):
        for token in lines[0].split()[1:]:
            key, _, value = token.partition("=")
            opts[key] = value or "1"
        lines = lines[1:]
    body = "\n".join(lines)
    layer: str | None = body
    pixels = body
    if "#!pixels" in body:
        layer, _, pixels = body.partition("#!pixels")
        layer, pixels = layer.rstrip("\n"), pixels.lstrip("\n")
    if opts.get("layer") == "off":
        layer = None
    elif layer is not None and not layer.strip():
        layer = None
    return _FixturePage(
        layer=layer,
        pixels=pixels,
        conf=float(opts.get("conf", 0.9)),
        handwriting="hw" in opts,
        skew="skew" in opts,
        vision_ok=opts.get("vision") != "off",
    )


class PlainTextSource(PageSource):
    """Offline stand-in for a PDF: text pages separated by form feeds (see the module docstring)."""

    kind = "text"

    def __init__(self, path: str, content: str) -> None:
        """Split the content into pages."""
        super().__init__(path)
        self.direct = Path(path).suffix.lower() in DIRECT_TEXT_SUFFIXES
        blocks = content.replace("\r\n", "\n").split("\f")
        while len(blocks) > 1 and not blocks[-1].strip():
            blocks.pop()  # a trailing form feed does not start a page
        self._pages = [_parse_fixture_page(b) for b in blocks]

    @property
    def page_count(self) -> int:
        """Number of form-feed separated pages."""
        return len(self._pages)

    def text_layer(self, page: int) -> str | None:
        """The page's visible text, or None for a scan."""
        self.check_page(page)
        return self._pages[page - 1].layer

    def text_boxes(self, page: int) -> list[list[float]]:
        """Synthetic boxes, one per paragraph block, stacked down the page."""
        text = self.text_layer(page) or ""
        boxes, y = [], 72.0
        for block in paragraph_blocks(text):
            height = 14.0 * (1 + len(block) // 90)
            boxes.append([72.0, y, 523.0, y + height])
            y += height + 8.0
        return boxes

    def text_coverage(self, page: int) -> float:
        """Characters over a typical full page of 1800."""
        return min(1.0, len(self.text_layer(page) or "") / 1800.0)

    def render(self, page: int, dpi: int = 200) -> bytes | None:
        """A stand-in image: the fixture magic plus the page's pixel text, confidence and flags as JSON."""
        self.check_page(page)
        p = self._pages[page - 1]
        payload = {"text": p.pixels, "conf": p.conf, "hw": p.handwriting, "vision_ok": p.vision_ok}
        return FIXTURE_MAGIC + json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def hints(self, page: int) -> PageHints:
        """Handwriting, skew and table hints from the directive and the text."""
        self.check_page(page)
        p = self._pages[page - 1]
        return PageHints(handwriting=p.handwriting, skew=p.skew, layout_complex=looks_tabular(p.layer or ""))


def is_fixture_image(image: bytes) -> bool:
    """True for the offline stand-in image produced by `PlainTextSource.render`."""
    return image.startswith(FIXTURE_MAGIC)


def decode_fixture_image(image: bytes) -> dict:
    """The text, confidence and flags inside a stand-in image."""
    return json.loads(image[len(FIXTURE_MAGIC) :].decode("utf-8"))


# ---------------------------------------------------------------- PDF (PyMuPDF)


class PdfSource(PageSource):
    """PDF pages through PyMuPDF (imported lazily)."""

    kind = "pdf"

    def __init__(self, path: str, password: str | None = None) -> None:
        """Open the PDF; a password-protected or corrupt file raises SourceError."""
        super().__init__(path)
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise ModelUnavailable("PyMuPDF is not installed, so PDF text and page images cannot be read (pip install pymupdf)") from exc
        self._fitz = fitz
        try:
            doc = fitz.open(path)
        except Exception as exc:  # corrupt files raise several different errors
            raise SourceError("broken", f"the PDF could not be opened: {exc}") from exc
        if doc.needs_pass and not (password and doc.authenticate(password)):
            doc.close()
            raise SourceError("locked", "the PDF is password-protected")
        if doc.page_count == 0:
            doc.close()
            raise SourceError("broken", "the PDF has no pages")
        self._doc = doc

    @property
    def page_count(self) -> int:
        """Number of pages."""
        return int(self._doc.page_count)

    def _page(self, page: int):  # noqa: ANN202
        self.check_page(page)
        return self._doc[page - 1]

    def text_layer(self, page: int) -> str | None:
        """Embedded text, or None when the page has none."""
        text = self._page(page).get_text("text")
        return text if text.strip() else None

    def _blocks(self, page: int) -> list[tuple]:
        return [b for b in self._page(page).get_text("blocks") if b[6] == 0 and str(b[4]).strip()]

    def text_boxes(self, page: int) -> list[list[float]]:
        """Text block rectangles in reading order."""
        return [[round(b[0], 1), round(b[1], 1), round(b[2], 1), round(b[3], 1)] for b in self._blocks(page)]

    def page_area(self, page: int) -> float:
        """Page area in points squared."""
        rect = self._page(page).rect
        return float(rect.width * rect.height) or A4_AREA

    def text_coverage(self, page: int) -> float:
        """How much of what the page shows is also in its text layer, 0 to 1.

        A born-digital page with a short body still has a complete layer, so the text-block area over the whole page
        (a few percent for a one-paragraph order) is the wrong measure. The layer is thin when images cover far more
        of the page than the text blocks do: a scan with a sparse or partial OCR layer. Without images the layer is
        complete (1.0 when there is any text).
        """
        pg = self._page(page)
        area = self.page_area(page)
        text_area = sum(max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1]) for b in self._blocks(page))
        if text_area <= 0.0:
            return 0.0
        image_area = 0.0
        try:
            for info in pg.get_image_info():
                x0, y0, x1, y1 = info["bbox"]
                w = max(0.0, min(x1, pg.rect.x1) - max(x0, pg.rect.x0))
                h = max(0.0, min(y1, pg.rect.y1) - max(y0, pg.rect.y0))
                image_area += w * h
        except Exception:  # noqa: BLE001 - image listing is best effort; fall back to the text-only reading
            image_area = 0.0
        if image_area < 0.25 * area:  # logos, stamps and signatures do not make a page a scan
            return 1.0
        return min(1.0, text_area / image_area)

    def render(self, page: int, dpi: int = 200) -> bytes | None:
        """The page as PNG bytes."""
        return self._page(page).get_pixmap(dpi=dpi).tobytes("png")

    def hints(self, page: int) -> PageHints:
        """Ink annotations mean handwriting; a lone image on an odd-shaped page means a photo; tables from the text."""
        pg = self._page(page)
        ink = any(getattr(a, "type", (None,))[0] == 15 for a in (pg.annots() or []))  # 15 = PDF_ANNOT_INK
        ratio = pg.rect.width / pg.rect.height if pg.rect.height else 1.0
        odd_shape = not any(abs(ratio - r) < 0.03 for r in (0.707, 0.773, 0.607, 1 / 0.707, 1 / 0.773))
        photo = len(pg.get_images()) == 1 and not (pg.get_text("text").strip()) and odd_shape
        return PageHints(handwriting=ink, skew=photo, layout_complex=looks_tabular(pg.get_text("text")))

    def close(self) -> None:
        """Close the document."""
        self._doc.close()


# ---------------------------------------------------------------- DOCX and images


class DocxSource(PageSource):
    """A Word document read directly as one page (python-docx, imported lazily)."""

    kind = "docx"
    direct = True

    def __init__(self, path: str) -> None:
        """Read paragraphs and tables."""
        super().__init__(path)
        try:
            import docx
        except ImportError as exc:
            raise ModelUnavailable("python-docx is not installed, so DOCX files cannot be read", None) from exc
        try:
            document = docx.Document(path)
        except Exception as exc:
            raise SourceError("broken", f"the DOCX could not be opened: {exc}") from exc
        parts = [p.text for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            parts.extend(" | ".join(c.text.strip() for c in row.cells) for row in table.rows)
        self._text = "\n\n".join(parts)

    @property
    def page_count(self) -> int:
        """A DOCX is read as one page."""
        return 1

    def text_layer(self, page: int) -> str | None:
        """The document text."""
        self.check_page(page)
        return self._text or None

    def text_coverage(self, page: int) -> float:
        """Typed text: treated as fully covering the page when present."""
        return 1.0 if self._text else 0.0


class ImageSource(PageSource):
    """A JPG, PNG, TIFF or HEIC file as a single page without a text layer."""

    kind = "image"

    @property
    def page_count(self) -> int:
        """One page."""
        return 1

    def text_layer(self, page: int) -> str | None:
        """Images have no text layer."""
        self.check_page(page)
        return None

    def render(self, page: int, dpi: int = 200) -> bytes | None:
        """The file bytes (HEIC is converted to PNG when pillow-heif is installed)."""
        self.check_page(page)
        raw = Path(self.path).read_bytes()
        if Path(self.path).suffix.lower() not in {".heic", ".heif"}:
            return raw
        try:
            import io

            import pillow_heif
            from PIL import Image

            pillow_heif.register_heif_opener()
            out = io.BytesIO()
            Image.open(io.BytesIO(raw)).convert("RGB").save(out, format="PNG")
            return out.getvalue()
        except ImportError as exc:
            raise ModelUnavailable("pillow-heif is not installed, so HEIC photos cannot be read", "ocr") from exc

    def hints(self, page: int) -> PageHints:
        """Camera formats are treated as phone photos (perspective and uneven light, K4)."""
        return PageHints(skew=Path(self.path).suffix.lower() in PHOTO_SUFFIXES)


# ---------------------------------------------------------------- detection and opening


def _read_head(path: Path, n: int = 4096) -> bytes:
    with path.open("rb") as fh:
        return fh.read(n)


def detect_file_kind(path: str) -> tuple[InputKind | None, str]:
    """File-level input kind: K9 (missing, empty, locked or corrupt), K10 (not a PDF) or None for PDFs.

    Args:
        path: file to look at

    Returns:
        (kind, detail). The detail says why ('locked', 'broken', 'docx', 'image', 'audio', 'text') or 'pdf'.
    """
    p = Path(path)
    if not p.is_file():
        return InputKind.K9_LOCKED_OR_BROKEN, "broken: file not found"
    if p.stat().st_size == 0:
        return InputKind.K9_LOCKED_OR_BROKEN, "broken: empty file"
    suffix = p.suffix.lower()
    if suffix in AUDIO_SUFFIXES:
        return InputKind.K10_NOT_PDF, "audio"
    if suffix in IMAGE_SUFFIXES:
        return InputKind.K10_NOT_PDF, "image"
    if suffix == ".docx":
        return InputKind.K10_NOT_PDF, "docx"
    head = _read_head(p)
    if head.startswith(b"%PDF"):
        if b"/Encrypt" in _tail_and_head(p):
            return InputKind.K9_LOCKED_OR_BROKEN, "locked: password-protected PDF"
        if b"%%EOF" not in _tail_and_head(p):
            return InputKind.K9_LOCKED_OR_BROKEN, "broken: PDF is truncated or corrupt"
        return None, "pdf"
    if suffix in DIRECT_TEXT_SUFFIXES:
        return InputKind.K10_NOT_PDF, "text"
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return InputKind.K9_LOCKED_OR_BROKEN, "broken: not a PDF and not readable text"
    return None, "text-pdf"  # plain text standing in for a PDF (offline fixtures)


def _tail_and_head(p: Path) -> bytes:
    size = p.stat().st_size
    with p.open("rb") as fh:
        head = fh.read(8192)
        fh.seek(max(0, size - 8192))
        return head + fh.read()


@lru_cache(maxsize=16)
def _open_cached(path: str, mtime_ns: int, size: int) -> PageSource:  # noqa: ARG001 (keys invalidate stale entries)
    kind, detail = detect_file_kind(path)
    if kind == InputKind.K9_LOCKED_OR_BROKEN:
        raise SourceError("locked" if detail.startswith("locked") else "broken", detail.split(": ", 1)[-1])
    suffix = Path(path).suffix.lower()
    if detail == "audio":
        raise SourceError("unsupported", "audio files are transcribed, not read as pages")
    if detail == "docx":
        return DocxSource(path)
    if detail == "image":
        return ImageSource(path)
    if detail == "pdf":
        return PdfSource(path)
    try:
        return PlainTextSource(path, Path(path).read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise SourceError("broken", f"{suffix or 'file'} is not readable text") from exc


def open_source(path: str) -> PageSource:
    """Open a file as pages (cached per file version).

    Args:
        path: file to open

    Returns:
        A PageSource.

    Raises:
        SourceError: K9, the file is locked, corrupt, missing or not a page source.
        ModelUnavailable: a needed optional library is not installed.
    """
    p = Path(path)
    try:
        st = p.stat()
    except OSError as exc:
        raise SourceError("broken", f"file not found: {path}") from exc
    return _open_cached(str(p), st.st_mtime_ns, st.st_size)


def clear_source_cache() -> None:
    """Close and forget cached sources (for tests and after files change)."""
    _open_cached.cache_clear()
