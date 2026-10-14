"""Step 4: for 30% of kept pairs, replace the input with Surya OCR of an Augraphy-degraded rendering of the same text; target unchanged (plan §12)."""

from __future__ import annotations


def augment_pairs(pairs_path: str, out_path: str, fraction: float = 0.3) -> int:
    """Create noisy inputs.

    Args:
        pairs_path: see behaviour
        out_path: see behaviour
        fraction: see behaviour

    Returns:
        Number augmented.
    """
    raise NotImplementedError
