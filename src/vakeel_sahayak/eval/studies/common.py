"""Shared output of the studies: a JSON with the numbers and a Markdown table, both small."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def md_table(columns: list[str], rows: list[list[Any]]) -> str:
    """A Markdown table; None prints as n/a and floats to 3 places."""
    def f(x: Any) -> str:
        return "n/a" if x is None else f"{x:.3f}" if isinstance(x, float) else str(x)

    return "\n".join(["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|", *["| " + " | ".join(f(c) for c in r) + " |" for r in rows]]) + "\n"


def write_result(out_dir: str, study: str, result: dict[str, Any], title: str, caption: str, columns: list[str], rows: list[list[Any]], notes: list[str]) -> dict[str, Any]:
    """Write `<out_dir>/<study>.json` and `<study>.md` (title, italic caption, table, notes) and return `result` with `study` set."""
    result = {"study": study, **result}
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{study}.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    (d / f"{study}.md").write_text(f"### {title}\n\n*{caption}*\n\n" + md_table(columns, rows) + "\n" + "".join(f"- {n}\n" for n in notes), encoding="utf-8")
    return result
