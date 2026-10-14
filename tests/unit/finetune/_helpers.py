"""Helpers for the fine-tuning unit tests (plan §12, §17): synthetic teacher dossiers, pair files, a rule-based span_check.

ASSUMPTION (one place to adjust): every pair file in the fine-tuning pipeline is JSON lines of
`{"doc_id": ..., "facts": <facts text>, "dossier": <CaseDossier as JSON>}`. Steps 1-4 of the data recipe (teacher dossiers, span
filter, noise augmentation) all read and write this row shape; `build_sft_dataset` turns it into chat-format rows.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from tests.fakes.data import read_json
from tests.unit.pipelines._helpers import patch_everywhere, write_jsonl  # noqa: F401  (re-exported for the tests)
from vakeel_sahayak.tools.types import SpanCheckResult

BAD_QUOTE = "BAD QUOTE: a sentence that does not support the value"


def valued_fields(dossier: dict[str, Any]) -> list[str]:
    """Names of the fields that carry a value (and therefore a quote)."""
    return [k for k, v in dossier["fields"].items() if v.get("value") is not None]


def teacher_dossier(case_id: str = "case-0007") -> dict[str, Any]:
    """A teacher-style dossier (JSON): case-0007's fields, each valued field with a source quote, no computed fields.

    The teacher only reads the facts section, so COMPUTED fields (custody_days) are left empty; UNSUPPORTED ones stay empty.
    """
    d = copy.deepcopy(read_json("case_0007", "dossier.json"))
    d["case_id"] = case_id
    for name, field in d["fields"].items():
        src = field.get("source") or {}
        if not src.get("quote"):
            field["value"], field["source"] = None, None
    return d


def pair_row(doc_id: str, bad_fields: tuple[str, ...] = (), facts: str | None = None) -> dict[str, Any]:
    """One pair row; the quotes of `bad_fields` are replaced by BAD_QUOTE so the rule-based span_check rejects them."""
    dossier = teacher_dossier(doc_id)
    for name in bad_fields:
        dossier["fields"][name]["source"]["quote"] = BAD_QUOTE
    return {"doc_id": doc_id, "facts": facts or f"Facts of {doc_id}: the accused was arrested on 20.08.2024 under Section 318(4) BNS.",
            "dossier": dossier}


class RuleSpanCheck:
    """Stands in for the NLI-based `span_check` tool: a quote supports its value unless it is BAD_QUOTE or empty. Records calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, str]] = []

    def __call__(self, value: Any, quote: str) -> SpanCheckResult:
        self.calls.append((value, quote))
        ok = bool(quote) and not quote.startswith("BAD QUOTE")
        return SpanCheckResult(supported=ok, score=0.95 if ok else 0.05, quote=quote)

    def install(self, monkeypatch) -> "RuleSpanCheck":
        patch_everywhere(monkeypatch, "vakeel_sahayak.tools.dossier", "span_check", self)
        return self


def read_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
