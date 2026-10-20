"""Wrappers that try Sarvam and fall back to the local implementation (plan §12: local first, Sarvam optional).

When Sarvam is off, has no key, is policy-blocked (mode, data class, no counsel consent), fails the boundary check or the API
errors, the call is answered by the local client and nothing leaves the machine. `last_engine` / `name` say which engine
answered, so the ingestion log shows 'sarvam-vision' or the local engine, never a silent swap.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from vakeel_sahayak.models.base import AsrClient, LLMClient, OcrClient, TranslationClient, VisionClient
from vakeel_sahayak.models.sarvam.errors import SarvamError
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError

log = logging.getLogger("vakeel_sahayak.sarvam")
FALLBACK_ERRORS = (SarvamError, PrivacyBoundaryError)


class _Fallback:
    """Primary-then-local helper."""

    def __init__(self, primary: Any, local: Callable[[], Any]) -> None:
        self.primary = primary
        self._local_factory = local
        self._local: Any = None
        self.last_engine: Any = primary
        self.last_error: str | None = None

    @property
    def local(self) -> Any:
        """The local client (built on first need)."""
        if self._local is None:
            self._local = self._local_factory()
        return self._local

    def _call(self, method: str, *args: Any, **kw: Any) -> Any:
        try:
            out = getattr(self.primary, method)(*args, **kw)
        except FALLBACK_ERRORS as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            log.info("sarvam %s not used (%s); using the local engine", method, type(exc).__name__)
            self.last_engine = self.local
            return getattr(self.local, method)(*args, **kw)
        self.last_engine, self.last_error = self.primary, None
        return out

    @property
    def name(self) -> str:
        """Name of the engine that answered last (the primary's before any call)."""
        return str(getattr(self.last_engine, "name", type(self.last_engine).__name__))


class FallbackVision(_Fallback, VisionClient):
    """Sarvam Vision, else the local vision model."""

    def transcribe_page(self, image: bytes, lang_hint: str | None = None) -> str:
        """See `VisionClient`."""
        return self._call("transcribe_page", image, lang_hint)


class FallbackOcr(_Fallback, OcrClient):
    """Sarvam Vision as OCR, else Surya/Tesseract."""

    def ocr(self, image: bytes, lang: str) -> tuple[str, float, list[list[float]]]:
        """See `OcrClient`."""
        return self._call("ocr", image, lang)


class FallbackAsr(_Fallback, AsrClient):
    """Saaras, else Whisper/IndicConformer."""

    def transcribe(self, audio_path: str, lang_hint: str | None = None) -> str:
        """See `AsrClient`."""
        return self._call("transcribe", audio_path, lang_hint)


class FallbackTranslator(_Fallback, TranslationClient):
    """Sarvam-Translate, else IndicTrans2 / the offline glossary."""

    def translate(self, text: str, src: str = "hi", tgt: str = "en") -> str:
        """See `TranslationClient`."""
        return self._call("translate", text, src, tgt)

    @property
    def is_identity(self) -> bool:
        """True when the engine that answered last made no translation."""
        return bool(getattr(self.last_engine, "is_identity", False))


class FallbackLLM(LLMClient):
    """Sarvam (or OpenAI) chat for an agent role, else the role's configured local/vLLM client."""

    def __init__(self, primary: LLMClient, local: Callable[[], LLMClient], where: str, errors: tuple[type[BaseException], ...] = FALLBACK_ERRORS) -> None:
        """`where` is the role's location, so the agents' boundary rule applies whichever client answers; `errors` are the failures
        that trigger the fallback (Sarvam's by default; OpenAI's include `BudgetExceeded`, so over the cap the local client answers)."""
        self._errors = errors
        self.primary = primary
        self._local_factory = local
        self._local: LLMClient | None = None
        self.last_engine: LLMClient = primary
        self.where = where
        self.model_id = primary.model_id

    @property
    def local(self) -> LLMClient:
        """The fallback client (built on first need)."""
        if self._local is None:
            self._local = self._local_factory()
        return self._local

    @property
    def name(self) -> str:  # type: ignore[override]
        """Name of the engine that answered last."""
        return self.last_engine.name

    @property
    def family(self) -> str:  # type: ignore[override]
        """Model family of the engine that answered last."""
        return str(self.last_engine.family)

    @property
    def is_offline(self) -> bool:  # type: ignore[override]
        """True when the local fallback is the deterministic offline client and it answered last."""
        return bool(self.last_engine.is_offline)

    def _run(self, method: str, *args: Any, **kw: Any) -> str:
        try:
            out = getattr(self.primary, method)(*args, **kw)
            self.last_engine = self.primary
        except self._errors as exc:
            log.info("%s llm not used (%s); using the local engine", getattr(self.primary, "name", "external"), type(exc).__name__)
            self.last_engine = self.local
            out = getattr(self.local, method)(*args, **kw)
        last = getattr(self.last_engine._accounting()[1], "last", None)
        if last:
            self.record_usage(*last)
        return out  # type: ignore[no-any-return]

    def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None) -> str:
        """Sarvam first, local on a block or failure."""
        return self._run("generate", prompt, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)

    def chat(self, messages: list[dict[str, str]], max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None) -> str:
        """Sarvam first, local on a block or failure."""
        return self._run("chat", messages, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)

    def count_tokens(self, text: str) -> int:
        """The answering engine's count."""
        return self.last_engine.count_tokens(text)
