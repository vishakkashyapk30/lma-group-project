"""Feature evaluation F8: Hindi and voice intake vs English-only pipeline, Whisper vs IndicConformer, no read-back. Test set: T2 (K5, K6); T8. Metrics: Hindi CER; field-accuracy gap Hindi vs English; WER; date/section/number error rate before and after read-back (plan §15.6)."""

from __future__ import annotations


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F8 (system and comparison arms), resumable.

    Args:
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    raise NotImplementedError


def score(run_dir: str) -> dict[str, float]:
    """Compute F8 metrics.

    Args:
        run_dir: see behaviour

    Returns:
        Metrics.
    """
    raise NotImplementedError
