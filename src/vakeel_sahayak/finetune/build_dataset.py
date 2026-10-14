"""Assemble the SFT dataset (chat format), excluding test and same-FIR orders (plan §2, §12)."""

from __future__ import annotations


def build_sft_dataset(pairs_path: str, out_dir: str) -> int:
    """Write train/dev jsonl.

    Args:
        pairs_path: see behaviour
        out_dir: see behaviour

    Returns:
        Rows.
    """
    raise NotImplementedError
