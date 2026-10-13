"""Whisper large-v3-turbo or IndicConformer, picked on dev (plan §4.5)."""

from __future__ import annotations

from vakeel_sahayak.models.base import AsrClient


class WhisperAsrClient(AsrClient):
    """Whisper large-v3-turbo or IndicConformer, picked on dev (plan §4.5)."""

    def transcribe(self, audio_path: str, lang_hint: str | None = None) -> str:
        """Transcribe.

        Args:
            audio_path: see behaviour
            lang_hint: see behaviour

        Returns:
            Transcript.
        """
        raise NotImplementedError
