"""Small sync and async httpx transport for the OpenAI API: bearer auth, timeouts, retries with backoff, no key in logs.

Auth: header `Authorization: Bearer <key>` (developers.openai.com/api/docs, checked 2026-10-24). Retries: only 429 and 5xx
(and transport errors that happen before the request was sent) with exponential backoff; 4xx other than 429 are never
retried, and a 429 `insufficient_quota` (credit exhausted) is not retried either. A `Retry-After` header is honoured when
present. Error messages carry the API's `message` with the key scrubbed; never the request body. Tests inject `transport`
(httpx.MockTransport) and `sleep`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from vakeel_sahayak.models.openai.config import api_key, openai_config
from vakeel_sahayak.models.openai.errors import (
    OpenAIAuthError,
    OpenAIHttpError,
    OpenAIQuotaError,
    OpenAIRateLimited,
    OpenAIUnavailable,
)

log = logging.getLogger("vakeel_sahayak.openai")
_SAFE_BEFORE_SEND = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)  # the request never left: nothing can be billed


def _retry_status(status: int) -> bool:
    return status == 429 or status >= 500


class OpenAIHttp:
    """Sync (`request`) and async (`arequest`) transport sharing one retry policy. Holds the key privately; `repr` hides it."""

    def __init__(
        self,
        key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        base_delay: float | None = None,
        max_delay: float | None = None,
        transport: httpx.BaseTransport | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        asleep: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        """Configure the transport; nothing connects yet.

        Args:
            key: API key (default: the OPENAI_API_KEY environment variable)
            base_url: default configs/models.yaml `openai.base_url`
            timeout: seconds per request
            max_retries: retries after the first attempt
            base_delay: first backoff delay in seconds (doubles each retry)
            max_delay: backoff cap in seconds
            transport: httpx transport for sync calls (tests: MockTransport)
            async_transport: httpx transport for async calls
            sleep: sync sleep (tests)
            asleep: async sleep (tests)
        """
        cfg = openai_config()
        retry = cfg["retries"]
        self._key = key if key is not None else api_key()
        self.base_url = (base_url or cfg["base_url"]).rstrip("/")
        self.timeout = float(timeout if timeout is not None else cfg["timeout_s"])
        self.max_retries = int(max_retries if max_retries is not None else retry["max"])
        self.base_delay = float(base_delay if base_delay is not None else retry["base_delay_s"])
        self.max_delay = float(max_delay if max_delay is not None else retry["max_delay_s"])
        self._transport = transport
        self._async_transport = async_transport
        self._sleep = sleep
        self._asleep = asleep

    def __repr__(self) -> str:
        """Never shows the key."""
        return f"OpenAIHttp(base_url={self.base_url!r}, key={'set' if self._key else 'unset'})"

    @property
    def has_key(self) -> bool:
        """True when a key is configured."""
        return bool(self._key)

    def _headers(self) -> dict[str, str]:
        from vakeel_sahayak.models.paid_lock import assert_unlocked

        assert_unlocked("openai")  # paid provider: locked unless VS_ALLOW_PAID names it (models/paid_lock.py)
        if not self._key:
            raise OpenAIUnavailable("OPENAI_API_KEY is not set in the environment, so the OpenAI API cannot be called")
        return {"Authorization": f"Bearer {self._key}"}

    def _scrub(self, text: str) -> str:
        return text.replace(self._key, "***") if self._key else text

    def _delay(self, attempt: int, resp: httpx.Response | None) -> float:
        if resp is not None:
            try:
                return max(0.0, min(float(resp.headers["retry-after"]), self.max_delay))
            except (KeyError, ValueError):
                pass
        return min(self.base_delay * (2**attempt), self.max_delay)

    def _error(self, resp: httpx.Response) -> OpenAIHttpError:
        """Map an error response to an exception (the message carries the API's text, truncated, with any key scrubbed)."""
        code = param = None
        message = ""
        try:
            err = resp.json().get("error") or {}
            code, param, message = err.get("code"), err.get("param"), str(err.get("message") or "")[:300]
        except (ValueError, AttributeError):
            pass
        text = self._scrub(f"OpenAI API error {resp.status_code}" + (f" ({code})" if code else "") + (f": {message}" if message else ""))
        if resp.status_code in (401, 403):
            return OpenAIAuthError(text, resp.status_code, code, param)
        if resp.status_code == 429 and code == "insufficient_quota":
            return OpenAIQuotaError(text, resp.status_code, code, param)
        if _retry_status(resp.status_code):
            return OpenAIRateLimited(text, resp.status_code, code, param)
        return OpenAIHttpError(text, resp.status_code, code, param)

    def _retryable(self, resp: httpx.Response) -> bool:
        return _retry_status(resp.status_code) and not isinstance(self._error(resp), OpenAIQuotaError)

    def _url(self, path: str) -> str:
        return path if path.startswith("http") else self.base_url + (path if path.startswith("/") else "/" + path)

    def request(self, method: str, path: str, *, json: Any = None) -> httpx.Response:
        """One API call with retries; returns the successful response.

        Raises:
            OpenAIUnavailable: no key, or transport failures through every retry (`maybe_billed` says whether the request could have been processed).
            OpenAIAuthError, OpenAIQuotaError, OpenAIRateLimited, OpenAIHttpError: error responses.
        """
        headers = self._headers()
        url = self._url(path)
        with httpx.Client(transport=self._transport, timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                last = attempt == self.max_retries
                try:
                    resp = client.request(method, url, headers=headers, json=json)
                except httpx.TransportError as exc:
                    log.warning("openai %s %s transport error: %s", method, path, type(exc).__name__)
                    if last:
                        raise OpenAIUnavailable(f"the OpenAI API could not be reached ({type(exc).__name__})", maybe_billed=not isinstance(exc, _SAFE_BEFORE_SEND)) from exc
                    self._sleep(self._delay(attempt, None))
                    continue
                log.info("openai %s %s -> %s", method, path, resp.status_code)
                if resp.status_code < 400:
                    return resp
                if self._retryable(resp) and not last:
                    self._sleep(self._delay(attempt, resp))
                    continue
                raise self._error(resp)
        raise OpenAIUnavailable("unreachable")  # pragma: no cover

    async def arequest(self, method: str, path: str, *, json: Any = None) -> httpx.Response:
        """Async twin of `request` (same retry policy)."""
        headers = self._headers()
        url = self._url(path)
        async with httpx.AsyncClient(transport=self._async_transport, timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                last = attempt == self.max_retries
                try:
                    resp = await client.request(method, url, headers=headers, json=json)
                except httpx.TransportError as exc:
                    if last:
                        raise OpenAIUnavailable(f"the OpenAI API could not be reached ({type(exc).__name__})", maybe_billed=not isinstance(exc, _SAFE_BEFORE_SEND)) from exc
                    await self._asleep(self._delay(attempt, None))
                    continue
                if resp.status_code < 400:
                    return resp
                if self._retryable(resp) and not last:
                    await self._asleep(self._delay(attempt, resp))
                    continue
                raise self._error(resp)
        raise OpenAIUnavailable("unreachable")  # pragma: no cover
