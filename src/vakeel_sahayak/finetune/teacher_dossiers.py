"""Step 1: the teacher reads the facts section of about 4K train orders and outputs a CaseDossier quoting a source sentence per field. Runs as an Ada interactive shard with resume (plan §12, §17)."""

from __future__ import annotations


def run_shard(orders_path: str, out_path: str, shard: int, n_shards: int) -> int:
    """Generate dossiers for one shard, saving each output as it finishes.

    Args:
        orders_path: see behaviour
        out_path: see behaviour
        shard: see behaviour
        n_shards: see behaviour

    Returns:
        Number completed.
    """
    raise NotImplementedError


def teacher_pilot(orders_path: str, n: int = 50) -> dict[str, float]:
    """Week-1 pilot: Qwen3-32B-AWQ vs a Mistral API model on the same 50 train orders; measure the share of outputs passing span_check, tokens per hour, rate-limit stalls (plan §17).

    Args:
        orders_path: see behaviour
        n: see behaviour

    Returns:
        Pilot metrics.
    """
    raise NotImplementedError
