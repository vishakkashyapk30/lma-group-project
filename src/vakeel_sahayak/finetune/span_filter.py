"""Steps 2-3: keep only orders where every field passes span_check (about 2K pairs) (plan §12)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.finetune._io import read_rows, write_rows


def field_checks(dossier: dict[str, Any]) -> list[tuple[str, Any, str]]:
    """(name, value, quote) for every field of a dossier JSON that carries a value; fields without a value have nothing to verify."""
    out: list[tuple[str, Any, str]] = []
    for name, field in (dossier.get("fields") or {}).items():
        value = (field or {}).get("value")
        if value is None:
            continue
        quote = ((field or {}).get("source") or {}).get("quote") or ""
        out.append((name, value, quote))
    return out


def all_fields_pass(dossier: dict[str, Any]) -> bool:
    """True when every valued field has a quote that `span_check` says supports the value (a value with no quote fails)."""
    from vakeel_sahayak.tools import dossier as dossier_tools  # looked up at call time

    for _name, value, quote in field_checks(dossier):
        if not isinstance(quote, str) or not quote.strip():
            return False
        if not dossier_tools.span_check(value, quote).supported:
            return False
    return True


def filter_pairs(dossiers_path: str, out_path: str) -> int:
    """Run span_check per field; keep all-pass orders.

    Args:
        dossiers_path: JSONL of {"doc_id", "facts", "dossier"} rows from the teacher
        out_path: JSONL of the kept rows, unchanged and in input order

    Returns:
        Pairs kept.
    """
    kept = [row for row in read_rows(dossiers_path) if all_fields_pass(row.get("dossier") or {})]
    return write_rows(out_path, kept)


def main(argv: list[str] | None = None) -> int:
    """CLI: python -m vakeel_sahayak.finetune.span_filter DOSSIERS OUT."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: python -m vakeel_sahayak.finetune.span_filter DOSSIERS.jsonl PAIRS.jsonl")
        return 2
    print(f"kept {filter_pairs(args[0], args[1])} pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
