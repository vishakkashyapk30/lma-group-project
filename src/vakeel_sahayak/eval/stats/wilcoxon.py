"""Wilcoxon signed-rank test (plan §15.9)."""

from __future__ import annotations


def wilcoxon_signed_rank(a: list[float], b: list[float]) -> float:
    """Two-sided Wilcoxon signed-rank p-value for paired samples (plan §15.9).

    Uses scipy's exact test for small samples. When every paired difference is zero the systems are identical, so the
    p-value is 1.0 (scipy would otherwise raise).

    Args:
        a: system A's per-case scores
        b: system B's per-case scores (paired with A)

    Returns:
        Two-sided p-value.
    """
    if len(a) != len(b):
        raise ValueError(f"paired samples must have equal length: {len(a)} != {len(b)}")
    diffs = [x - y for x, y in zip(a, b, strict=True)]
    if all(d == 0 for d in diffs):
        return 1.0
    from scipy.stats import wilcoxon

    return float(wilcoxon(a, b).pvalue)
