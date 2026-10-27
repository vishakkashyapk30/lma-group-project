"""OpenAI implementation of `LLMClient`. Each call is authorised by the shared privacy gate (`sarvam.policy.authorize(provider="openai")`) first.

`data` pins the data class: CLIENT_TEXT for agent roles (every outbound message is boundary-checked), PUBLIC for the
independent non-Qwen labeler/teacher option (public court orders only). With `data=None` the class comes from the caller's
declared scope (`public_scope()` / `sarvam_scope(...)`), and a call with no declared scope is CLIENT_RAW, which needs counsel's
consent for a case and is otherwise blocked. Token usage (incl. cached tokens and cost) is recorded per call.

A CLIENT_TEXT call goes through the wire step first (`policy.wire_codec`, `privacy.quasi`): quasi-identifiers become the case's aliases
and every date moves by the case's shift; the reply is turned back before it is returned, so the caller only ever sees real values.
"""

from __future__ import annotations

import dataclasses

from vakeel_sahayak.models.base import LLMClient, approx_tokens
from vakeel_sahayak.models.openai.api import ChatResult, OpenAIApi
from vakeel_sahayak.models.openai.config import openai_config
from vakeel_sahayak.models.prompting import to_messages
from vakeel_sahayak.models.sarvam.policy import DataClass, SarvamScope, authorize, current_scope, wire_codec

FAMILY = "openai"


class OpenAILLMClient(LLMClient):
    """OpenAI chat completions (structured output through `response_format`)."""

    name = "openai"
    family = FAMILY

    def __init__(
        self, model: str | None = None, *, api: OpenAIApi | None = None, data: DataClass | None = None, where: str = "api",
        role: str | None = None, scope: SarvamScope | None = None,
    ) -> None:  # fmt: skip
        """Configure the client; nothing is sent until the first call."""
        self._api = api
        self._scope = scope
        self.model_id = model or openai_config()["chat"]["model"]
        self.data = data
        self.where = where
        self.role = role
        self.last_result: ChatResult | None = None
        self.cached_tokens = 0  # prompt tokens served from OpenAI's prompt cache (cheaper)
        self.cost_micro = 0  # micro-USD billed through this client
        self.cache_hits = 0

    @property
    def api(self) -> OpenAIApi:
        """The API handle (built on first use)."""
        if self._api is None:
            self._api = OpenAIApi()
        return self._api

    def _chat_scope(self) -> SarvamScope:
        base = self._scope or current_scope()
        return dataclasses.replace(base, data=self.data) if self.data is not None and base.data is not self.data else base

    def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None) -> str:
        """One chat call from a single prompt."""
        return self.chat(to_messages(prompt), max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)

    def chat(
        self, messages: list[dict[str, str]], max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None
    ) -> str:
        """Chat call. The whole message list is policy- and boundary-checked first, then budget-checked by the ledger; a schema asks for structured JSON.

        Raises:
            OpenAIPolicyError, PrivacyBoundaryError: the gate refused (nothing sent).
            BudgetExceeded: the spending cap would be exceeded (nothing sent).
            OpenAIError: the API failed.
        """
        scope, codec = wire_codec(self._chat_scope())
        if codec is not None:
            messages = codec.encode(messages)
        authorize("chat", scope, payload={"messages": messages}, provider="openai")
        purpose = scope.purpose or self.role or "chat"
        res = self.api.chat(messages, model=self.model_id, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema, purpose=purpose, case_id=scope.case_id)
        self.last_result = res
        self.record_usage(res.prompt_tokens, res.completion_tokens)
        self.cached_tokens += res.cached_tokens
        self.cost_micro += res.cost_micro
        self.cache_hits += int(res.from_cache)
        return codec.decode_text(res.text) if codec is not None else res.text

    def count_tokens(self, text: str) -> int:
        """Estimate (the API reports exact usage per call)."""
        return approx_tokens(text)

    def spend_usd(self) -> float:
        """USD billed through this client so far (cache hits are free)."""
        return self.cost_micro / 1e6

    def version(self) -> str:
        """The model snapshot OpenAI last reported serving for this model (the configured alias until a call was made)."""
        served = self.last_result.model if self.last_result and self.last_result.model else None
        return served or self.model_id or ""

