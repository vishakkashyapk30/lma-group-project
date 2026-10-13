"""IndicTrans2 Hindi to English (plan §4.5)."""

from __future__ import annotations

from vakeel_sahayak.models.base import TranslationClient


class IndicTrans2Client(TranslationClient):
    """IndicTrans2 Hindi to English (plan §4.5)."""

    def translate(self, text: str, src: str = "hi", tgt: str = "en") -> str:
        """Translate.

        Args:
            text: see behaviour
            src: see behaviour
            tgt: see behaviour

        Returns:
            Translation.
        """
        raise NotImplementedError
