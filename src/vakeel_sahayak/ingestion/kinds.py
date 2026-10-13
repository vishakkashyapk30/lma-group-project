"""Input-kind recognition K1-K10 (plan §4.1)."""

from __future__ import annotations

from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.schemas.enums import InputKind


def classify_input_kind(signals: PageSignals) -> InputKind:
    """Map signals to K1-K10 (plan §4.1).

    Args:
        signals: see behaviour

    Returns:
        InputKind.
    """
    raise NotImplementedError
