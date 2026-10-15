"""OfflineLLM: a deterministic, template- and rule-based stand-in for every language model (plan §12, §3.3).

It is NOT a language model and says so: `name` is 'offline-template', `is_offline` is True, and every agent call made
through it is logged with `offline: true`. It lets the whole system run end to end with no GPU, no vLLM and no network,
and it is exactly reproducible: the same prompt always gives the same output (no randomness, no clock).

How it answers a prompt written in the shared layout (`models.prompting`):

1. a handler registered for the prompt's task id (`register_offline_handler('vakeel.draft_ground', fn)`) builds the
   answer from the evidence in the INPUT JSON. Each agent package registers the rule-based handlers for its own tasks;
2. with a JSON schema, the answer is coerced so it validates by construction (`models.json_schema.coerce`); with no
   handler, a conservative instance is built from the evidence alone (`fill`): values are copied, never invented;
3. on a repair attempt the handler is skipped and the conservative instance is returned, so the repair loop converges;
4. free text with no handler is an extractive, clearly labelled template.

Instructions inside the evidence are never followed: handlers only read data, and the generic path only copies values.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from vakeel_sahayak.models.base import LLMClient, approx_tokens
from vakeel_sahayak.models.json_schema import coerce, fill, is_valid
from vakeel_sahayak.models.prompting import ParsedPrompt, parse_prompt, render_messages

OFFLINE_NAME = "offline-template"
OFFLINE_LABEL = "OFFLINE TEMPLATE OUTPUT (deterministic rules, no language model)"


@dataclass(frozen=True)
class OfflineRequest:
    """What an offline handler receives."""

    task: str | None
    instructions: str
    data: dict[str, Any]
    prompt: str
    schema: dict[str, Any] | None
    role: str | None = None
    repair: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def case(self) -> dict[str, Any]:
        """The private (pseudonymised) part of the input, by convention under 'case'."""
        value = self.data.get("case")
        return value if isinstance(value, dict) else {}

    @property
    def corpus(self) -> dict[str, Any]:
        """The public part of the input (paragraphs, statutes), by convention under 'corpus'."""
        value = self.data.get("corpus")
        return value if isinstance(value, dict) else {}


OfflineHandler = Callable[[OfflineRequest], Any]
_HANDLERS: dict[str, OfflineHandler] = {}


def register_offline_handler(task: str, handler: OfflineHandler) -> None:
    """Register the rule-based answer for one task id (the latest registration wins).

    Args:
        task: dotted task id used in `render_prompt` (e.g. 'abhiyojak.raise_objections')
        handler: returns a JSON-able value (structured calls) or a string (free text) built only from the request's data
    """
    _HANDLERS[task] = handler


def offline_handler(task: str) -> Callable[[OfflineHandler], OfflineHandler]:
    """Decorator form of `register_offline_handler`."""

    def deco(fn: OfflineHandler) -> OfflineHandler:
        register_offline_handler(task, fn)
        return fn

    return deco


def unregister_offline_handler(task: str) -> None:
    """Remove a handler (tests)."""
    _HANDLERS.pop(task, None)


def offline_handlers() -> dict[str, OfflineHandler]:
    """The registered handlers, by task id."""
    return dict(_HANDLERS)


_SENT = re.compile(r"(?<=[.!?।])\s+")


def _strings(value: Any, out: list[str]) -> list[str]:
    """Every string in a JSON value, in order."""
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _strings(v, out)
    elif isinstance(value, list):
        for v in value:
            _strings(v, out)
    return out


def extractive_summary(data: Any, max_sentences: int = 2) -> str:
    """The first sentences of the evidence's text, verbatim (the generic free-text answer)."""
    texts = [t.strip() for t in _strings(data, []) if t.strip() and not t.strip().startswith("<<<")]
    sentences: list[str] = []
    for t in texts:
        for s in _SENT.split(t):
            if s.strip():
                sentences.append(s.strip())
            if len(sentences) >= max_sentences:
                return " ".join(sentences)
    return " ".join(sentences)


class OfflineLLM(LLMClient):
    """Deterministic template/rule client with the LLMClient interface; schema-valid outputs from the given evidence."""

    name = OFFLINE_NAME
    model_id = OFFLINE_NAME
    is_offline = True
    label = OFFLINE_LABEL

    def __init__(self, role: str | None = None, where: str | None = None) -> None:
        """Create the client.

        Args:
            role: the model role it stands in for ('agents_14b', 'extractor_4b', ...); handlers may read it
            where: where the real model would run ('ada' or 'laptop'); agents apply the privacy boundary for 'ada'
        """
        self.role = role
        if where:
            self.where = where

    def answer(self, parsed: ParsedPrompt, json_schema: dict | None = None) -> Any:
        """The answer value (before JSON encoding) for a parsed prompt."""
        schema = json_schema if json_schema is not None else parsed.schema
        req = OfflineRequest(
            task=parsed.task, instructions=parsed.instructions, data=parsed.data, prompt=parsed.raw,
            schema=schema, role=self.role, repair=parsed.repair,
        )  # fmt: skip
        handler = _HANDLERS.get(parsed.task or "")
        evidence = parsed.data.get("prefill", parsed.data) if isinstance(parsed.data, dict) else parsed.data
        if schema is not None:
            if handler is not None and parsed.repair is None:
                out = handler(req)
                if isinstance(out, str):
                    try:
                        out = json.loads(out)
                    except ValueError:
                        out = None
                if out is not None:
                    return out if is_valid(out, schema) else coerce(out, schema, evidence)
            return fill(schema, evidence)
        if handler is not None:
            out = handler(req)
            return out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, sort_keys=False, default=str)
        summary = extractive_summary(parsed.data) if parsed.data else ""
        return f"[{OFFLINE_LABEL}] {summary}".strip()

    def generate(
        self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None
    ) -> str:
        """Answer deterministically (temperature and max_tokens are accepted and ignored: output never varies).

        Args:
            prompt: a prompt, ideally in the `models.prompting` layout
            max_tokens: ignored
            temperature: ignored
            json_schema: when given, the reply is JSON valid against it

        Returns:
            The reply text.
        """
        value = self.answer(parse_prompt(prompt), json_schema)
        text = value if isinstance(value, str) and json_schema is None else json.dumps(value, ensure_ascii=False, default=str)
        self.record_usage(self.count_tokens(prompt), self.count_tokens(text))
        return text

    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        json_schema: dict | None = None,
    ) -> str:
        """Chat by flattening the messages (the last user turn carries the shared layout)."""
        return self.generate(render_messages(messages), max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)

    def count_tokens(self, text: str) -> int:
        """The deterministic estimate used everywhere offline."""
        return approx_tokens(text)
