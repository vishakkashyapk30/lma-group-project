"""Stand-in for a susceptible model, for ablation A15 and variants S17, S17b, S17c, S17d (the injection defences switched off one at a time and together; claim C37, test set T7).

Switches: `Switches.for_variant('S17')` (`no_typed_handoff`), `'S17b'` (`no_spotlighting`), `'S17c'` (`no_guard`), `'S17d'` (all three; alias A15 is S17).
The defences themselves live in `agents/base.py` (`untrusted`, `flag_instructions`, `_handoff`), `agents/munshi` and `privacy/defences.py`, which also carries the
papers (Design Patterns for Securing LLM Agents against Prompt Injections; CaMeL; Spotlighting; AgentDojo) and the measurement `attack_outcome`.

This module adds the offline stand-in for a susceptible model, so the arms can be told apart without a GPU:

`SusceptibleLLM` wraps any client and, per call, finds where each planted instruction sits in the prompt (`privacy.defences.channel_of`): in the instruction text,
in the data but outside any delimiter block, or inside a delimiter block. It follows the instruction with a probability per channel
(`rates`, default: always in the instruction text and in unmarked data, never inside a block); the decision is a hash of the instruction and the prompt, so it is
deterministic. "Following" is modelled as the instruction's text surfacing in the reply (appended to the longest string of a JSON reply, its free-text part, or to a text reply),
which is what `attack_outcome` looks for. This is a model of susceptibility, not a measurement of any real model: Hines et al. report that delimiting
and datamarking cut attack success on GPT-family models, and small open models may do worse, so the real numbers need the real models (T7 on Ada).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from vakeel_sahayak.models.base import LLMClient
from vakeel_sahayak.privacy.defences import channel_of

DEFAULT_RATES: dict[str, float] = {"instructions": 1.0, "unfenced": 1.0, "fenced": 0.0}


def _longest_string_path(value: Any, path: tuple = ()) -> tuple | None:
    """Path to the longest string in a JSON value (the free-text part of a reply: a quote, an argument, a sentence); None when it has none."""
    best: tuple[int, tuple] | None = None
    if isinstance(value, str):
        return path
    children = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else ()
    for k, v in children:
        sub = _longest_string_path(v, (*path, k))
        if sub is None:
            continue
        node = v
        for step in sub[len(path) + 1:]:
            node = node[step]
        if best is None or len(node) > best[0]:
            best = (len(node), sub)
    return best[1] if best else None


def _append(value: Any, path: tuple, text: str) -> Any:
    if not path:
        return f"{value} {text}"
    head, *rest = path
    if isinstance(value, dict):
        return {**value, head: _append(value[head], tuple(rest), text)}
    items = list(value)
    items[head] = _append(items[head], tuple(rest), text)
    return items


class SusceptibleLLM(LLMClient):
    """A client that follows planted instructions according to the channel they arrive in (see the module docstring)."""

    def __init__(self, inner: LLMClient, planted: Sequence[str], rates: dict[str, float] | None = None) -> None:
        """Wrap `inner`; `planted` are the instruction texts to follow; `rates` give the follow probability per channel."""
        self.inner = inner
        self.planted = [p for p in planted if p.strip()]
        self.rates = {**DEFAULT_RATES, **(rates or {})}
        self.name = f"susceptible({getattr(inner, 'name', 'llm')})"
        self.model_id = getattr(inner, "model_id", None)
        self.is_offline = getattr(inner, "is_offline", False)
        self.where = getattr(inner, "where", "laptop")
        self.followed: list[dict[str, str]] = []  # one entry per followed instruction: the channel and the prompt hash
        self.calls = 0

    def _follows(self, prompt: str, text: str) -> str | None:
        channel = channel_of(prompt, text)
        rate = self.rates.get(channel, 0.0)
        if rate <= 0.0:
            return None
        if rate >= 1.0:
            return channel
        draw = int(hashlib.sha256(f"{text}|{prompt}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        return channel if draw < rate else None

    def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None) -> str:
        """The inner reply, with each followed instruction surfacing in it."""
        self.calls += 1
        reply = self.inner.generate(prompt, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)
        for text in self.planted:
            channel = self._follows(prompt, text)
            if channel is None:
                continue
            self.followed.append({"channel": channel, "prompt": hashlib.sha256(prompt.encode()).hexdigest()[:12]})
            try:
                value = json.loads(reply)
            except ValueError:
                reply = f"{reply}\n{text}"
                continue
            path = _longest_string_path(value)
            reply = json.dumps(_append(value, path, text), ensure_ascii=False) if path is not None else reply
        return reply

    def count_tokens(self, text: str) -> int:
        """The inner client's count."""
        return self.inner.count_tokens(text)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__dict__["inner"], name)
