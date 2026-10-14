"""T8 speech: Kathbath Hindi test subset plus T1 facts dictated in Hindi and English by Indic Parler-TTS; about 300 utterances (plan §15.2)."""

from __future__ import annotations

from vakeel_sahayak.testsets.common import TestSetManifest


def build_t8(kathbath_dir: str, t1_dir: str, out_dir: str) -> TestSetManifest:
    """Synthesise dictation and package transcripts.

    Args:
        kathbath_dir: see behaviour
        t1_dir: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.
    """
    raise NotImplementedError
