"""Abstract interfaces for every model type (plan §12).

The abstract methods are the contract every client implements (`LLMClient.generate` and `count_tokens`, `NliClient.entails`,
...). Everything else on these classes is concrete and built on those methods, so a minimal client (a test fake, the
offline client, vLLM, the local 4B) gets chat, structured generation and token accounting for free:

- `LLMClient.complete` returns a `Completion` with the token counts of one call; `usage` accumulates them;
- `LLMClient.chat` takes role/content messages (real clients override it to use the chat API);
- `LLMClient.structured` generates against a JSON schema or a pydantic model with validation and repair
  (`orchestration.structured_output`);
- `NliClient.judge` / `supports` turn an entailment score into a verdict against a dev-tuned threshold.
"""

from __future__ import annotations

import re
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ModelUnavailable(RuntimeError):
    """A model backend or its optional dependency is missing. Tools map it to a `model_unavailable` ToolError.

    Attributes:
        extra: the pyproject extra that installs the backend (for example 'ocr'), or None.
    """

    def __init__(self, message: str, extra: str | None = None) -> None:
        """Say what is missing and which extra installs it."""
        hint = f" (install the '{extra}' extra: pip install 'vakeel_sahayak[{extra}]')" if extra else ""
        super().__init__(message + hint)
        self.extra = extra


class LabelerUnavailable(ModelUnavailable, NotImplementedError):
    """The evaluation labeler cannot run here. Also a NotImplementedError, so the gold pipeline falls back to rule-only records."""


_PIECE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def approx_tokens(text: str) -> int:
    """Deterministic token estimate (words and punctuation, times 4/3) for clients without a tokenizer."""
    if not text:
        return 0
    pieces = len(_PIECE.findall(text))
    return max(1, pieces + pieces // 3)


def strip_thinking(text: str) -> str:
    """Remove a Qwen3 `<think>...</think>` block (thinking is switched off, but a stray block must not reach a parser)."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip() if "<think>" in text else text


def model_family(model_id: str | None) -> str:
    """Model family of a checkpoint id ('Qwen/Qwen3-32B-AWQ' -> 'qwen'); used for the teacher/labeler family rule (plan §17)."""
    low = (model_id or "").lower()
    for family, cues in (
        ("qwen", ("qwen",)),
        ("llama", ("llama",)),
        ("mistral", ("mistral", "mixtral", "ministral", "magistral", "codestral")),
        ("deberta", ("deberta",)),
        ("gemma", ("gemma",)),
        ("phi", ("phi-",)),
    ):
        if any(c in low for c in cues):
            return family
    name = low.rsplit("/", 1)[-1]
    return re.split(r"[-_.0-9]", name, maxsplit=1)[0] or "unknown"


@dataclass
class TokenUsage:
    """Tokens a client has spent (plan §6.2 budgets)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    @property
    def total(self) -> int:
        """Prompt plus completion tokens."""
        return self.prompt_tokens + self.completion_tokens

    def add(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Add one call."""
        self.prompt_tokens += int(prompt_tokens)
        self.completion_tokens += int(completion_tokens)
        self.calls += 1


@dataclass(frozen=True)
class Completion:
    """One generation with its token counts."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str = "unknown"
    offline: bool = False

    @property
    def total_tokens(self) -> int:
        """Prompt plus completion tokens."""
        return self.prompt_tokens + self.completion_tokens


class LLMClient(ABC):
    """Text-generation client interface.

    Class attributes describe the backend: `name` (shown in logs), `model_id`, `is_offline` (True only for the
    deterministic offline client) and `where` ('laptop', 'ada' or 'api'; payloads to 'ada' must be pseudonymised).
    """

    name: str = "llm"
    model_id: str | None = None
    is_offline: bool = False
    where: str = "laptop"

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

    # ------------------------------------------------------------------ token accounting (concrete)

    def _accounting(self) -> tuple[TokenUsage, threading.local, threading.Lock]:
        """Per-client usage, per-thread last-call slot and lock, created on first use (subclasses need not call super().__init__)."""
        state = self.__dict__.get("_vs_accounting")
        if state is None:
            state = (TokenUsage(), threading.local(), threading.Lock())
            self.__dict__["_vs_accounting"] = state
        return state

    @property
    def usage(self) -> TokenUsage:
        """Tokens spent through this client so far (all threads)."""
        return self._accounting()[0]

    def record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Record one call's tokens. Backends that know the real counts (vLLM `usage`) call this from `generate`."""
        usage, local, lock = self._accounting()
        with lock:
            usage.add(prompt_tokens, completion_tokens)
        local.last = (int(prompt_tokens), int(completion_tokens))

    def _count(self, text: str) -> int:
        """`count_tokens`, falling back to the estimate when the backend cannot count."""
        try:
            return int(self.count_tokens(text))
        except (NotImplementedError, ModelUnavailable):
            return approx_tokens(text)

    def complete(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None
    ) -> Completion:
        """`generate` plus the call's token counts (reported by the backend when it can, else counted).

        Args:
            prompt: the full prompt
            max_tokens: completion limit
            temperature: 0.0 for deterministic runs
            json_schema: constrain decoding to this schema

        Returns:
            Completion.
        """
        _, local, _ = self._accounting()
        local.last = None
        text = self.generate(prompt, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)
        if getattr(local, "last", None) is None:
            self.record_usage(self._count(prompt), self._count(text))
        p, c = local.last
        return Completion(text=text, prompt_tokens=p, completion_tokens=c, model=self.model_id or self.name, offline=self.is_offline)

    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        json_schema: dict | None = None,
    ) -> str:
        """Generate from role/content messages ('system', 'user', 'assistant').

        The default renders the messages into one prompt (`models.prompting.render_messages`) and calls `generate`;
        clients with a chat API override this.

        Args:
            messages: [{'role': ..., 'content': ...}, ...]
            max_tokens: completion limit
            temperature: sampling temperature
            json_schema: constrain decoding to this schema

        Returns:
            Completion text.
        """
        from vakeel_sahayak.models.prompting import render_messages

        return self.generate(render_messages(messages), max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)

    def structured(
        self, prompt: str, schema: Any, *, max_tokens: int = 2048, temperature: float = 0.0, retries: int = 2
    ) -> Any:
        """Schema-constrained generation with validation and repair (see `orchestration.structured_output`).

        Args:
            prompt: the full prompt
            schema: a pydantic model class or a JSON schema dict
            max_tokens: completion limit per attempt
            temperature: sampling temperature
            retries: repair attempts after the first

        Returns:
            A validated model instance (pydantic schema) or a JSON value (dict schema).
        """
        from vakeel_sahayak.orchestration.structured_output import constrained_generate

        return constrained_generate(self, prompt, schema, max_tokens=max_tokens, temperature=temperature, retries=retries)


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


@dataclass(frozen=True)
class NliVerdict:
    """An NLI decision: the entailment score, the threshold it was held against, and (offline) why."""

    score: float
    threshold: float
    supported: bool
    label: str  # 'entailment' | 'contradiction' | 'neutral'
    reasons: tuple[str, ...] = field(default_factory=tuple)


class NliClient(ABC):
    """NLI / fact-support interface.

    `default_threshold` is the backend's untuned cut-off; the dev-tuned values live in configs/thresholds.yaml
    (`nli.*_min`) and are read by `models.nli.nli_threshold`.
    """

    name: str = "nli"
    is_offline: bool = False
    default_threshold: float = 0.5

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

    def entails_batch(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Scores for (premise, hypothesis) pairs, in order."""
        return [self.entails(p, h) for p, h in pairs]

    def judge(self, premise: str, hypothesis: str, threshold: float | None = None) -> NliVerdict:
        """Score a pair and decide it against `threshold` (default: `default_threshold`).

        Args:
            premise: the source text (dossier quote, cited paragraph)
            hypothesis: the claim or value
            threshold: decision threshold in [0, 1]

        Returns:
            NliVerdict.
        """
        thr = self.default_threshold if threshold is None else float(threshold)
        score = float(self.entails(premise, hypothesis))
        return NliVerdict(score=score, threshold=thr, supported=score >= thr, label="entailment" if score >= thr else "neutral")

    def supports(self, premise: str, hypothesis: str, threshold: float | None = None) -> bool:
        """True when the premise supports the hypothesis at the threshold."""
        return self.judge(premise, hypothesis, threshold).supported


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

NLIClient = NliClient  # the plan's spelling (plan §12)
