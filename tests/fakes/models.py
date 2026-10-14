"""Deterministic fake model clients implementing the interfaces in `vakeel_sahayak.models.base`."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from vakeel_sahayak.models.base import (
    AsrClient,
    EmbeddingClient,
    LLMClient,
    NliClient,
    OcrClient,
    TranslationClient,
    VisionClient,
)

Responder = str | dict | list | BaseModel | Callable[..., Any]


@dataclass
class LLMCall:
    """One recorded `generate` call."""

    prompt: str
    schema_title: str | None
    json_schema: dict | None
    max_tokens: int
    completion: str


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value, ensure_ascii=False)


class Seq:
    """A per-call sequence of responders: the n-th call gets the n-th item, the last item repeats."""

    def __init__(self, *items: Any) -> None:
        self.items = list(items)
        self.i = 0

    def next(self) -> Any:
        item = self.items[min(self.i, len(self.items) - 1)]
        self.i += 1
        return item


class ScriptedLLM(LLMClient):
    """A scripted LLM.

    * `by_schema`: schema title -> responder, used when `json_schema` is given (title = pydantic class name).
    * `by_prompt`: ordered `(substring_or_regex, responder)` pairs, used for calls without a JSON schema (and as a
      fallback for schema calls whose title is not scripted).
    * A responder is a literal (str / dict / list / pydantic model, JSON-encoded unless already a str), a `Seq(...)`
      giving one literal per call, or a callable `(prompt, json_schema) -> literal`.
    * `where`: "ada" or "laptop"; lets privacy tests assert on what an Ada-side client ever received (`prompts`).
    * `strict=True` raises AssertionError on an unscripted call so tests notice unexpected LLM use.
    """

    def __init__(
        self,
        by_schema: dict[str, Responder] | None = None,
        by_prompt: list[tuple[str | re.Pattern, Responder]] | None = None,
        default: str | None = None,
        strict: bool = True,
        where: str = "laptop",
    ) -> None:
        self.by_schema = dict(by_schema or {})
        self.by_prompt = list(by_prompt or [])
        self.default = default
        self.strict = strict
        self.where = where
        self.calls: list[LLMCall] = []

    @staticmethod
    def _resolve(responder: Any, prompt: str, schema: dict | None) -> str:
        if isinstance(responder, Seq):
            responder = responder.next()
        if callable(responder) and not isinstance(responder, (BaseModel, type)):
            responder = responder(prompt, schema)
        return _to_text(responder)

    def generate(
        self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None
    ) -> str:
        title = (json_schema or {}).get("title")
        completion: str | None = None
        if json_schema is not None and title in self.by_schema:
            completion = self._resolve(self.by_schema[title], prompt, json_schema)
        else:
            for pattern, responder in self.by_prompt:
                hit = pattern.search(prompt) if isinstance(pattern, re.Pattern) else pattern in prompt
                if hit:
                    completion = self._resolve(responder, prompt, json_schema)
                    break
        if completion is None:
            if self.strict and self.default is None:
                raise AssertionError(f"ScriptedLLM: no script for schema={title!r}, prompt starts {prompt[:120]!r}")
            completion = self.default or ""
        self.calls.append(LLMCall(prompt, title, json_schema, max_tokens, completion))
        return completion

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    @property
    def prompts(self) -> list[str]:
        return [c.prompt for c in self.calls]

    @property
    def total_tokens(self) -> int:
        return sum(self.count_tokens(c.prompt) + self.count_tokens(c.completion) for c in self.calls)

    def calls_for(self, schema_title: str) -> list[LLMCall]:
        return [c for c in self.calls if c.schema_title == schema_title]


class FakeNli(NliClient):
    """Entailment by overlap: 0.95 when every number/date token and >=60% of content words of the hypothesis occur in the
    premise, else 0.05. Changing a date, number or name in a hypothesis therefore flips it to 'unsupported'."""

    _STOP = {"the", "a", "an", "of", "in", "on", "was", "is", "to", "and", "by", "for", "with", "that", "has", "been"}

    def entails(self, premise: str, hypothesis: str) -> float:
        tok = lambda s: re.findall(r"[\w.\-]+", s.lower())  # noqa: E731
        p, h = set(tok(premise)), tok(hypothesis)
        digits = [t for t in h if any(c.isdigit() for c in t)]
        if any(t not in p for t in digits):
            return 0.05
        words = [t for t in h if t not in self._STOP and not any(c.isdigit() for c in t)]
        if not words:
            return 0.95
        return 0.95 if sum(t in p for t in words) / len(words) >= 0.6 else 0.05


class FakeOcr(OcrClient):
    """OCR keyed by the exact image bytes: `pages={b'img': ('text', 0.9)}`. Unknown images raise (like an OCR crash)."""

    def __init__(self, pages: dict[bytes, tuple[str, float]] | None = None, fail_on: set[bytes] | None = None) -> None:
        self.pages = dict(pages or {})
        self.fail_on = set(fail_on or ())
        self.calls: list[tuple[bytes, str]] = []

    def ocr(self, image: bytes, lang: str) -> tuple[str, float, list[list[float]]]:
        self.calls.append((image, lang))
        if image in self.fail_on:
            raise RuntimeError("fake OCR crash")
        text, conf = self.pages[image]
        return text, conf, [[0.0, 0.0, 100.0, 20.0]]


class FakeVision(VisionClient):
    """Vision transcription keyed by image bytes; unknown images return '' (an unreadable page)."""

    def __init__(self, pages: dict[bytes, str] | None = None) -> None:
        self.pages = dict(pages or {})
        self.calls: list[bytes] = []

    def transcribe_page(self, image: bytes, lang_hint: str | None = None) -> str:
        self.calls.append(image)
        return self.pages.get(image, "")


class FakeAsr(AsrClient):
    """ASR keyed by audio path."""

    def __init__(self, transcripts: dict[str, str] | None = None) -> None:
        self.transcripts = dict(transcripts or {})

    def transcribe(self, audio_path: str, lang_hint: str | None = None) -> str:
        return self.transcripts[audio_path]


class FakeTranslator(TranslationClient):
    """Hindi -> English by phrase table; unknown text is returned as '[en] <text>' so the call is visible."""

    TABLE = {
        "प्रथम सूचना रिपोर्ट सं. 112/2024 दिनांक 14.08.2024": "FIR No. 112/2024 dated 14.08.2024",
        "धारा 318(4) बी.एन.एस.": "Section 318(4) BNS",
        "घटना दिनांक 10.08.2024": "date of occurrence 10.08.2024",
    }

    def __init__(self, table: dict[str, str] | None = None) -> None:
        self.table = {**self.TABLE, **(table or {})}
        self.calls: list[str] = []

    def translate(self, text: str, src: str = "hi", tgt: str = "en") -> str:
        self.calls.append(text)
        return self.table.get(text, f"[en] {text}")


class FakeEmbedder(EmbeddingClient):
    """Hash-based bag-of-words embeddings (dimension 32); identical text -> identical vector."""

    DIM = 32

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * self.DIM
            for w in re.findall(r"\w+", t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.DIM] += 1.0
            n = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / n for x in v])
        return out
