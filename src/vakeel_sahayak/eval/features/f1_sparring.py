"""Feature evaluation F1: Abhiyojak sparring vs a one-call list; 2x2 with A2, A8, A9. Test set: T1, G4. Metrics: objection-factor recall/precision vs G4; unsupported-fact rate in replies; share of UNANSWERED flagged (plan §15.6)."""

from __future__ import annotations


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F1 (system and comparison arms), resumable.

    Args:
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    raise NotImplementedError


def score(run_dir: str) -> dict[str, float]:
    """Compute F1 metrics.

    Args:
        run_dir: see behaviour

    Returns:
        Metrics.
    """
    raise NotImplementedError
