"""T2 messy bundles: 100 T1 cases bundled with 2-3 companions rendered as K1-K6, plus about 200 HLDC Hindi documents and optional e-SCR Hindi judgments; about 600 bundles, 4,800 pages; answers by construction (plan §15.2)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vakeel_sahayak.testsets.common import TestSetManifest


def build_t2(t1_dir: str, hldc_dir: str | None, escr_dir: str | None, out_dir: str) -> TestSetManifest:
    """Build bundles with known page text, document boundaries, types and field values.

    Args:
        t1_dir: see behaviour
        hldc_dir: see behaviour
        escr_dir: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.
    """
    raise NotImplementedError


def scripted_counsel(truth: dict[str, Any]) -> Callable[[str], str]:
    """Counsel stub that knows the true values and supplies a clean copy when asked (plan §15.5).

    Args:
        truth: see behaviour

    Returns:
        Answer function.
    """
    raise NotImplementedError
