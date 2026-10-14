"""Shared helpers for the privacy tests."""

from __future__ import annotations

import pytest

# ASSUMPTION: a boundary / guard violation raises one of these. RuntimeError is deliberately NOT accepted because
# NotImplementedError is a RuntimeError: a stub must never satisfy a "raises" assertion.
VIOLATION = (AssertionError, ValueError, PermissionError)


def rejects():
    """`with rejects():` passes only when the body raises a violation error (never NotImplementedError)."""
    return pytest.raises(VIOLATION)


# Tiny synthetic stand-ins for client files (no real data).
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + bytes(range(64))  # a page image
WAV_BYTES = b"RIFF\x24\x08\x00\x00WAVEfmt " + bytes(range(32))  # an audio clip

# Sentences embedding the planted names (tests/fakes/data.py PLANTED_NAMES / PLANTED_NAMES_HI) with role cues.
EN_TEXT = (
    "The accused Ramesh Kumar Yadav was arrested on 20.08.2024. "
    "The co-accused Anil Pratap Singh was granted bail on 05.12.2024. "
    "The complainant Sunita Devi Sharma deposed before the Magistrate. "
    "The Investigating Officer Mohd. Irfan Qureshi filed the charge sheet."
)
HI_TEXT = "आरोपी रमेश कुमार यादव को 20.08.2024 को गिरफ्तार किया गया। शिकायतकर्ता सुनीता देवी शर्मा ने बयान दिया।"
