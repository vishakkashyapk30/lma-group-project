"""Open India Law ingest: select HC bail orders 2019-2025 by case type and keywords ('BAIL APPLN', '439 Cr.P.C.', '483 BNSS'), SC bail judgments, and the statute texts (plan §2 source 1)."""

from __future__ import annotations


def select_bail_orders(raw_dir: str, out_dir: str, keywords: list[str] | None = None) -> int:
    """Filter Open India Law dumps to bail orders; write interim parquet/jsonl.

    Args:
        raw_dir: see behaviour
        out_dir: see behaviour
        keywords: see behaviour

    Returns:
        Number of orders selected.
    """
    raise NotImplementedError


def extract_statute_texts(raw_dir: str, out_dir: str) -> int:
    """Extract IPC, BNS, CrPC, BNSS text plus NDPS s.37, UAPA s.43D(5), PMLA s.45.

    Args:
        raw_dir: see behaviour
        out_dir: see behaviour

    Returns:
        Number of sections.
    """
    raise NotImplementedError


def check_feasibility(interim_dir: str) -> dict[str, int]:
    """Week-0 data feasibility: >=250 cleanly split orders, >=60 BNS-era, citation metadata available (plan §18 week 0).

    Args:
        interim_dir: see behaviour

    Returns:
        Counts.
    """
    raise NotImplementedError
