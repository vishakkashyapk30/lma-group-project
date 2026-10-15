"""Docling layout parser for columns and tables (step 2). Plan §4.2. Docling is imported lazily."""

from __future__ import annotations

import re

from vakeel_sahayak.ingestion.hindi import lang_of
from vakeel_sahayak.ingestion.ladder import RouteOutcome
from vakeel_sahayak.ingestion.source import PdfSource, open_source
from vakeel_sahayak.schemas.enums import PageStatus, ParseRoute

_CELL_SPLIT = re.compile(r"\s{3,}|\t|\s\|\s")


def heuristic_tables(text: str) -> list[list[list[str]]]:
    """Tables found in plain text: runs of at least two lines whose cells are separated by wide gaps, tabs or bars."""
    tables: list[list[list[str]]] = []
    run: list[list[str]] = []
    for line in [*text.splitlines(), ""]:
        cells = [c.strip() for c in _CELL_SPLIT.split(line.strip()) if c.strip()]
        if len(cells) >= 2:
            run.append(cells)
            continue
        if len(run) >= 2:
            tables.append(run)
        run = []
    return tables


def _docling(file_path: str, page: int) -> tuple[str, list[list[list[str]]]]:
    """Text and tables of one page through Docling (raises ImportError when it is not installed)."""
    from docling.document_converter import DocumentConverter

    result = DocumentConverter().convert(file_path, page_range=(page, page))
    document = result.document
    tables = [[[str(c) for c in row] for row in t.export_to_dataframe().values.tolist()] for t in document.tables]
    return document.export_to_markdown(), tables


def parse_layout_page(file_path: str, page: int) -> RouteOutcome:
    """Docling layout parser for columns and tables (step 2).

    Docling runs on PDFs when installed; otherwise (or for other sources, or if Docling fails) the text layer is split
    into tables by a plain-text heuristic and the log says so.

    Args:
        file_path: see behaviour
        page: page number from 1

    Returns:
        RouteOutcome with the text, the tables (rows of cells) and the engine named in the log.
    """
    src = open_source(file_path)
    layer = src.text_layer(page) or ""
    engine, text, tables = "heuristic", layer, heuristic_tables(layer)
    if isinstance(src, PdfSource):
        try:
            text, tables = _docling(file_path, page)
            engine = "docling"
        except Exception:  # not installed, or Docling failed on this page: keep the heuristic result
            text, tables = layer, heuristic_tables(layer)
    return RouteOutcome(
        route=ParseRoute.LAYOUT,
        text=text,
        tables=tables,
        boxes=src.text_boxes(page),
        lang=lang_of(text) if text.strip() else None,
        confidence=1.0 if text.strip() else None,
        status=PageStatus.OK if text.strip() else PageStatus.UNREADABLE,
        log=[f"layout: {engine}" + (f" ({len(tables)} tables)" if tables else "")],
    )
