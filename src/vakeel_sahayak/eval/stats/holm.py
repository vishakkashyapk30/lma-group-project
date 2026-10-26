"""Holm-Bonferroni correction within each family of comparisons (plan §15.9)."""

from __future__ import annotations


def holm_bonferroni(p_values: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    """Reject/accept per comparison with the step-down Holm-Bonferroni procedure (plan §15.9).

    The p-values are sorted ascending; the i-th (0-based) is compared against `alpha / (m - i)`; the first one that fails
    stops the step-down and no later hypothesis is rejected.

    Args:
        p_values: comparison id -> p-value
        alpha: family-wise error rate

    Returns:
        Comparison id -> rejected (True) or not.
    """
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(ordered)
    decisions: dict[str, bool] = {}
    still_rejecting = True
    for i, (key, p) in enumerate(ordered):
        if still_rejecting and p <= alpha / (m - i):
            decisions[key] = True
        else:
            decisions[key] = False
            still_rejecting = False
    return decisions
