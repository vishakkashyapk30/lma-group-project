"""Render text into PDFs of kinds K1-K6 (born-digital, scanned, degraded, photo, Hindi, legacy-font) (plan §15.2 T2)."""

from __future__ import annotations


def render_born_digital(text: str, out_pdf: str, lang: str = "en") -> None:
    """K1: text-layer PDF.

    Args:
        text: see behaviour
        out_pdf: see behaviour
        lang: see behaviour
    """
    raise NotImplementedError


def render_scanned(text: str, out_pdf: str, lang: str = "en") -> None:
    """K2: image-only PDF.

    Args:
        text: see behaviour
        out_pdf: see behaviour
        lang: see behaviour
    """
    raise NotImplementedError


def render_legacy_font(text: str, out_pdf: str) -> None:
    """K6: Hindi typed in a Kruti Dev-style font so the text layer decodes to Latin gibberish.

    Args:
        text: see behaviour
        out_pdf: see behaviour
    """
    raise NotImplementedError


def render_phone_photo(text: str, out_pdf: str) -> None:
    """K4: perspective skew and uneven light.

    Args:
        text: see behaviour
        out_pdf: see behaviour
    """
    raise NotImplementedError
