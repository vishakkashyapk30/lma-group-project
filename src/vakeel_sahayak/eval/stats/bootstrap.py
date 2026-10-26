"""Paired bootstrap 95% confidence intervals (plan §15.9)."""

from __future__ import annotations

import numpy as np


def paired_bootstrap_ci(
    a: list[float], b: list[float], n_boot: int = 10000, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Bootstrap the mean paired difference and its percentile confidence interval (plan §15.9).

    Resampling is seeded, so the interval is reproducible across runs.

    Args:
        a: system A's per-case scores
        b: system B's per-case scores (paired with A)
        n_boot: number of bootstrap resamples
        alpha: 1 - alpha is the confidence level (0.05 -> 95%)

    Returns:
        (mean paired difference, lower bound, upper bound).
    """
    if len(a) != len(b):
        raise ValueError(f"paired samples must have equal length: {len(a)} != {len(b)}")
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    n = len(diff)
    mean = float(diff.mean())
    if n == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(0)
    resamples = rng.integers(0, n, size=(n_boot, n))
    boot_means = diff[resamples].mean(axis=1)
    lo = float(np.quantile(boot_means, alpha / 2))
    hi = float(np.quantile(boot_means, 1 - alpha / 2))
    return mean, lo, hi
