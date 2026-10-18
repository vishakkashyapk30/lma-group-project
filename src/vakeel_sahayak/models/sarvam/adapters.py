"""Sarvam implementations of the model interfaces (plan §12). Each call is authorised by `policy.authorize` first.

| class | interface | Sarvam product |
|---|---|---|
| `SarvamVisionClient` | `VisionClient` + `OcrClient` | Sarvam Vision document intelligence (digitise jobs; handwriting, Indic scripts) |
| `SarvamTranslator` | `TranslationClient` | Sarvam-Translate (22 languages) or Mayura (11) |
| `SarvamAsr` | `AsrClient` | Saaras (code-mix aware) |
| `SarvamLLMClient` | `LLMClient` | Sarvam-105B chat completions |
| `SarvamTts` | (none) | Bulbul |
| `SarvamLangId` | (none) | text-lid |

They raise `SarvamPolicyError` / `PrivacyBoundaryError` when the policy forbids the call and a `SarvamError` when the API fails;
`models.sarvam.fallback` wraps them so callers get the local implementation instead.
"""

from __future__ import annotations

import dataclasses
import io
import re
import wave
from pathlib import Path
from typing import Any

from vakeel_sahayak.models.base import (
    AsrClient,
    LLMClient,
    OcrClient,
    TranslationClient,
    VisionClient,
    approx_tokens,
    strip_thinking,
)
from vakeel_sahayak.models.prompting import to_messages
from vakeel_sahayak.models.sarvam.api import LidResult, SarvamApi, from_bcp47
from vakeel_sahayak.models.sarvam.config import sarvam_config
from vakeel_sahayak.models.sarvam.errors import SarvamError
from vakeel_sahayak.models.sarvam.policy import DataClass, SarvamScope, authorize, current_scope

_OCR_LANG = {"hin": "hi", "eng": "en"}
_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


def _image_type(image: bytes) -> tuple[str, str]:
    """(filename, content type) of a page image from its magic bytes."""
    if image[:8] == b"\x89PNG\r\n\x1a\n":
        return "page.png", "image/png"
    if image[:3] == b"\xff\xd8\xff":
        return "page.jpg", "image/jpeg"
    return "page.png", "image/png"


class _Base:
    """Shared: the API handle and the scope (a fixed one, or whatever `policy.current_scope()` says at call time)."""

    def __init__(self, api: SarvamApi | None = None, scope: SarvamScope | None = None) -> None:
        """Wrap an API handle (default: key from the environment); `scope` pins the data class and case."""
        self._api = api
        self._scope = scope

    @property
    def api(self) -> SarvamApi:
        """The API handle (built on first use)."""
        if self._api is None:
            self._api = SarvamApi()
        return self._api

    def _gate(self, capability: str, **kw: Any) -> SarvamScope:
        return authorize(capability, self._scope or current_scope(), **kw)


class SarvamVisionClient(_Base, VisionClient, OcrClient):
    """Page image to text with Sarvam Vision. The page image leaves the machine, so it needs `consented` mode and counsel's consent."""

    name = "sarvam-vision"

    def transcribe_page(self, image: bytes, lang_hint: str | None = None) -> str:
        """Transcribe a page image (Markdown out of the digitise job; never a summary).

        Args:
            image: PNG or JPEG bytes
            lang_hint: 'hi', 'en' or None (None lets Sarvam default to Indic scripts)

        Returns:
            Transcript.
        """
        self._gate("vision", nbytes=len(image))
        filename, ctype = _image_type(image)
        return self.api.digitise(image, filename, ctype, lang_hint if lang_hint in ("hi", "en") else None).text.strip()

    def ocr(self, image: bytes, lang: str) -> tuple[str, float, list[list[float]]]:
        """OCR through the same job. Sarvam gives no per-word confidence, so the confidence is the share of pages it processed
        successfully (1.0 or 0.0 for one image) and there are no boxes."""
        self._gate("vision", nbytes=len(image))
        filename, ctype = _image_type(image)
        hint = _OCR_LANG.get(lang)
        res = self.api.digitise(image, filename, ctype, hint)
        return res.text.strip(), res.success_ratio, []


class SarvamTranslator(_Base, TranslationClient):
    """Sarvam-Translate (default) or Mayura. The original is kept by the caller (`ingestion.hindi.translate_keeping_original`)."""

    name = "sarvam-translate"
    is_identity = False

    def __init__(self, api: SarvamApi | None = None, scope: SarvamScope | None = None, model: str | None = None) -> None:
        """Choose the model (default configs/models.yaml `sarvam.translate.model`)."""
        super().__init__(api, scope)
        self.model = model

    def _pieces(self, line: str, limit: int) -> list[str]:
        if len(line) <= limit:
            return [line]
        out: list[str] = []
        cur = ""
        for sent in _SENTENCE_END.split(line):
            while len(sent) > limit:
                out.append(sent[:limit])
                sent = sent[limit:]
            if cur and len(cur) + 1 + len(sent) > limit:
                out.append(cur)
                cur = sent
            else:
                cur = f"{cur} {sent}".strip()
        return [*out, cur] if cur else out

    def translate(self, text: str, src: str = "hi", tgt: str = "en") -> str:
        """Translate line by line (so layout survives); lines over the model's limit are split at sentence ends."""
        self._gate("translate", text=text)
        cfg = sarvam_config()["translate"]
        model = self.model or cfg["model"]
        limit = int(cfg["max_chars"].get(model, 1000))
        lines = text.split("\n")
        for i, ln in enumerate(lines):
            if ln.strip():
                lines[i] = " ".join(self.api.translate(p, src, tgt, model=model).text.strip() for p in self._pieces(ln, limit))
        return "\n".join(lines)


def _split_wav(data: bytes, max_seconds: float) -> list[bytes]:
    """Split a PCM WAV into clips of at most `max_seconds` (returns [data] when it is short or not a readable WAV)."""
    try:
        with wave.open(io.BytesIO(data)) as src:
            rate, frames = src.getframerate(), src.getnframes()
            per = int(max_seconds * rate)
            if frames <= per:
                return [data]
            params = src.getparams()
            clips = []
            while True:
                chunk = src.readframes(per)
                if not chunk:
                    break
                buf = io.BytesIO()
                with wave.open(buf, "wb") as out:
                    out.setparams(params)
                    out.writeframes(chunk)
                clips.append(buf.getvalue())
            return clips
    except (wave.Error, EOFError):
        return [data]


class SarvamAsr(_Base, AsrClient):
    """Saaras speech-to-text, code-mix aware (mode from `sarvam.speech_to_text.mode`, default 'codemix'). Audio is raw client data."""

    name = "sarvam-saaras"

    def transcribe(self, audio_path: str, lang_hint: str | None = None) -> str:
        """Transcribe a dictation file. Saaras takes no language field, so `lang_hint` is not sent; the mode handles Hindi-English mix.

        WAV files over 30 seconds are split into 30 second clips (the synchronous API's limit) and the transcripts joined.
        """
        p = Path(audio_path)
        data = p.read_bytes()
        self._gate("speech_to_text", nbytes=len(data))
        s = sarvam_config()["speech_to_text"]
        clips = _split_wav(data, float(s["max_seconds"])) if p.suffix.lower() == ".wav" else [data]
        return " ".join(self.api.speech_to_text(c, p.name if len(clips) == 1 else f"part{i}.wav").transcript.strip() for i, c in enumerate(clips)).strip()


class SarvamLLMClient(_Base, LLMClient):
    """Sarvam-105B through chat completions (OpenAI-style; `response_format` for structured output).

    `data` pins the data class: CLIENT_TEXT for agent roles (every outbound message is boundary-checked) or PUBLIC for the
    independent non-Qwen labeler/teacher option (public court orders only). `where` is 'ada' for agent roles so the agents' own
    `guard_outbound` also applies, and 'api' for labeler/teacher.
    """

    name = "sarvam"

    def __init__(
        self, model: str | None = None, *, api: SarvamApi | None = None, data: DataClass = DataClass.CLIENT_TEXT,
        where: str = "api", role: str | None = None, scope: SarvamScope | None = None,
    ) -> None:  # fmt: skip
        """Configure the client; nothing is sent until the first call."""
        _Base.__init__(self, api, scope)
        self.model_id = model or sarvam_config()["chat"]["model"]
        self.data = data
        self.where = where
        self.role = role

    def _chat_scope(self) -> SarvamScope:
        base = self._scope or current_scope()
        return dataclasses.replace(base, data=self.data) if base.data is not self.data else base

    def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None) -> str:
        """One chat call from a single prompt."""
        return self.chat(to_messages(prompt), max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)

    def chat(
        self, messages: list[dict[str, str]], max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None
    ) -> str:
        """Chat call. The whole message list is policy- and boundary-checked first; a schema asks for structured JSON."""
        authorize("chat", self._chat_scope(), payload={"messages": messages})
        res = self.api.chat(messages, model=self.model_id, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)
        self.record_usage(res.prompt_tokens, res.completion_tokens)
        text = strip_thinking(res.text)
        if not text.strip():
            raise SarvamError("Sarvam chat returned an empty answer")
        return text

    def count_tokens(self, text: str) -> int:
        """Estimate (the API reports exact usage per call)."""
        return approx_tokens(text)


class SarvamTts(_Base):
    """Bulbul text-to-speech: T8 synthetic dictation (public/constructed text) and the optional read-back audio."""

    name = "sarvam-bulbul"

    def synthesize(self, text: str, language: str = "en", speaker: str | None = None) -> bytes:
        """WAV bytes of `text`. Inside `public_scope()` for constructed text; client text (a read-back) needs pseudonymised mode
        and a boundary pass, or consent when it is not pseudonymised."""
        self._gate("text_to_speech", text=text)
        return self.api.text_to_speech(text, language, speaker).audio


class SarvamLangId(_Base):
    """`/text-lid`: language and script of a text."""

    name = "sarvam-lid"

    def identify(self, text: str) -> LidResult:
        """Language code ('hi-IN') and script code ('Deva')."""
        self._gate("language_id", text=text[:1000])
        return self.api.identify_language(text)

    def script(self, text: str) -> str | None:
        """'devanagari' or 'latin' (the labels of `ingestion.hindi.detect_script`), None for other scripts."""
        code = (self.identify(text).script_code or "").lower()
        return {"deva": "devanagari", "latn": "latin"}.get(code)

    def language(self, text: str) -> str | None:
        """Two-letter language ('hi')."""
        return from_bcp47(self.identify(text).language_code)
