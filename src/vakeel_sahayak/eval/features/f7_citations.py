"""Feature evaluation F7: Citation resolver and good-law check vs regex-only resolver and B0-B4. Test set: T9; labeler agreement; T1 runs. Metrics: resolution accuracy by format; coverage; treatment agreement (kappa); rate of citing overruled precedents (plan §15.6)."""

from __future__ import annotations


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F7 (system and comparison arms), resumable.

    Args:
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    raise NotImplementedError


def score(run_dir: str) -> dict[str, float]:
    """Compute F7 metrics.

    Args:
        run_dir: see behaviour

    Returns:
        Metrics.
    """
    raise NotImplementedError
