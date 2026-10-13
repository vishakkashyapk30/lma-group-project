"""Shared plumbing of the store-backed tools: argument checks and one place that opens a store, calls it and turns failures into ToolError (plan §3.3, §5.1)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any, TypeVar

from vakeel_sahayak.pipelines.concordance.refs import make_ref, split_ref
from vakeel_sahayak.schemas.enums import Factor, StoreName
from vakeel_sahayak.schemas.ids import check_iso_date
from vakeel_sahayak.stores.base import Store
from vakeel_sahayak.stores.registry import open_store
from vakeel_sahayak.tools.base import ToolError

T = TypeVar("T")
MAX_K = 50


def invalid(tool: str, message: str) -> ToolError:
    """A retryable invalid-input error."""
    return ToolError(tool=tool, kind="invalid_input", message=message, retryable=True)


def check_search_args(tool: str, query: str, k: int, before: str | None, *, need_before: bool = True) -> ToolError | None:
    """Common checks: a non-empty query, 1 <= k <= 50, and a valid `before` date (mandatory: leakage rule, plan §2)."""
    if not isinstance(query, str) or not query.strip():
        return invalid(tool, "query must not be empty")
    if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= MAX_K:
        return invalid(tool, f"k must be an integer from 1 to {MAX_K}")
    if need_before and not before:
        return invalid(tool, "'before' (the case's order date, YYYY-MM-DD) is required: queries only see earlier documents")
    if before:
        try:
            check_iso_date(before)
        except ValueError as exc:
            return invalid(tool, str(exc))
    return None


def parse_filters(tool: str, factor: Any, section_family: list[str] | None) -> tuple[Factor | None, list[str] | None, ToolError | None]:
    """Validate the factor and the section-family references of a paragraph search."""
    parsed: Factor | None = None
    if factor is not None:
        try:
            parsed = Factor(factor)
        except ValueError:
            return None, None, invalid(tool, f"unknown factor {factor!r}: use one of {[f.value for f in Factor]}")
    family: list[str] | None = None
    if section_family:
        try:
            family = [make_ref(*split_ref(ref)) for ref in section_family]
        except ValueError as exc:
            return None, None, invalid(tool, f"section_family entries must look like 'IPC 420' or 'BNS 318(4)': {exc}")
    return parsed, family, None


def call_store(tool: str, name: StoreName, action: Callable[[Any], T], case_id: str | None = None) -> T | ToolError:
    """Open a store, run `action(store)`, close it, and map errors to ToolError (invalid input, not found, store unavailable)."""
    store: Store | None = None
    try:
        store = open_store(name, None, case_id)
        return action(store)
    except LookupError as exc:
        return ToolError(tool=tool, kind="not_found", message=str(exc.args[0] if exc.args else exc), retryable=False)
    except ValueError as exc:  # includes LeakageError
        return invalid(tool, str(exc))
    except (sqlite3.Error, OSError, ImportError) as exc:
        return ToolError(tool=tool, kind="store_unavailable", message=f"{name.value}: {exc}", retryable=True)
    finally:
        if store is not None:
            store.close()
