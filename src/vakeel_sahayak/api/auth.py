"""Optional bearer-token check for counsel's actions (opt-in; default behaviour is unchanged).

Without `VS_API_TOKEN` the API trusts every caller as counsel, as before. With `VS_API_TOKEN` set (non-empty), every request that changes anything under `/api` (POST, PUT, PATCH, DELETE:
create case, upload, draft, edit a field, approve a gate, export, chat, desk) must send `Authorization: Bearer <token>`: no header gives 401, a wrong token 403. `/healthz`, the
docs routes, CORS preflights (OPTIONS) and, unless `VS_API_TOKEN_READS=1`, every GET stay open. The comparison is constant time (`hmac.compare_digest`); the token is read from the
environment per request, never stored, logged or echoed. This is one shared secret for a single-counsel desk, not user accounts: gate approvals still record the actor `COUNSEL`.
"""

from __future__ import annotations

import hmac
import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

TOKEN_ENV = "VS_API_TOKEN"
READS_ENV = "VS_API_TOKEN_READS"
_WRITES = {"POST", "PUT", "PATCH", "DELETE"}

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


def configured_token() -> str | None:
    """The token from the environment (None or empty: the check is off)."""
    return (os.environ.get(TOKEN_ENV) or "").strip() or None


def decide(method: str, path: str, header: str | None, token: str | None = None, reads: bool | None = None) -> tuple[int, str] | None:
    """`None` when the request may go on, else `(status, message)`: 401 without a bearer header, 403 for a wrong token."""
    token = configured_token() if token is None else token
    if not token:
        return None
    if reads is None:
        reads = os.environ.get(READS_ENV) == "1"
    method = method.upper()
    if method == "OPTIONS" or not path.startswith("/api"):
        return None  # preflights, /healthz and the docs routes are never gated
    if method not in _WRITES and not reads:
        return None
    scheme, _, supplied = (header or "").partition(" ")
    if scheme.lower() != "bearer" or not supplied.strip():
        return 401, "authorization required: send 'Authorization: Bearer <token>'"
    if not hmac.compare_digest(supplied.strip().encode("utf-8"), token.encode("utf-8")):
        return 403, "invalid token"
    return None


class BearerTokenMiddleware:
    """Pure ASGI middleware applying `decide` (no body buffering, so uploads and the SSE stream are untouched)."""

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        verdict = decide(scope["method"], scope["path"], headers.get("authorization"))
        if verdict is None:
            await self.app(scope, receive, send)
            return
        status, message = verdict
        body = json.dumps({"detail": message}).encode()
        out = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
        if status == 401:
            out.append((b"www-authenticate", b"Bearer"))
        await send({"type": "http.response.start", "status": status, "headers": out})
        await send({"type": "http.response.body", "body": body})
