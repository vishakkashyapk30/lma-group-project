"""Retrieval-only analysis: the nine retrieval configurations scored by recall@10 of G2, overall and BNS-era; A10 knock-outs as slot-fill rates (plan §15.7)."""

from __future__ import annotations


def run_configuration(config_id: int) -> dict[str, float]:
    """Run one retrieval configuration on T1.

    Args:
        config_id: 1..9 as listed in plan §15.7

    Returns:
        Metrics.
    """
    raise NotImplementedError


def run_all(out_dir: str) -> None:
    """Run all nine and write a table.

    Args:
        out_dir: see behaviour
    """
    raise NotImplementedError
