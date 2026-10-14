"""Shared helpers for the law/case tool tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from vakeel_sahayak.tools.base import ToolError


def assert_tool_error(call: Callable[[], Any]) -> None:
    """The call must fail loudly: raise ValueError/KeyError/LookupError or return a ToolError (never a guess).
    # ASSUMPTION: the plan (§15.8, tool-error recovery) does not fix which of the two the tools use."""
    try:
        result = call()
    except (ValueError, KeyError, LookupError):
        return
    assert isinstance(result, ToolError), f"expected an error, got {result!r}"


def write_jsonl(path: Path, rows: list[Any]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path
