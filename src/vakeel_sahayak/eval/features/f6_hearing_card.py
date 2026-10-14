"""Feature evaluation F6: Hearing-prep card vs one-call 'what will the bench ask?'. Test set: T1, G5, G6. Metrics: recall/precision of court-discussed factors (G5); recall of imposed condition types (G6) (plan §15.6)."""

from __future__ import annotations


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F6 (system and comparison arms), resumable.

    Args:
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    raise NotImplementedError


def score(run_dir: str) -> dict[str, float]:
    """Compute F6 metrics.

    Args:
        run_dir: see behaviour

    Returns:
        Metrics.
    """
    raise NotImplementedError
