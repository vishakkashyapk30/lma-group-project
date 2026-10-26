"""Statistics the plan asks for that `eval/stats` does not have (evaluation plan 5.2, 5.4): exact McNemar, cluster bootstrap, Wilson interval, effect sizes.

Everything is seeded and pure python plus numpy; nothing here needs scipy (the exact tests use `math.comb`).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

SEED = 0


def mcnemar_exact(a: Sequence[bool], b: Sequence[bool]) -> dict[str, float | int | None]:
    """Exact two-sided McNemar test (binomial on the discordant pairs) for paired binary outcomes (plan 5.2).

    The plan uses the exact binomial test when the discordant count is under 25; it is always used here (it is also valid above 25 and needs no scipy).

    Args:
        a: outcome of system A per item (True = success)
        b: outcome of system B on the same items

    Returns:
        `b01` (A fails, B succeeds), `b10` (A succeeds, B fails), `p` (two-sided, 1.0 when there are no discordant pairs), `odds_ratio` (b10 / b01; None when
        b01 is 0), `diff` (proportion A minus proportion B).
    """
    if len(a) != len(b):
        raise ValueError(f"paired samples must have equal length: {len(a)} != {len(b)}")
    b10 = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    b01 = sum(1 for x, y in zip(a, b, strict=True) if y and not x)
    n = b10 + b01
    if n == 0:
        p = 1.0
    else:
        k = min(b10, b01)
        tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
        p = min(1.0, 2 * tail)
    diff = (sum(a) - sum(b)) / len(a) if len(a) else 0.0
    return {"b10": b10, "b01": b01, "p": p, "odds_ratio": (b10 / b01) if b01 else None, "diff": diff}


def cluster_bootstrap_diff(
    hits_a: Sequence[Sequence[float]], hits_b: Sequence[Sequence[float]], n_boot: int = 10000, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Cluster bootstrap of the difference of two pooled item-level proportions (plan 5.2, "pooled item-level data from several items per case").

    Each cluster is one case: `hits_a[i]` are the 0/1 item outcomes of system A on case i (for example one entry per gold factor), `hits_b[i]` those of B
    on the same case and the same items. Cases are resampled, items stay with their case; the statistic is pooled hits over pooled items.

    Returns:
        (pooled proportion A minus pooled proportion B, lower, upper); (0, 0, 0) with no items.
    """
    if len(hits_a) != len(hits_b):
        raise ValueError("cluster samples must have equal length")
    ha = np.array([float(sum(x)) for x in hits_a])
    na = np.array([float(len(x)) for x in hits_a])
    hb = np.array([float(sum(x)) for x in hits_b])
    nb = np.array([float(len(x)) for x in hits_b])
    if len(ha) == 0 or na.sum() == 0 or nb.sum() == 0:
        return 0.0, 0.0, 0.0
    point = float(ha.sum() / na.sum() - hb.sum() / nb.sum())
    idx = np.random.default_rng(SEED).integers(0, len(ha), size=(n_boot, len(ha)))
    sa, ta, sb, tb = ha[idx].sum(1), na[idx].sum(1), hb[idx].sum(1), nb[idx].sum(1)
    ok = (ta > 0) & (tb > 0)
    diffs = sa[ok] / ta[ok] - sb[ok] / tb[ok]
    if len(diffs) == 0:
        return point, 0.0, 0.0
    return point, float(np.quantile(diffs, alpha / 2)), float(np.quantile(diffs, 1 - alpha / 2))


def cluster_bootstrap_ci(hits: Sequence[Sequence[float]], n_boot: int = 10000, alpha: float = 0.05) -> tuple[float, float, float]:
    """Cluster bootstrap interval of one pooled item-level proportion (resamples cases, keeps items together)."""
    return cluster_bootstrap_diff(hits, [[0.0] * len(x) for x in hits], n_boot, alpha)


def bootstrap_mean_ci(values: Sequence[float], n_boot: int = 10000, alpha: float = 0.05) -> tuple[float, float, float]:
    """Seeded percentile interval of the mean of per-case values (the "interval of the mean for the row", plan 6.0)."""
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0:
        return float("nan"), float("nan"), float("nan")
    idx = np.random.default_rng(SEED).integers(0, len(arr), size=(n_boot, len(arr)))
    means = arr[idx].mean(axis=1)
    return float(arr.mean()), float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def bootstrap_p_value(diff: Sequence[float], n_boot: int = 10000) -> float:
    """Two-sided bootstrap p for "mean paired difference = 0": twice the smaller share of resampled means on one side of 0 (floor 1/n_boot).

    Used only when scipy is missing and the Wilcoxon test cannot run; the table says so (`p_source`).
    """
    arr = np.asarray(diff, dtype=float)
    if len(arr) == 0 or not np.any(arr):
        return 1.0
    idx = np.random.default_rng(SEED).integers(0, len(arr), size=(n_boot, len(arr)))
    means = arr[idx].mean(axis=1)
    p = 2 * min(float((means <= 0).mean()), float((means >= 0).mean()))
    return float(min(1.0, max(p, 1.0 / n_boot)))


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Wilson score interval of a proportion (plan 5.2, unpaired proportions); (nan, nan, nan) when n is 0."""
    if n <= 0:
        return float("nan"), float("nan"), float("nan")
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def cohens_dz(diff: Sequence[float]) -> float | None:
    """Cohen's d_z of paired differences: mean over sample SD (plan 5.4); None with fewer than 2 pairs or zero spread."""
    arr = np.asarray(diff, dtype=float)
    if len(arr) < 2:
        return None
    sd = float(arr.std(ddof=1))
    return float(arr.mean() / sd) if sd > 0 else None
