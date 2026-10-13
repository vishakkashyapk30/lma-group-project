"""Surya (English+Hindi) with Tesseract fallback (plan §12)."""

from __future__ import annotations

from vakeel_sahayak.models.base import OcrClient


class SuryaOcrClient(OcrClient):
    """Surya (English+Hindi) with Tesseract fallback (plan §12)."""

    def ocr(self, image: bytes, lang: str) -> tuple[str, float, list[list[float]]]:
        """OCR.

        Args:
            image: see behaviour
            lang: see behaviour

        Returns:
            (text, conf, boxes).
        """
        raise NotImplementedError
