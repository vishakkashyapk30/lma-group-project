"""T5 batch set: 200 T1 cases plus 100 T4 scenarios with deadlines planted in the next 7 days; 300 cases (plan §15.2)."""

from __future__ import annotations

from vakeel_sahayak.testsets.common import TestSetManifest


def build_t5(t1_dir: str, t4_dir: str, out_dir: str) -> TestSetManifest:
    """Plant deadlines and record them as truth.

    Args:
        t1_dir: see behaviour
        t4_dir: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.
    """
    raise NotImplementedError
