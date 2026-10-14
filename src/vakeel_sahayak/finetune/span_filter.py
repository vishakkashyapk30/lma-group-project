"""Steps 2-3: keep only orders where every field passes span_check (about 2K pairs) (plan §12)."""

from __future__ import annotations


def filter_pairs(dossiers_path: str, out_path: str) -> int:
    """Run span_check per field; keep all-pass orders.

    Args:
        dossiers_path: see behaviour
        out_path: see behaviour

    Returns:
        Pairs kept.
    """
    raise NotImplementedError
