"""Generic shard runner: starts vLLM inside the script (no long-lived server), processes a shard of about 5 h, saves each case's output as it finishes and resumes from saved progress (plan §17)."""

from __future__ import annotations

from typing import Any


def run_shard(job: str, shard: int, n_shards: int, out_dir: str, time_limit_hours: float = 5.0) -> int:
    """Run one shard of a named job (see configs/eval/runs.yaml).

    Args:
        job: see behaviour
        shard: see behaviour
        n_shards: see behaviour
        out_dir: see behaviour
        time_limit_hours: see behaviour

    Returns:
        Cases completed.
    """
    raise NotImplementedError


def load_progress(out_dir: str) -> set[str]:
    """Case ids already saved.

    Args:
        out_dir: see behaviour

    Returns:
        Done ids.
    """
    raise NotImplementedError


def start_vllm(model_key: str) -> Any:
    """Launch vLLM in-process; model loaded from node /scratch.

    Args:
        model_key: see behaviour

    Returns:
        Engine handle.
    """
    raise NotImplementedError
