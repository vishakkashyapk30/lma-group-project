"""Metrics: CER, boundary F1, document-type accuracy, downstream field accuracy, escalation rate, questions asked, seconds and GPU-seconds per page (plan §15.8)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.dossier import CaseDossier


def character_error_rate(hyp: str, ref: str) -> float:
    """CER.

    Args:
        hyp: see behaviour
        ref: see behaviour

    Returns:
        CER.
    """
    raise NotImplementedError


def boundary_f1(pred: list[tuple[int, int]], gold: list[tuple[int, int]]) -> float:
    """Document boundary F1.

    Args:
        pred: see behaviour
        gold: see behaviour

    Returns:
        F1.
    """
    raise NotImplementedError


def field_accuracy(dossier: CaseDossier, gold: dict[str, Any]) -> float:
    """Downstream accuracy vs G3.

    Args:
        dossier: see behaviour
        gold: see behaviour

    Returns:
        Accuracy.
    """
    raise NotImplementedError
