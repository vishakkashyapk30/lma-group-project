"""Feature evaluation F2: Incremental redrafting vs full regeneration. Test set: T3. Metrics: stale-claim rate; unchanged-claim stability; tokens and wall time; factor recall and unsupported rate vs full regeneration; no edits on no-op controls (plan §15.6)."""

from __future__ import annotations


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F2 (system and comparison arms), resumable.

    Args:
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    raise NotImplementedError


def score(run_dir: str) -> dict[str, float]:
    """Compute F2 metrics.

    Args:
        run_dir: see behaviour

    Returns:
        Metrics.
    """
    raise NotImplementedError
