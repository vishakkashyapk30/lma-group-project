"""T9 citation formats: about 500 OIL judgments cited in each format the resolver handles, plus near-miss distractors; about 2,000 strings (plan §15.2)."""

from __future__ import annotations

from vakeel_sahayak.testsets.common import TestSetManifest


def build_t9(metadata_path: str, out_dir: str) -> TestSetManifest:
    """Generate citation strings with doc-id truth.

    Args:
        metadata_path: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.
    """
    raise NotImplementedError
