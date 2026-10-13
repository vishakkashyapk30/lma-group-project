"""Hindi handling: script detection, Hindi OCR, IndicTrans2; both texts kept (plan §4.5)."""

from __future__ import annotations


def detect_script(text: str) -> str:
    """Return 'devanagari', 'latin' or 'mixed'.

    Args:
        text: see behaviour

    Returns:
        Script label.
    """
    raise NotImplementedError


def to_english_with_original(text_hi: str) -> tuple[str, str]:
    """Translate and keep the Hindi original; span_check runs on the translation, counsel sees the original.

    Args:
        text_hi: see behaviour

    Returns:
        (original, translation).
    """
    raise NotImplementedError
