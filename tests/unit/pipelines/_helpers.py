"""Helpers for the pipeline unit tests: synthetic order tables, JSONL writers, patching."""

from __future__ import annotations

import importlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return path


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def patch_everywhere(monkeypatch, module_name: str, attr: str, value: Any) -> None:
    """Patch `module.attr` at its source and on every imported vakeel_sahayak module aliasing it (raising=False)."""
    mod = importlib.import_module(module_name)
    original = getattr(mod, attr, None)
    monkeypatch.setattr(mod, attr, value, raising=False)
    for name, other in list(sys.modules.items()):
        if name.startswith("vakeel_sahayak") and other is not None and other is not mod:
            if original is not None and getattr(other, attr, None) is original:
                monkeypatch.setattr(other, attr, value, raising=False)


COURTS = ["Delhi High Court", "Bombay High Court", "Allahabad High Court", "Madras High Court"]


def order_row(doc_id: str, order_date: str, court: str = "Delhi High Court", offence_date: str | None = None,
              ps: str = "PS-A", fir: str = "1", fir_year: int = 2023) -> dict[str, Any]:
    """One synthetic order row. ASSUMPTION: schema = tests/fixtures/caselaw/orders.jsonl keys (minus `split`) plus offence_date."""
    return {"doc_id": doc_id, "court": court, "date": order_date, "police_station": ps, "fir_number": fir,
            "fir_year": fir_year, "offence_date": offence_date or order_date}


def spread_dates(start: str, n: int, step_days: int = 1) -> list[str]:
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i * step_days)).isoformat() for i in range(n)]


def words(prefix: str, n: int) -> list[str]:
    """n distinct pseudo-words, so accidental overlaps are impossible."""
    return [f"{prefix}{i:03d}" for i in range(n)]
