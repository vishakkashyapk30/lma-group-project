"""Abstract interfaces for every model type (plan §12)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Text-generation client interface."""

    @abstractmethod
    def generate(
        self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None
    ) -> str:
        """Generate text.

        Args:
            prompt: see behaviour
            max_tokens: see behaviour
            temperature: see behaviour
            json_schema: constrain decoding to this schema

        Returns:
            Completion.
        """
        raise NotImplementedError

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Token count for budgets.

        Args:
            text: see behaviour

        Returns:
            Count.
        """
        raise NotImplementedError


class VisionClient(ABC):
    """Vision-language transcription interface."""

    @abstractmethod
    def transcribe_page(self, image: bytes, lang_hint: str | None = None) -> str:
        """Transcribe only; never summarise (plan §4.2 step 4).

        Args:
            image: see behaviour
            lang_hint: see behaviour

        Returns:
            Transcript.
        """
        raise NotImplementedError


class OcrClient(ABC):
    """OCR interface."""

    @abstractmethod
    def ocr(self, image: bytes, lang: str) -> tuple[str, float, list[list[float]]]:
        """Run OCR (plan §4.2 step 3).

        Args:
            image: see behaviour
            lang: see behaviour

        Returns:
            (text, mean confidence, boxes).
        """
        raise NotImplementedError


class AsrClient(ABC):
    """Speech-recognition interface."""

    @abstractmethod
    def transcribe(self, audio_path: str, lang_hint: str | None = None) -> str:
        """Transcribe Hindi, English or mixed dictation (plan §4.5).

        Args:
            audio_path: see behaviour
            lang_hint: see behaviour

        Returns:
            Transcript.
        """
        raise NotImplementedError


class TranslationClient(ABC):
    """Translation interface."""

    @abstractmethod
    def translate(self, text: str, src: str = "hi", tgt: str = "en") -> str:
        """IndicTrans2 Hindi to English (plan §4.5).

        Args:
            text: see behaviour
            src: see behaviour
            tgt: see behaviour

        Returns:
            Translation.
        """
        raise NotImplementedError


class NliClient(ABC):
    """NLI / fact-support interface."""

    @abstractmethod
    def entails(self, premise: str, hypothesis: str) -> float:
        """Entailment probability (DeBERTa-v3 NLI in system; MiniCheck in evaluation only).

        Args:
            premise: see behaviour
            hypothesis: see behaviour

        Returns:
            Score.
        """
        raise NotImplementedError


class EmbeddingClient(ABC):
    """Dense embedding interface."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """BGE-M3 embeddings (plan §12).

        Args:
            texts: see behaviour

        Returns:
            Vectors.
        """
        raise NotImplementedError
