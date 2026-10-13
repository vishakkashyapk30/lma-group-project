"""Qwen3-VL 4-bit (4B laptop; 8B Ada) or Qwen2.5-VL-7B (plan §12)."""

from __future__ import annotations

from vakeel_sahayak.models.base import VisionClient


class LocalVisionClient(VisionClient):
    """Qwen3-VL 4-bit (4B laptop; 8B Ada) or Qwen2.5-VL-7B (plan §12)."""

    def transcribe_page(self, image: bytes, lang_hint: str | None = None) -> str:
        """Transcribe.

        Args:
            image: see behaviour
            lang_hint: see behaviour

        Returns:
            Transcript.
        """
        raise NotImplementedError
