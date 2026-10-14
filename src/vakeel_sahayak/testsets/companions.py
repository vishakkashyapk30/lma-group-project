"""Constructed companion documents on public layouts (IIF-1 FIR, remand order, custody certificate) filled with the case's G3 values and Faker names (plan §2 source 6, §15.2 T2)."""

from __future__ import annotations

from typing import Any


def make_fir(g3_record: dict[str, Any], lang: str = "hi") -> str:
    """FIR text (Hindi via NLLB-200 if needed).

    Args:
        g3_record: see behaviour
        lang: see behaviour

    Returns:
        Text.
    """
    raise NotImplementedError


def make_remand_order(g3_record: dict[str, Any]) -> str:
    """Remand order text.

    Args:
        g3_record: see behaviour

    Returns:
        Text.
    """
    raise NotImplementedError


def make_custody_certificate(g3_record: dict[str, Any]) -> str:
    """Custody certificate text.

    Args:
        g3_record: see behaviour

    Returns:
        Text.
    """
    raise NotImplementedError
