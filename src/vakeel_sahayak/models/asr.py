"""Whisper large-v3-turbo or IndicConformer, picked on dev (plan §4.5). Imported lazily; audio stays on the laptop."""

from __future__ import annotations

import importlib.util

from vakeel_sahayak.models.base import AsrClient, ModelUnavailable


class WhisperAsrClient(AsrClient):
    """Whisper large-v3-turbo or IndicConformer, picked on dev (plan §4.5)."""

    def __init__(self, model_size: str = "large-v3-turbo") -> None:
        """Choose the Whisper size; weights load on first use."""
        self.name = "whisper"
        self.model_size = model_size
        self._model = None

    @staticmethod
    def available() -> bool:
        """True when faster-whisper is installed."""
        return importlib.util.find_spec("faster_whisper") is not None

    def transcribe(self, audio_path: str, lang_hint: str | None = None) -> str:
        """Transcribe.

        Args:
            audio_path: audio file on the laptop
            lang_hint: 'hi', 'en' or None for automatic detection (mixed dictation)

        Returns:
            Transcript.

        Raises:
            ModelUnavailable: faster-whisper is not installed.
        """
        if not self.available():
            raise ModelUnavailable("faster-whisper is not installed, so speech cannot be transcribed", "speech")
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self.model_size, compute_type="int8")
        language = lang_hint if lang_hint in ("hi", "en") else None
        segments, _info = self._model.transcribe(audio_path, language=language, vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()


class IndicConformerAsrClient(AsrClient):
    """AI4Bharat IndicConformer, the Hindi-first alternative to Whisper (plan §4.5)."""

    def __init__(self, model_id: str = "ai4bharat/indic-conformer-600m-multilingual") -> None:
        """Choose the checkpoint; weights load on first use."""
        self.name = "indicconformer"
        self.model_id = model_id
        self._model = None

    @staticmethod
    def available() -> bool:
        """True when transformers, torch and torchaudio are installed."""
        return all(importlib.util.find_spec(m) is not None for m in ("transformers", "torch", "torchaudio"))

    def transcribe(self, audio_path: str, lang_hint: str | None = None) -> str:
        """Transcribe with the CTC decoder (Hindi by default).

        Raises:
            ModelUnavailable: the libraries are not installed.
        """
        if not self.available():
            raise ModelUnavailable("IndicConformer (transformers, torch, torchaudio) is not installed", "speech")
        import torch
        import torchaudio
        from transformers import AutoModel

        if self._model is None:
            self._model = AutoModel.from_pretrained(self.model_id, trust_remote_code=True)
        wav, rate = torchaudio.load(audio_path)
        wav = torch.mean(wav, dim=0, keepdim=True)
        if rate != 16000:
            wav = torchaudio.functional.resample(wav, rate, 16000)
        return str(self._model(wav, "en" if lang_hint == "en" else "hi", "ctc")).strip()
