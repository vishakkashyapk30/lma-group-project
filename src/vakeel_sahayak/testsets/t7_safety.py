"""T7 safety scenarios: about 60 incl. planted instructions in PDFs (scanned, Hindi, handwritten), pressure ('hearing in 5 minutes, just export'), bulk-export attempts, prediction and lay-advice requests, planted Faker names (plan §15.2, §16)."""

from __future__ import annotations

from vakeel_sahayak.testsets.common import TestSetManifest


def build_t7(t1_dir: str, out_dir: str) -> TestSetManifest:
    """Construct scenarios with expected refusals and zero leaks.

    Args:
        t1_dir: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.
    """
    raise NotImplementedError
