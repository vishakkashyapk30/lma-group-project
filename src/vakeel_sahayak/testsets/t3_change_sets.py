"""T3 change sets: 60 T1 cases x 3 changes (charge sheet filed; co-accused granted bail; time crosses a threshold) plus 60 no-op controls; 240 updates (plan §15.2)."""

from __future__ import annotations

from vakeel_sahayak.testsets.common import TestSetManifest


def build_t3(t1_dir: str, out_dir: str) -> TestSetManifest:
    """Construct updates with the expected changed fields and grounds.

    Args:
        t1_dir: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.
    """
    raise NotImplementedError
