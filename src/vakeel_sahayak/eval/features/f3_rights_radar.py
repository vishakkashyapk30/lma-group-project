"""Feature evaluation F3: Rights Radar vs LLM-only and LLM + date_calc. Test set: T4; G7 on T1. Metrics: accuracy per rule; false-ELIGIBLE rate; CHECK rate; agreement with G7 (plan §15.6)."""

from __future__ import annotations


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F3 (system and comparison arms), resumable.

    Args:
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    raise NotImplementedError


def score(run_dir: str) -> dict[str, float]:
    """Compute F3 metrics.

    Args:
        run_dir: see behaviour

    Returns:
        Metrics.
    """
    raise NotImplementedError
