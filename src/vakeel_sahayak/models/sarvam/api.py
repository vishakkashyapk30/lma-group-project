"""Typed wrappers over the Sarvam endpoints (request and response mapping only; the privacy gate is in `policy`, the
interface adapters are in `adapters`).

Facts (fetched from docs.sarvam.ai on 2026-10-19, see configs/models.yaml for the names and paths):

- chat: POST /v1/chat/completions, OpenAI-style `messages`, `max_tokens`, `temperature`, `response_format`
  (`json_schema` | `json_object`), `reasoning_effort` (null disables thinking), reply in `choices[0].message.content`, `usage`.
- translate: POST /translate {input, source_language_code, target_language_code, model, mode, numerals_format, ...} ->
  {request_id, translated_text, source_language_code}. Input limit 1000 chars (mayura:v1) or 2000 (sarvam-translate:v1).
- speech-to-text: POST /speech-to-text multipart {file, model, mode} -> {request_id, transcript, language_code}; 30 s per request.
- text-to-speech: POST /text-to-speech {text, language_code, speaker, model, speech_sample_rate} -> {request_id, audios:[base64 WAV]}.
- transliterate: POST /transliterate {input, source_language_code, target_language_code, ...} -> {transliterated_text, ...}.
- language id: POST /text-lid {input} -> {request_id, language_code, script_code}.
- Vision (document intelligence): POST /doc-ai/v1/job/digitise multipart {file, language, output_format} -> {job_id, status};
  GET /doc-ai/v1/job/{id}/status (pending, running | completed, partially_completed, failed, rejected);
  GET /doc-ai/v1/job/{id}/download-url -> {method, url}; the download is a ZIP (primary file, metadata/page_NNN.json, manifest.json).
"""

from __future__ import annotations

import base64
import io
import re
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from vakeel_sahayak.models.sarvam.config import sarvam_config
from vakeel_sahayak.models.sarvam.errors import SarvamError, SarvamHttpError
from vakeel_sahayak.models.sarvam.http import SarvamHttp

TERMINAL = frozenset({"completed", "partially_completed", "failed", "rejected"})
_TAGS = re.compile(r"<[^>]+>")


def to_bcp47(code: str | None) -> str | None:
    """'hi' -> 'hi-IN', 'en' -> 'en-IN' (Sarvam uses BCP-47 codes with the -IN region); codes already regional pass through."""
    if not code:
        return None
    low = code.strip()
    return low if "-" in low else f"{low.lower()}-IN"


def from_bcp47(code: str | None) -> str | None:
    """'hi-IN' -> 'hi'."""
    return code.split("-")[0].lower() if code else None


@dataclass(frozen=True)
class ChatResult:
    """One chat completion."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str | None = None
    model: str = ""


@dataclass(frozen=True)
class TranslateResult:
    """One translation."""

    text: str
    source_language_code: str | None
    request_id: str | None = None


@dataclass(frozen=True)
class SttResult:
    """One transcription."""

    transcript: str
    language_code: str | None
    request_id: str | None = None


@dataclass(frozen=True)
class TtsResult:
    """Synthesised speech: WAV bytes (the API returns base64 WAV chunks, joined then decoded)."""

    audio: bytes
    request_id: str | None = None


@dataclass(frozen=True)
class LidResult:
    """Language and script of a text."""

    language_code: str | None
    script_code: str | None


@dataclass
class VisionResult:
    """A digitised document or page: markdown text and the job's page counts."""

    text: str
    job_id: str
    status: str
    pages_total: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    files: list[str] = field(default_factory=list)

    @property
    def success_ratio(self) -> float:
        """Share of pages that were processed successfully (the honest stand-in for an OCR confidence)."""
        return self.pages_succeeded / self.pages_total if self.pages_total else 0.0


def unpack_digitised(blob: bytes, output_format: str = "md") -> tuple[str, list[str]]:
    """Text of a digitise ZIP: the primary output file(s) (not `metadata/` or `manifest.json`), in name order.

    Returns:
        (text, names of the files read). HTML output has its tags stripped. A non-ZIP body is treated as the text itself.
    """
    if not zipfile.is_zipfile(io.BytesIO(blob)):
        return blob.decode("utf-8", errors="replace").strip(), []
    ext = {"md": ".md", "html": ".html", "json": ".json"}.get(output_format, ".md")
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = sorted(n for n in zf.namelist() if not n.endswith("/") and not n.startswith("metadata/") and n != "manifest.json")
        chosen = [n for n in names if n.endswith(ext)] or names
        parts = [zf.read(n).decode("utf-8", errors="replace") for n in chosen]
    text = "\n\n".join(p.strip() for p in parts if p.strip())
    if output_format == "html":
        text = re.sub(r"[ \t]+", " ", _TAGS.sub(" ", text)).strip()
    return text, chosen


class SarvamApi:
    """The Sarvam endpoints as typed methods."""

    def __init__(self, http: SarvamHttp | None = None, config: dict[str, Any] | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        """Wrap a transport (default: one reading SARVAM_API_KEY) with the settings (default: configs/models.yaml)."""
        self.http = http or SarvamHttp()
        self.cfg = config or sarvam_config()
        self._sleep = sleep

    def _ep(self, name: str, **fmt: str) -> str:
        return str(self.cfg["endpoints"][name]).format(**fmt)

    # ------------------------------------------------------------------ chat

    def chat_body(
        self, messages: list[dict[str, str]], *, model: str | None = None, max_tokens: int = 1024, temperature: float = 0.0,
        json_schema: dict | None = None, json_mode_only: bool = False, reasoning_effort: Any = "config",
    ) -> dict[str, Any]:  # fmt: skip
        """The request body of a chat call."""
        c = self.cfg["chat"]
        body: dict[str, Any] = {
            "model": model or c["model"],
            "messages": messages,
            "max_tokens": min(int(max_tokens), int(c["max_tokens_cap"])),
            "temperature": temperature,
            "reasoning_effort": c.get("reasoning_effort") if reasoning_effort == "config" else reasoning_effort,
        }
        if json_schema is not None:
            if json_mode_only:
                body["response_format"] = {"type": "json_object"}
            else:
                body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "output", "strict": bool(c.get("strict_json")), "schema": json_schema},
                }
        return body

    @staticmethod
    def parse_chat(data: dict[str, Any]) -> ChatResult:
        """Read a chat response (content, finish reason and usage)."""
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        usage = data.get("usage") or {}
        text = str(msg.get("content") or "")
        if not text.strip() and choice.get("finish_reason") == "length":
            raise SarvamError("Sarvam chat stopped at the token limit before any answer (thinking used the budget); raise max_tokens or disable reasoning")
        return ChatResult(text, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)), choice.get("finish_reason"), str(data.get("model") or ""))

    def chat(self, messages: list[dict[str, str]], **kw: Any) -> ChatResult:
        """Chat completion. With `json_schema` a `response_format` is sent; when the API rejects it (400/422) the call is
        repeated once in plain JSON mode, and the caller's validation does the rest."""
        path = self._ep("chat")
        try:
            resp = self.http.request("POST", path, json=self.chat_body(messages, **kw))
        except SarvamHttpError as exc:
            if kw.get("json_schema") is None or exc.status not in (400, 422):
                raise
            resp = self.http.request("POST", path, json=self.chat_body(messages, **{**kw, "json_mode_only": True}))
        return self.parse_chat(resp.json())

    # ------------------------------------------------------------------ text

    def translate_body(self, text: str, src: str | None, tgt: str, model: str | None = None, mode: str | None = None) -> dict[str, Any]:
        """The request body of a translate call ('auto' source when `src` is None)."""
        t = self.cfg["translate"]
        name = model or t["model"]
        limit = int(t["max_chars"].get(name, 1000))
        if len(text) > limit:
            raise ValueError(f"{name} accepts at most {limit} characters per call, got {len(text)} (split the text first)")
        return {
            "input": text,
            "source_language_code": to_bcp47(src) or "auto",
            "target_language_code": to_bcp47(tgt),
            "model": name,
            "mode": mode or t["mode"],
            "numerals_format": t["numerals_format"],
        }

    def translate(self, text: str, src: str | None, tgt: str, model: str | None = None, mode: str | None = None) -> TranslateResult:
        """Translate one text (within the model's character limit)."""
        d = self.http.request("POST", self._ep("translate"), json=self.translate_body(text, src, tgt, model, mode)).json()
        return TranslateResult(str(d.get("translated_text", "")), d.get("source_language_code"), d.get("request_id"))

    def transliterate(self, text: str, src: str, tgt: str, spoken_form: bool = False) -> str:
        """Transliterate between scripts (for example hi-IN to en-IN); at most 1000 characters."""
        if len(text) > 1000:
            raise ValueError("transliterate accepts under 1000 characters per call")
        body = {"input": text, "source_language_code": to_bcp47(src), "target_language_code": to_bcp47(tgt), "spoken_form": spoken_form}
        return str(self.http.request("POST", self._ep("transliterate"), json=body).json().get("transliterated_text", ""))

    def identify_language(self, text: str) -> LidResult:
        """Language and script of a text (the first 1000 characters are sent)."""
        d = self.http.request("POST", self._ep("language_id"), json={"input": text[:1000]}).json()
        return LidResult(d.get("language_code"), d.get("script_code"))

    # ------------------------------------------------------------------ speech

    def speech_to_text(self, audio: bytes, filename: str = "audio.wav", model: str | None = None, mode: str | None = None) -> SttResult:
        """Transcribe one clip (30 seconds at most; the adapter splits longer WAV files)."""
        s = self.cfg["speech_to_text"]
        data = {"model": model or s["model"], "mode": mode or s["mode"]}
        d = self.http.request("POST", self._ep("speech_to_text"), data=data, files={"file": (filename, audio)}).json()
        return SttResult(str(d.get("transcript") or ""), d.get("language_code"), d.get("request_id"))

    def text_to_speech(self, text: str, language: str = "en", speaker: str | None = None, model: str | None = None) -> TtsResult:
        """Synthesise speech (WAV)."""
        t = self.cfg["text_to_speech"]
        body = {
            "text": text, "language_code": to_bcp47(language), "speaker": speaker or t["speaker"], "model": model or t["model"],
            "speech_sample_rate": int(t["sample_rate"]),
        }  # fmt: skip
        d = self.http.request("POST", self._ep("text_to_speech"), json=body).json()
        return TtsResult(base64.b64decode("".join(d.get("audios") or [])), d.get("request_id"))

    # ------------------------------------------------------------------ vision (document intelligence)

    def vision_submit(self, content: bytes, filename: str, content_type: str, language: str | None, output_format: str | None = None) -> str:
        """Create and submit a digitise job; returns the job id."""
        fmt = output_format or self.cfg["vision"]["output_format"]
        data = {"output_format": fmt, **({"language": to_bcp47(language)} if language else {})}
        d = self.http.request("POST", self._ep("vision_digitise"), data=data, files={"file": (filename, content, content_type)}).json()
        if not d.get("job_id"):
            raise SarvamError("Sarvam Vision did not return a job id")
        return str(d["job_id"])

    def vision_status(self, job_id: str) -> dict[str, Any]:
        """Job status: {'status', 'usage': {pages_total, pages_succeeded, pages_failed, ...}, ...}."""
        return dict(self.http.request("GET", self._ep("vision_status", job_id=job_id)).json())

    def vision_download(self, job_id: str) -> bytes:
        """The result ZIP (the pre-signed URL is fetched without the API key)."""
        d = self.http.request("GET", self._ep("vision_download", job_id=job_id)).json()
        return self.http.get_external(str(d["url"])).content

    def vision_wait(self, job_id: str) -> dict[str, Any]:
        """Poll until the job is terminal (poll interval and timeout from `sarvam.vision`)."""
        v = self.cfg["vision"]
        waited, step = 0.0, float(v["poll_interval_s"])
        while True:
            st = self.vision_status(job_id)
            if str(st.get("status")) in TERMINAL:
                return st
            if waited >= float(v["timeout_s"]):
                raise SarvamError(f"Sarvam Vision job {job_id} did not finish within {v['timeout_s']} s")
            self._sleep(step)
            waited += step

    def digitise(self, content: bytes, filename: str, content_type: str, language: str | None = None, output_format: str | None = None) -> VisionResult:
        """Submit, wait, download and unpack: one document or page image to text.

        Raises:
            SarvamError: the job failed or was rejected, or produced no pages.
        """
        fmt = output_format or self.cfg["vision"]["output_format"]
        job = self.vision_submit(content, filename, content_type, language, fmt)
        st = self.vision_wait(job)
        status = str(st.get("status"))
        usage = st.get("usage") or {}
        if status in ("failed", "rejected"):
            raise SarvamError(f"Sarvam Vision job {status}")
        text, files = unpack_digitised(self.vision_download(job), fmt)
        return VisionResult(
            text, job, status, int(usage.get("pages_total", 0)), int(usage.get("pages_succeeded", 0)), int(usage.get("pages_failed", 0)), files
        )


class AsyncSarvamApi:
    """Async chat, translate and language-id (the calls an async caller makes in bulk, such as gold labelling)."""

    def __init__(self, http: SarvamHttp | None = None, config: dict[str, Any] | None = None) -> None:
        """Wrap a transport and settings, as `SarvamApi`."""
        self.http = http or SarvamHttp()
        self._sync = SarvamApi(self.http, config)

    async def chat(self, messages: list[dict[str, str]], **kw: Any) -> ChatResult:
        """Async `SarvamApi.chat` (same JSON-mode fallback)."""
        path = self._sync._ep("chat")
        try:
            resp = await self.http.arequest("POST", path, json=self._sync.chat_body(messages, **kw))
        except SarvamHttpError as exc:
            if kw.get("json_schema") is None or exc.status not in (400, 422):
                raise
            resp = await self.http.arequest("POST", path, json=self._sync.chat_body(messages, **{**kw, "json_mode_only": True}))
        return self._sync.parse_chat(resp.json())

    async def translate(self, text: str, src: str | None, tgt: str, model: str | None = None, mode: str | None = None) -> TranslateResult:
        """Async `SarvamApi.translate`."""
        body = self._sync.translate_body(text, src, tgt, model, mode)
        d = (await self.http.arequest("POST", self._sync._ep("translate"), json=body)).json()
        return TranslateResult(str(d.get("translated_text", "")), d.get("source_language_code"), d.get("request_id"))

    async def identify_language(self, text: str) -> LidResult:
        """Async `SarvamApi.identify_language`."""
        d = (await self.http.arequest("POST", self._sync._ep("language_id"), json={"input": text[:1000]})).json()
        return LidResult(d.get("language_code"), d.get("script_code"))


__all__ = ["AsyncSarvamApi", "SarvamApi"]
