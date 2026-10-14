"""Feature evaluation F4: Pairokar vs no cache and FIFO order. Test set: T5. Metrics: missed-deadline rate; pairwise ranking accuracy; cases per node-hour; cache hit rate; output equality with single-case runs (plan §15.6)."""

from __future__ import annotations


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F4 (system and comparison arms), resumable.

    Args:
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    raise NotImplementedError


def score(run_dir: str) -> dict[str, float]:
    """Compute F4 metrics.

    Args:
        run_dir: see behaviour

    Returns:
        Metrics.
    """
    raise NotImplementedError
