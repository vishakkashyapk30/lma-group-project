"""Small sync and async httpx transport for the Sarvam API: auth header, timeouts, retries with backoff, no key in logs.

Auth: header `api-subscription-key` (docs.sarvam.ai/api/getting-started/quickstart). Retries follow the docs'
errors-troubleshooting page: only 429, 500 and 503 (and transport errors) are retried, with exponential backoff from 1 s
doubling to 60 s, at most five retries; 400, 403 and 422 are not retried. A 429 with `insufficient_quota_error` (credits
exhausted) is not retried either. No Retry-After header is documented, so a `Retry-After` is honoured only when present.
Tests inject `transport` (httpx.MockTransport) and `sleep`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from vakeel_sahayak.models.sarvam.config import api_key, sarvam_config
from vakeel_sahayak.models.sarvam.errors import (
    SarvamAuthError,
    SarvamHttpError,
    SarvamQuotaError,
    SarvamRateLimited,
    SarvamUnavailable,
)

log = logging.getLogger("vakeel_sahayak.sarvam")
RETRY_STATUS = frozenset({429, 500, 503})


class SarvamHttp:
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
            key: API key (default: the SARVAM_API_KEY environment variable)
            base_url: default configs/models.yaml `sarvam.base_url`
            timeout: seconds per request
            max_retries: retries after the first attempt
            base_delay: first backoff delay in seconds (doubles each retry)
            max_delay: backoff cap in seconds
            transport: httpx transport for sync calls (tests: MockTransport)
            async_transport: httpx transport for async calls
            sleep: sync sleep (tests)
            asleep: async sleep (tests)
        """
        cfg = sarvam_config()
        retry = cfg["retries"]
        self._key = key if key is not None else api_key()
        self.base_url = (base_url or cfg["base_url"]).rstrip("/")
        self.header = str(cfg["auth_header"])
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
        return f"SarvamHttp(base_url={self.base_url!r}, key={'set' if self._key else 'unset'})"

    @property
    def has_key(self) -> bool:
        """True when a key is configured."""
        return bool(self._key)

    # ------------------------------------------------------------------ shared helpers

    def _headers(self) -> dict[str, str]:
        from vakeel_sahayak.models.paid_lock import assert_unlocked

        assert_unlocked("sarvam")  # paid provider: locked unless VS_ALLOW_PAID names it (models/paid_lock.py)
        if not self._key:
            raise SarvamUnavailable("SARVAM_API_KEY is not set in the environment, so the Sarvam API cannot be called")
        return {self.header: self._key}

    def _scrub(self, text: str) -> str:
        return text.replace(self._key, "***") if self._key else text

    def _delay(self, attempt: int, resp: httpx.Response | None) -> float:
        if resp is not None:
            try:
                return min(float(resp.headers["retry-after"]), self.max_delay)
            except (KeyError, ValueError):
                pass
        return min(self.base_delay * (2**attempt), self.max_delay)

    def _error(self, resp: httpx.Response) -> SarvamHttpError:
        """Map an error response to an exception (the message carries the API's text with any key scrubbed)."""
        code, message = None, ""
        try:
            err = resp.json().get("error") or {}
            code, message = err.get("code"), str(err.get("message") or "")
        except (ValueError, AttributeError):
            pass
        text = self._scrub(f"Sarvam API error {resp.status_code}" + (f" ({code})" if code else "") + (f": {message}" if message else ""))
        if resp.status_code == 403:
            return SarvamAuthError(text, resp.status_code, code)
        if resp.status_code == 429 and code == "insufficient_quota_error":
            return SarvamQuotaError(text, resp.status_code, code)
        if resp.status_code in (429, 503):
            return SarvamRateLimited(text, resp.status_code, code)
        return SarvamHttpError(text, resp.status_code, code)

    def _retryable(self, resp: httpx.Response) -> bool:
        if resp.status_code not in RETRY_STATUS:
            return False
        return not isinstance(self._error(resp), SarvamQuotaError)

    def _kwargs(self, path: str, json: Any, data: Any, files: Any, params: Any) -> dict[str, Any]:
        url = path if path.startswith("http") else self.base_url + (path if path.startswith("/") else "/" + path)
        return {"url": url, "json": json, "data": data, "files": files, "params": params}

    # ------------------------------------------------------------------ sync

    def request(
        self, method: str, path: str, *, json: Any = None, data: Any = None, files: Any = None, params: Any = None
    ) -> httpx.Response:
        """One API call with retries; returns the successful response.

        Raises:
            SarvamUnavailable: no key, or transport failures through every retry.
            SarvamAuthError, SarvamQuotaError, SarvamRateLimited, SarvamHttpError: error responses.
        """
        headers = self._headers()
        kw = self._kwargs(path, json, data, files, params)
        with httpx.Client(transport=self._transport, timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                last = attempt == self.max_retries
                try:
                    resp = client.request(method, headers=headers, **kw)
                except httpx.TransportError as exc:
                    log.warning("sarvam %s %s transport error: %s", method, path, type(exc).__name__)
                    if last:
                        raise SarvamUnavailable(f"the Sarvam API could not be reached ({type(exc).__name__})") from exc
                    self._sleep(self._delay(attempt, None))
                    continue
                log.info("sarvam %s %s -> %s", method, path, resp.status_code)
                if resp.status_code < 400:
                    return resp
                if self._retryable(resp) and not last:
                    self._sleep(self._delay(attempt, resp))
                    continue
                raise self._error(resp)
        raise SarvamUnavailable("unreachable")  # pragma: no cover

    def get_external(self, url: str) -> httpx.Response:
        """GET a pre-signed download URL WITHOUT the API key (it points at storage, not at Sarvam)."""
        with httpx.Client(transport=self._transport, timeout=self.timeout, follow_redirects=True) as client:
            try:
                resp = client.get(url)
            except httpx.TransportError as exc:
                raise SarvamUnavailable(f"the Sarvam result download failed ({type(exc).__name__})") from exc
        if resp.status_code >= 400:
            raise SarvamHttpError(f"Sarvam result download failed with status {resp.status_code}", resp.status_code)
        return resp

    # ------------------------------------------------------------------ async

    async def arequest(
        self, method: str, path: str, *, json: Any = None, data: Any = None, files: Any = None, params: Any = None
    ) -> httpx.Response:
        """Async twin of `request` (same retry policy)."""
        headers = self._headers()
        kw = self._kwargs(path, json, data, files, params)
        async with httpx.AsyncClient(transport=self._async_transport, timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                last = attempt == self.max_retries
                try:
                    resp = await client.request(method, headers=headers, **kw)
                except httpx.TransportError as exc:
                    if last:
                        raise SarvamUnavailable(f"the Sarvam API could not be reached ({type(exc).__name__})") from exc
                    await self._asleep(self._delay(attempt, None))
                    continue
                if resp.status_code < 400:
                    return resp
                if self._retryable(resp) and not last:
                    await self._asleep(self._delay(attempt, resp))
                    continue
                raise self._error(resp)
        raise SarvamUnavailable("unreachable")  # pragma: no cover
