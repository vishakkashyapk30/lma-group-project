"""Shared checks and error mapping for the intake tools (plan §3.3): the same conventions as the store tools.

A bad argument is a retryable `invalid_input` ToolError. A missing optional library is `model_unavailable`; a locked or
broken file is `unreadable_file` (ask counsel, never guess); a database or disk problem is `store_unavailable`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from vakeel_sahayak.ingestion.source import SourceError, open_source
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.tools.base import ToolError
from vakeel_sahayak.tools.store_call import invalid

T = TypeVar("T")


def check_file(tool: str, file_path: str) -> ToolError | None:
    """The path must be a non-empty string naming an existing file."""
    if not isinstance(file_path, str) or not file_path.strip():
        return invalid(tool, "file_path must not be empty")
    if not Path(file_path).is_file():
        return ToolError(tool=tool, kind="not_found", message=f"file not found: {Path(file_path).name}", retryable=False)
    return None


def check_page(tool: str, file_path: str, page: int) -> ToolError | None:
    """The file must exist, open as pages, and have the page (numbers start at 1)."""
    if err := check_file(tool, file_path):
        return err
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        return invalid(tool, f"page must be an integer from 1, got {page!r}")
    try:
        count = open_source(file_path).page_count
    except ModelUnavailable:
        return None  # the page count is unknown without the PDF library; the tool's own read reports that if it needs it
    except SourceError as exc:
        return map_error(tool, exc)
    if page > count:
        return invalid(tool, f"page {page} is outside the file's {count} pages")
    return None


def map_error(tool: str, exc: Exception) -> ToolError:
    """Turn an expected failure into a ToolError."""
    if isinstance(exc, ModelUnavailable):
        return ToolError(tool=tool, kind="model_unavailable", message=str(exc), retryable=False)
    if isinstance(exc, ImportError):
        return ToolError(tool=tool, kind="model_unavailable", message=f"missing optional dependency: {exc}", retryable=False)
    if isinstance(exc, SourceError):
        return ToolError(
            tool=tool,
            kind="unreadable_file",
            message=f"the file is {exc.kind} ({exc}); ask counsel for an unlocked or intact copy",
            retryable=False,
        )
    if isinstance(exc, FileNotFoundError):
        return ToolError(tool=tool, kind="not_found", message=str(exc), retryable=False)
    if isinstance(exc, ValidationError):
        return invalid(tool, "; ".join(f"{'.'.join(map(str, e['loc'])) or 'item'}: {e['msg']}" for e in exc.errors()[:5]))
    if isinstance(exc, (IndexError, ValueError)):
        return invalid(tool, str(exc))
    if isinstance(exc, sqlite3.Error):
        return ToolError(tool=tool, kind="store_unavailable", message=str(exc), retryable=True)
    if isinstance(exc, OSError):
        return ToolError(tool=tool, kind="io_error", message=str(exc), retryable=True)
    raise exc


_EXPECTED = (ModelUnavailable, ImportError, SourceError, FileNotFoundError, IndexError, ValueError, sqlite3.Error, OSError)


def guarded(tool: str, action: Callable[[], T]) -> T | ToolError:
    """Run `action`, turning expected failures into ToolError; anything unexpected still raises."""
    try:
        return action()
    except _EXPECTED as exc:
        return map_error(tool, exc)
