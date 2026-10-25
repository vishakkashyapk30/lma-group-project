"""OpenAI chat completions with optional JSON-schema structured output, behind the spend ledger and the response cache.

Endpoint: `POST /v1/chat/completions` (Chat Completions; OpenAI recommends the newer Responses API for new projects but keeps
Chat Completions for the listed models, and its message list, `response_format` and `usage` shapes match the Sarvam client and
the `LLMClient.chat` interface). Verified against developers.openai.com on 2026-10-24 (see configs/models.yaml `openai:`).

Every call goes: cache lookup (temperature 0 only) -> worst-case estimate -> `Ledger.reserve` (refuses with `BudgetExceeded`
BEFORE any HTTP request) -> request -> `Ledger.settle` with the real `usage`. Structured output asks for `json_schema`
(strict when the schema allows it: every object lists all its properties as required and has `additionalProperties: false`),
falls back to non-strict `json_schema`, then to `json_object`; parameters a model rejects (`temperature`, `reasoning_effort`)
are dropped and the call repeated (a rejected request is not billed). The caller's validation and repair loop does the rest.
"""

from __future__ import annotations

import copy
import os
import threading
from dataclasses import dataclass
from typing import Any

from vakeel_sahayak.models.openai.config import Price, openai_config, price_of
from vakeel_sahayak.models.openai.errors import OpenAIError, OpenAIHttpError, OpenAIUnavailable
from vakeel_sahayak.models.openai.http import OpenAIHttp
from vakeel_sahayak.models.openai.ledger import Ledger, Reservation, ResponseCache, cache_key, worst_case_micro


@dataclass(frozen=True)
class ChatResult:
    """One chat completion (`cost_micro` is 0 for a cache hit)."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int = 0
    finish_reason: str | None = None
    model: str = ""
    cost_micro: int = 0
    from_cache: bool = False


def strictify(schema: dict[str, Any]) -> dict[str, Any] | None:
    """A copy of `schema` fit for `strict: true`, or None when it cannot be (an object with optional properties).

    Strict mode needs `additionalProperties: false` and every property listed in `required` on each object; `default` and
    `title` annotations are dropped. Optional fields would change meaning if forced required, so such schemas stay non-strict.
    """
    out = copy.deepcopy(schema)
    ok = True

    def walk(node: Any) -> None:
        nonlocal ok
        if isinstance(node, dict):
            node.pop("default", None)
            node.pop("title", None)
            props = node.get("properties")
            if node.get("type") == "object" or isinstance(props, dict):
                if node.get("additionalProperties") not in (None, False):
                    ok = False
                node["additionalProperties"] = False
                if set(node.get("required") or []) != set(props or {}):
                    ok = False
            for k, v in node.items():
                if k != "properties":
                    walk(v)
            for v in (props or {}).values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(out)
    return out if ok else None


def _with_json_word(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """`json_object` mode needs the word JSON in the messages; add one system line when missing."""
    if any("json" in str(m.get("content", "")).lower() for m in messages):
        return messages
    return [{"role": "system", "content": "Reply with a single JSON object and nothing else."}, *messages]


class OpenAIApi:
    """Sync chat completion with ledger and cache. Construct with injected pieces in tests."""

    def __init__(
        self, http: OpenAIHttp | None = None, config: dict[str, Any] | None = None, ledger: Ledger | None = None, cache: ResponseCache | None = None
    ) -> None:
        """Wrap a transport (default: key from the environment), a ledger and a cache (defaults: the configured files, opened on first use)."""
        self.cfg = config or openai_config()
        self.http = http or OpenAIHttp()
        self._ledger = ledger
        self._cache = cache
        self._init_lock = threading.Lock()  # the lazy ledger and cache are created once when threads call at the same time (the ledger itself is transactional)
        self._dropped: set[str] = set()  # parameters this account/model rejected before

    @property
    def ledger(self) -> Ledger:
        """The spend ledger (opened on first use)."""
        if self._ledger is None:
            with self._init_lock:
                if self._ledger is None:
                    self._ledger = Ledger()
        return self._ledger

    @property
    def cache(self) -> ResponseCache:
        """The response cache (opened on first use)."""
        if self._cache is None:
            with self._init_lock:
                if self._cache is None:
                    self._cache = ResponseCache()
        return self._cache

    def _ep(self) -> str:
        return str(self.cfg["endpoints"]["chat"])

    # ------------------------------------------------------------------ request building

    def max_completion_tokens(self, max_tokens: int) -> int:
        """The completion limit sent: the caller's `max_tokens` plus the reasoning headroom, the caller's value capped by `chat.max_tokens_cap`."""
        c = self.cfg["chat"]
        return max(1, min(int(max_tokens), int(c["max_tokens_cap"])) + int(c.get("reasoning_headroom_tokens") or 0))

    def chat_body(
        self, messages: list[dict[str, str]], *, model: str | None = None, max_tokens: int = 1024, temperature: float = 0.0,
        json_schema: dict | None = None, format_mode: str = "auto", reasoning_effort: Any = "config",
    ) -> dict[str, Any]:  # fmt: skip
        """The request body of a chat call.

        `format_mode`: 'auto' (strict json_schema when possible, else non-strict), 'schema' (non-strict), 'json_object'.
        """
        c = self.cfg["chat"]
        body: dict[str, Any] = {"model": model or c["model"], "messages": messages, "max_completion_tokens": self.max_completion_tokens(max_tokens)}
        if c.get("send_temperature", True) and "temperature" not in self._dropped:
            body["temperature"] = temperature
        effort = c.get("reasoning_effort") if reasoning_effort == "config" else reasoning_effort
        if effort and "reasoning_effort" not in self._dropped:
            body["reasoning_effort"] = effort
        if json_schema is not None:
            strict = strictify(json_schema) if format_mode == "auto" and str(c.get("strict_json", "auto")).lower() != "false" else None
            if format_mode == "json_object":
                body["messages"] = _with_json_word(messages)
                body["response_format"] = {"type": "json_object"}
            else:
                body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "output", "strict": strict is not None, "schema": strict if strict is not None else json_schema},
                }
        return body

    @staticmethod
    def parse_chat(data: dict[str, Any]) -> ChatResult:
        """Read a chat response (content, finish reason and usage incl. cached prompt tokens)."""
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        usage = data.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        return ChatResult(
            str(msg.get("content") or ""), int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)),
            int(details.get("cached_tokens", 0) or 0), choice.get("finish_reason"), str(data.get("model") or ""),
        )  # fmt: skip

    def _adapt(self, exc: OpenAIHttpError, body: dict[str, Any], mode: str, json_schema: dict | None) -> str | None:
        """After a 400/422: the next attempt's format mode (a rejected parameter is dropped), or None when the error cannot be worked around."""
        if exc.status not in (400, 422):
            return None
        text = f"{exc.param or ''} {exc.code or ''} {exc}".lower()
        for param in ("temperature", "reasoning_effort"):
            if param in body and param in text:
                self._dropped.add(param)
                return mode
        if json_schema is not None and any(w in text for w in ("response_format", "json_schema", "schema", "json")):
            return {"auto": "schema", "schema": "json_object"}.get(mode)
        return None

    # ------------------------------------------------------------------ the call

    def _begin(self, messages: list[dict[str, str]], model: str, max_tokens: int, temperature: float, json_schema: dict | None, purpose: str, case_id: str | None) -> tuple[ChatResult | None, Price, Reservation | None, str | None]:
        """Cache lookup, then price and reserve. Returns (cached result, price, reservation, cache key)."""
        price = price_of(model, self.cfg)
        if price is None:
            raise OpenAIUnavailable(f"no price for model {model!r} in configs/models.yaml openai.prices; refusing to call a model whose cost cannot be capped")
        key = None
        c = self.cfg["chat"]
        if temperature == 0 and os.environ.get("VS_OPENAI_NO_CACHE", "").strip() not in ("1", "true", "yes"):  # measurement runs: every call is real and billed
            key = cache_key(model, messages, json_schema, temperature, {"effort": c.get("reasoning_effort")})
            hit = self.cache.get(key)
            if hit is not None:
                self.ledger.record_cache_hit(model, purpose, case_id)
                return ChatResult(hit[0], hit[1], hit[2], 0, "stop", model, 0, True), price, None, key
        worst = worst_case_micro(price, messages, self.max_completion_tokens(max_tokens), json_schema)
        return None, price, self.ledger.reserve(model, worst, purpose, case_id), key

    def _finish(self, data: dict[str, Any], model: str, price: Price, res: Reservation, key: str | None) -> ChatResult:
        out = self.parse_chat(data)
        cost = self.ledger.settle(res, price, out.prompt_tokens, out.cached_tokens, out.completion_tokens, out.model or None)
        msg = ((data.get("choices") or [{}])[0].get("message")) or {}
        if msg.get("refusal"):
            raise OpenAIError("OpenAI refused to answer this request")
        if not out.text.strip():
            if out.finish_reason == "length":
                raise OpenAIError("OpenAI chat stopped at the token limit before any answer (reasoning used the budget); raise max_tokens or lower reasoning_effort")
            raise OpenAIError("OpenAI chat returned an empty answer")
        if key is not None and out.finish_reason == "stop":
            self.cache.put(key, model, out.text, out.prompt_tokens, out.completion_tokens)
        return ChatResult(out.text, out.prompt_tokens, out.completion_tokens, out.cached_tokens, out.finish_reason, out.model, cost, False)

    def _abort(self, res: Reservation, exc: Exception) -> None:
        if isinstance(exc, OpenAIHttpError) or (isinstance(exc, OpenAIUnavailable) and not exc.maybe_billed):
            self.ledger.release(res)
        else:
            self.ledger.mark_unknown(res)

    def chat(
        self, messages: list[dict[str, str]], *, model: str | None = None, max_tokens: int = 1024, temperature: float = 0.0,
        json_schema: dict | None = None, purpose: str = "", case_id: str | None = None, reasoning_effort: Any = "config",
    ) -> ChatResult:  # fmt: skip
        """Chat completion.

        Raises:
            BudgetExceeded: the call could exceed the cap (nothing was sent).
            OpenAIUnavailable, OpenAIAuthError, OpenAIQuotaError, OpenAIRateLimited, OpenAIHttpError, OpenAIError: as named.
        """
        model = model or self.cfg["chat"]["model"]
        cached, price, res, key = self._begin(messages, model, max_tokens, temperature, json_schema, purpose, case_id)
        if cached is not None:
            return cached
        assert res is not None
        mode = "auto"
        try:
            for _ in range(5):
                body = self.chat_body(messages, model=model, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema, format_mode=mode, reasoning_effort=reasoning_effort)
                try:
                    resp = self.http.request("POST", self._ep(), json=body)
                    break
                except OpenAIHttpError as exc:
                    nxt = self._adapt(exc, body, mode, json_schema)
                    if nxt is None:
                        raise
                    mode = nxt
            else:  # pragma: no cover
                raise OpenAIError("OpenAI request kept being rejected")
        except Exception as exc:
            self._abort(res, exc)
            raise
        return self._finish(resp.json(), model, price, res, key)


class AsyncOpenAIApi:
    """Async chat completion (same ledger, cache and fallbacks; for bulk labelling)."""

    def __init__(self, http: OpenAIHttp | None = None, config: dict[str, Any] | None = None, ledger: Ledger | None = None, cache: ResponseCache | None = None) -> None:
        """Share the sync API's building blocks."""
        self._sync = OpenAIApi(http, config, ledger, cache)
        self.http = self._sync.http

    async def chat(
        self, messages: list[dict[str, str]], *, model: str | None = None, max_tokens: int = 1024, temperature: float = 0.0,
        json_schema: dict | None = None, purpose: str = "", case_id: str | None = None, reasoning_effort: Any = "config",
    ) -> ChatResult:  # fmt: skip
        """Async `OpenAIApi.chat`."""
        s = self._sync
        model = model or s.cfg["chat"]["model"]
        cached, price, res, key = s._begin(messages, model, max_tokens, temperature, json_schema, purpose, case_id)
        if cached is not None:
            return cached
        assert res is not None
        mode = "auto"
        try:
            for _ in range(5):
                body = s.chat_body(messages, model=model, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema, format_mode=mode, reasoning_effort=reasoning_effort)
                try:
                    resp = await s.http.arequest("POST", s._ep(), json=body)
                    break
                except OpenAIHttpError as exc:
                    nxt = s._adapt(exc, body, mode, json_schema)
                    if nxt is None:
                        raise
                    mode = nxt
            else:  # pragma: no cover
                raise OpenAIError("OpenAI request kept being rejected")
        except Exception as exc:
            s._abort(res, exc)
            raise
        return s._finish(resp.json(), model, price, res, key)
