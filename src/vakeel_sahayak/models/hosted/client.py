"""`HostedLLMClient`: an `LLMClient` for any configured provider (models/registry.py), behind the privacy gate, a key pool and the request ledger.

Every call goes:

1. **privacy**: the wire step for client text (`policy.wire_codec`), then `authorize(provider=<name>)`, which reads the provider's
   `data_class_allowed` (a `public_only` free tier refuses client data in every mode; see `sarvam.policy`). Nothing is sent on a refusal.
2. **paid lock**: a provider marked `paid: true` is refused unless `VS_ALLOW_PAID` names it (`models.paid_lock`).
3. **cache** (temperature 0, `VS_HOSTED_NO_CACHE=1` turns it off): a repeat is answered locally and counts nothing.
4. **size**: a request whose estimated prompt is larger than the model's tokens-per-minute limit is refused (`HostedRequestTooLarge`); when
   only the answer limit does not fit, `max_tokens` is lowered to what fits (at least 256).
5. **key and model choice**: keys are tried in order from a rotating start; for each the ledger answers slot / wait / day full. The first slot
   is used; when every key must wait the client sleeps the shortest wait (plus jitter, at most `max_wait_s` in total); when every key's day is
   full, the next failover model is tried (only with `VS_HOSTED_FAILOVER=1`), else `HostedQuotaExceeded` (the factory falls back to the local
   client; the gold labeler stops and resumes another day).
6. **send and learn**: 200 settles the row with the reported tokens; 429 per-minute lowers that key's rate and honours Retry-After, 429 per-day
   blocks that key until the next reset, and the call moves on to the next key; 500/503 back off exponentially with jitter (bounded); 401/403
   drop the key for this process; a 400 naming a feature (system instruction, JSON mode, schema, thinking) switches to a weaker mode, which the
   ledger remembers for the model.

Keys appear only in the auth header, never in a URL, a log line, the ledger or an error (fingerprints only).
"""

from __future__ import annotations

import dataclasses
import logging
import os
import random
import sqlite3
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx

from vakeel_sahayak.models.base import LLMClient, approx_tokens
from vakeel_sahayak.models.hosted import protocols as proto
from vakeel_sahayak.models.hosted.errors import (
    HostedAuthError,
    HostedError,
    HostedHttpError,
    HostedQuotaExceeded,
    HostedRateLimited,
    HostedRequestTooLarge,
    HostedUnavailable,
)
from vakeel_sahayak.models.hosted.keys import ApiKey, pool, scrub
from vakeel_sahayak.models.hosted.quota import DayFull, QuotaLedger, Slot, Wait, estimate_tokens, iso, note_quota_stop
from vakeel_sahayak.models.prompting import to_messages
from vakeel_sahayak.models.registry import ProviderSpec, get_provider

log = logging.getLogger("vakeel_sahayak.hosted")
_SAFE_BEFORE_SEND = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
MIN_ANSWER_TOKENS = 256
_BAD_KEYS: dict[str, set[str]] = {}  # provider -> key fingerprints that got 401/403 in this process
_ROTATE = {"i": 0}
_ROTATE_LOCK = threading.Lock()


def _cache_path() -> Any:
    from vakeel_sahayak.models.hosted.quota import default_path

    return default_path().parent / "cache.sqlite"


class HostedLLMClient(LLMClient):
    """Chat with a configured hosted provider. Construct with `transport`, `ledger`, `sleep`, `clock` in tests."""

    where = "api"

    def __init__(
        self, provider: str | ProviderSpec, model: str | None = None, *, data: Any = None, where: str = "api", role: str | None = None,
        scope: Any = None, transport: httpx.BaseTransport | None = None, ledger: QuotaLedger | None = None, cache: Any = None,
        sleep: Callable[[float], None] = time.sleep, jitter: Callable[[], float] | None = None, environ: dict[str, str] | None = None,
    ) -> None:  # fmt: skip
        """Configure the client; nothing is sent until the first call.

        Args:
            provider: a registry name or a `ProviderSpec`
            model: model id (default the provider's model for the role, else its `default_model`)
            data: pin the data class (`DataClass.PUBLIC` for the labeler and teacher, `CLIENT_TEXT` for agent roles); None reads the caller's scope
            where, role: location label and role name (purpose in the ledger)
            transport: httpx transport (tests: `httpx.MockTransport`)
            ledger, cache: request ledger and response cache (defaults: `<data>/hosted/quota.sqlite`, `cache.sqlite`)
            sleep, jitter: waiting (tests)
            environ: where keys are read from (default the process environment)
        """
        spec = provider if isinstance(provider, ProviderSpec) else get_provider(provider)
        if spec is None:
            raise HostedUnavailable(f"no provider {provider!r} in configs/models.yaml providers: (or the override file)")
        if spec.builtin:
            raise HostedUnavailable(f"{spec.name} has its own adapter (models.{spec.name}); it is not a generic provider")
        self.spec = spec
        role_key = {"eval_labeler": "labeler", "teacher": "teacher"}.get(role or "", "agents")
        self.model_id = model or spec.model_for(role_key)
        if not self.model_id:
            raise HostedUnavailable(f"provider {spec.name} has no model configured (default_model or roles)")
        self.name = spec.name
        self.data = data
        self.where = where
        self.role = role
        self._scope = scope
        self._transport = transport
        self._ledger = ledger
        self._cache = cache
        self._sleep = sleep
        jit = float((spec.retries or {}).get("jitter_s", 1.0))
        self._jitter = jitter or (lambda: random.uniform(0.0, jit))
        self._environ = environ
        self._lock = threading.Lock()
        self.last_reply: proto.Reply | None = None
        self.last_model: str | None = None
        self.last_mode: str | None = None
        self.models_used: dict[str, int] = {}
        self.modes_used: dict[str, str] = {}

    @property
    def family(self) -> str:  # type: ignore[override]
        """Model family of the configured model (registry `family`, else from the id)."""
        return self.spec.family_of(self.model_id)

    def __repr__(self) -> str:
        """Provider and model; never a key."""
        return f"HostedLLMClient(provider={self.name!r}, model={self.model_id!r})"

    @property
    def ledger(self) -> QuotaLedger:
        """The request ledger (opened on first use)."""
        if self._ledger is None:
            with self._lock:
                if self._ledger is None:
                    learn = self.spec.learn or {}
                    self._ledger = QuotaLedger(learn_factor=float(learn.get("factor", 0.5)), learn_hold_s=float(learn.get("hold_s", 3600.0)))
        return self._ledger

    @property
    def cache(self) -> Any:
        """The response cache (opened on first use; the OpenAI cache class, a separate file)."""
        if self._cache is None:
            with self._lock:
                if self._cache is None:
                    from vakeel_sahayak.models.openai.ledger import ResponseCache

                    self._cache = ResponseCache(_cache_path())
        return self._cache

    def keys(self) -> list[ApiKey]:
        """The usable keys (configured, minus the ones that failed authentication in this process)."""
        bad = _BAD_KEYS.get(self.name, set())
        return [k for k in pool(self.spec.key_env, self._environ) if k.fp not in bad]

    # ------------------------------------------------------------------ the LLMClient interface

    def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None) -> str:
        """One chat call from a single prompt."""
        return self.chat(to_messages(prompt), max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)

    def count_tokens(self, text: str) -> int:
        """Estimate (the API reports exact usage per call)."""
        return approx_tokens(text)

    def version(self) -> str:
        """The model version the provider last reported (the configured id until a call was made)."""
        return (self.last_reply.served_model if self.last_reply and self.last_reply.served_model else None) or self.model_id

    def _chat_scope(self) -> Any:
        from vakeel_sahayak.models.sarvam.policy import current_scope

        base = self._scope or current_scope()
        return dataclasses.replace(base, data=self.data) if self.data is not None and base.data is not self.data else base

    def chat(self, messages: list[dict[str, str]], max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None) -> str:
        """Chat call through the gate, the cache, the size check, the key pool and the ledger (module doc).

        Raises:
            HostedPolicyError, PrivacyBoundaryError: the gate refused (nothing sent).
            PaidProviderLocked: a paid provider that is locked.
            HostedRequestTooLarge, HostedQuotaExceeded, HostedRateLimited, HostedAuthError, HostedHttpError, HostedError: as named.
        """
        from vakeel_sahayak.models.sarvam.policy import authorize, wire_codec

        scope, codec = wire_codec(self._chat_scope())
        if codec is not None:
            messages = codec.encode(messages)
        authorize("chat", scope, payload={"messages": messages}, provider=self.name)
        purpose = (getattr(scope, "purpose", "") or self.role or "chat")[:80]
        text = self._call(messages, max_tokens, temperature, json_schema, purpose, getattr(scope, "case_id", None))
        return codec.decode_text(text) if codec is not None else text

    # ------------------------------------------------------------------ internals

    def _modes(self, model: str) -> proto.Modes:
        learned = self.ledger.modes(self.name, model)
        system = "system" if self.spec.quirk(model, "system_instruction", True) else "fold"
        structured = str(self.spec.quirk(model, "structured", "schema") or "schema")
        if structured not in proto.STRUCTURED_ORDER:
            structured = "schema"
        thinking = "on" if self.spec.quirk(model, "thinking", {}) else "off"
        m = proto.Modes(learned.get("system", system), learned.get("structured", structured), learned.get("thinking", thinking))
        if proto.STRUCTURED_ORDER.index(m.structured) < proto.STRUCTURED_ORDER.index(structured):
            m = dataclasses.replace(m, structured=structured)
        return m

    def _url(self, model: str) -> str:
        base = self.spec.base_url.rstrip("/")
        if self.spec.protocol == "gemini_native":
            return f"{base}/{self.spec.api_version}/models/{model}:generateContent"
        path = self.spec.chat_path or "/chat/completions"
        return base + (path if path.startswith("/") else "/" + path)

    def _headers(self, key: ApiKey) -> dict[str, str]:
        scheme = (self.spec.auth_scheme or "").strip()
        return {self.spec.auth_header or "Authorization": f"{scheme} {key.value}" if scheme else key.value, "Content-Type": "application/json"}

    def _body(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float, json_schema: dict | None, modes: proto.Modes) -> dict[str, Any]:
        thinking = dict(self.spec.quirk(model, "thinking", {}) or {})
        send_t = bool(self.spec.quirk(model, "send_temperature", True))
        if self.spec.protocol == "gemini_native":
            return proto.gemini_body(messages, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema, modes=modes, thinking=thinking, send_temperature=send_t)
        return proto.openai_body(messages, model=model, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema, modes=modes, thinking=thinking,
                                 max_tokens_field=self.spec.max_tokens_field, send_temperature=send_t)  # fmt: skip

    def _parse(self, data: dict[str, Any]) -> proto.Reply:
        return proto.parse_gemini(data) if self.spec.protocol == "gemini_native" else proto.parse_openai(data)

    def _fit(self, model: str, prompt_est: int, max_tokens: int) -> int:
        """The answer limit to send, or raise when the prompt alone exceeds the model's tokens per minute."""
        tpm = int(self.spec.limits_for(model).get("tpm", 0))
        cap = int(self.spec.quirk(model, "max_tokens_cap", self.spec.max_tokens_cap) or 4096)
        # a model that always thinks (Gemma, `thinking_headroom` in its config) spends part of the limit on thoughts: add room for them
        want = max(1, min(int(max_tokens), cap)) + int(self.spec.quirk(model, "thinking_headroom", 0) or 0)
        if not tpm:
            return want
        if prompt_est + MIN_ANSWER_TOKENS > tpm:
            raise HostedRequestTooLarge(
                f"{self.name}/{model}: the request is about {prompt_est} prompt tokens, above what the model's limit of {tpm} tokens per minute allows "
                f"(with {MIN_ANSWER_TOKENS} for the answer); refused before sending: use a model with a larger TPM or a shorter prompt"
            )
        return min(want, tpm - prompt_est)

    def _send(self, key: ApiKey, model: str, body: dict[str, Any]) -> httpx.Response:
        with httpx.Client(transport=self._transport, timeout=float(self.spec.timeout_s)) as client:
            return client.post(self._url(model), headers=self._headers(key), json=body)

    def _error(self, resp: httpx.Response, keys: list[ApiKey]) -> HostedHttpError:
        try:
            payload = resp.json()
        except ValueError:
            payload = None
        message, code, retry, per_day = proto.error_info(resp.status_code, resp.headers, payload)
        text = scrub(f"{self.name} API error {resp.status_code}" + (f" ({code})" if code else "") + (f": {message}" if message else ""), keys)
        cls = HostedAuthError if resp.status_code in (401, 403) else HostedRateLimited if resp.status_code in (429, 500, 502, 503, 504) else HostedHttpError
        return cls(text, resp.status_code, code, retry, per_day)

    def _call(self, messages: list[dict[str, str]], max_tokens: int, temperature: float, json_schema: dict | None, purpose: str, case_id: str | None) -> str:
        if not self.keys():
            raise HostedUnavailable(f"{self.spec.key_env or 'the key variable'} is not set (nor a pool {self.spec.key_env}S / {self.spec.key_env}_1..N), so {self.name} cannot be called")
        cache_key = None
        if temperature == 0 and os.environ.get("VS_HOSTED_NO_CACHE", "").strip() not in ("1", "true", "yes"):
            from vakeel_sahayak.models.openai.ledger import cache_key as make_key

            cache_key = make_key(f"{self.name}:{self.model_id}", messages, json_schema, temperature, {"max_tokens": max_tokens})
            hit = self.cache.get(cache_key)
            if hit is not None:
                self.ledger.record_cache_hit(self.name, self.model_id, purpose, case_id, self.spec.quota_day_tz)
                self.record_usage(hit[1], hit[2])
                return hit[0]
        prompt_est = estimate_tokens(messages, json_schema)
        last_quota: HostedQuotaExceeded | None = None
        for model in self.spec.failover_models(self.model_id):
            try:
                answer_limit = self._fit(model, prompt_est, max_tokens)
            except HostedRequestTooLarge:
                if model == self.model_id and len(self.spec.failover_models(self.model_id)) == 1:
                    raise
                continue
            try:
                reply = self._on_model(model, messages, answer_limit, temperature, json_schema, prompt_est + answer_limit, purpose, case_id)
            except HostedQuotaExceeded as exc:
                last_quota = exc
                log.info("%s/%s: daily quota spent on every key; trying the next failover model", self.name, model)
                continue
            if cache_key is not None and reply.finish in ("STOP", "stop", None):
                self.cache.put(cache_key, self.model_id, reply.text, reply.input_tokens, reply.output_tokens)
            return reply.text
        note_quota_stop()
        if last_quota is not None:
            raise last_quota
        raise HostedRequestTooLarge(f"{self.name}: no configured model can take a request of about {prompt_est} prompt tokens")

    def _reserve(self, model: str, est: int, purpose: str, case_id: str | None, mode: str, waited: list[float]) -> tuple[ApiKey, Slot]:
        """A key with a slot for `model`, waiting when every key must wait; HostedQuotaExceeded when every key's day is full."""
        limits = self.spec.limits_for(model)
        max_wait = float(self.spec.max_wait_s)
        while True:
            keys = self.keys()
            if not keys:
                raise HostedAuthError(f"{self.name}: every configured key was refused (401/403); check the keys in AI Studio", 401)
            with _ROTATE_LOCK:
                start = _ROTATE["i"] % len(keys)
                _ROTATE["i"] += 1
            order = keys[start:] + keys[:start]
            waits: list[float] = []
            full: list[DayFull] = []
            for key in order:
                try:
                    got = self.ledger.try_reserve(self.name, key.fp, model, limits, est, day_tz=self.spec.quota_day_tz, purpose=purpose, case_id=case_id, mode=mode)
                except sqlite3.Error as exc:
                    raise HostedError(f"the {self.name} request ledger is unavailable, so the call was refused (the limits cannot be checked); nothing was sent") from exc
                if isinstance(got, Slot):
                    return key, got
                if isinstance(got, Wait):
                    waits.append(got.seconds)
                else:
                    full.append(got)
            if not waits:
                reset = min(f.reset_ts for f in full) if full else time.time()
                used = sum(f.used for f in full)
                raise HostedQuotaExceeded(
                    f"{self.name}/{model}: the daily request cap is reached on all {len(full)} key(s) ({used} requests counted today, limit {limits.get('rpd')} per key); "
                    f"0 remain until {iso(reset)}. Refused, nothing was sent", self.name, model, 0, iso(reset), "server" if any(f.source == "server" for f in full) else "ledger",
                )  # fmt: skip
            pause = min(waits) + max(0.0, float(self._jitter()))
            if waited[0] + pause > max_wait:
                raise HostedRateLimited(f"{self.name}/{model}: per-minute limits on every key; the next free slot is {min(waits):.0f} s away, beyond max_wait_s={max_wait:.0f}; nothing was sent", 429)
            log.info("%s/%s: per-minute limit on every key; waiting %.1f s", self.name, model, pause)
            self._sleep(pause)
            waited[0] += pause

    def _on_model(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float, json_schema: dict | None, est: int,
                  purpose: str, case_id: str | None) -> proto.Reply:  # fmt: skip
        retry = self.spec.retries or {}
        max_retries = int(retry.get("max", 5))
        base_delay, max_delay = float(retry.get("base_delay_s", 2.0)), float(retry.get("max_delay_s", 60.0))
        modes = self._modes(model)
        waited = [0.0]
        errors = 0
        last_exc: Exception | None = None
        for _ in range(max_retries + 8):  # 429s rotate keys without counting as errors; adapt steps are few
            key, slot = self._reserve(model, est, purpose, case_id, modes.label, waited)
            body = self._body(model, messages, max_tokens, temperature, json_schema, modes)
            keys = self.keys()
            try:
                resp = self._send(key, model, body)
            except httpx.TransportError as exc:
                (self.ledger.not_sent if isinstance(exc, _SAFE_BEFORE_SEND) else self.ledger.mark_unknown)(slot)
                log.warning("%s/%s via %s: transport error %s", self.name, model, key.fp, type(exc).__name__)
                errors += 1
                last_exc = HostedUnavailable(f"{self.name} could not be reached ({type(exc).__name__})")
                if errors > max_retries:
                    raise last_exc from exc
                self._sleep(min(base_delay * 2 ** (errors - 1), max_delay) + max(0.0, float(self._jitter())))
                continue
            log.info("%s %s via %s -> %s", self.name, model, key.fp, resp.status_code)
            if resp.status_code < 400:
                try:
                    reply = self._parse(resp.json())
                except ValueError as exc:
                    self.ledger.settle(slot, 0, 0, 0, None, modes.label)
                    raise HostedError(f"{self.name} answered with a body that is not JSON") from exc
                except HostedError:
                    self.ledger.settle(slot, 0, 0, 0, None, modes.label)
                    raise
                self.ledger.settle(slot, reply.input_tokens, reply.output_tokens, reply.thinking_tokens, reply.served_model, modes.label)
                self.last_reply, self.last_model, self.last_mode = reply, model, modes.label
                self.models_used[model] = self.models_used.get(model, 0) + 1
                self.modes_used[model] = modes.label
                self.record_usage(reply.input_tokens, reply.output_tokens + reply.thinking_tokens)
                return reply
            self.ledger.fail(slot, resp.status_code)
            err = self._error(resp, keys)
            last_exc = err
            if resp.status_code == 429:
                self.ledger.note_429(self.name, key.fp, model, int(self.spec.limits_for(model).get("rpm", 1)), per_day=err.per_day, retry_after=err.retry_after)
                log.info("%s/%s: 429 on %s (%s); rotating", self.name, model, key.fp, "per day" if err.per_day else "per minute")
                continue
            if resp.status_code in (401, 403):
                _BAD_KEYS.setdefault(self.name, set()).add(key.fp)
                log.warning("%s: key %s was refused (%s); not used again in this process", self.name, key.fp, resp.status_code)
                continue
            if resp.status_code in (500, 502, 503, 504):
                errors += 1
                if errors > max_retries:
                    raise err
                delay = err.retry_after if err.retry_after is not None else min(base_delay * 2 ** (errors - 1), max_delay)
                self._sleep(min(float(delay), max_delay) + max(0.0, float(self._jitter())))
                continue
            if resp.status_code in (400, 422):
                nxt = proto.adapt(modes, str(err), json_schema is not None)
                if nxt is not None:
                    log.info("%s/%s: %s rejected; switching to %s", self.name, model, modes.label, nxt.label)
                    self.ledger.set_modes(self.name, model, system=nxt.system, structured=nxt.structured, thinking=nxt.thinking)
                    modes = nxt
                    continue
            raise err
        raise last_exc if last_exc else HostedError(f"{self.name}/{model}: the request kept failing")
