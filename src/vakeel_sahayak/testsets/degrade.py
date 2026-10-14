"""Augraphy degradations: faint photocopy, fax noise, stamps and signatures over text (plan §15.2 T2, §12 noise-augmented training)."""

from __future__ import annotations


def degrade_page(image: bytes, severity: str = "medium", seed: int = 0) -> bytes:
    """K3 degradation with Augraphy.

    Args:
        image: see behaviour
        severity: see behaviour
        seed: see behaviour

    Returns:
        Degraded image.
    """
    raise NotImplementedError
