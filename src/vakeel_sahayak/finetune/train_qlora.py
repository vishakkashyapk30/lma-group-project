"""Step 5: QLoRA on Qwen3-4B (r=16, 2 epochs, one 2080 Ti, FP16), checkpoint every epoch. Launched by scripts/ada/sbatch_qlora.sbatch (plan §12, §17)."""

from __future__ import annotations


def train(config_path: str = "configs/finetune/qlora.yaml") -> str:
    """Train and return the adapter directory.

    Args:
        config_path: see behaviour

    Returns:
        Adapter path.
    """
    raise NotImplementedError
