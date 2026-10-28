"""API keys of a hosted provider, from the environment only: one key or a POOL of keys (one per project).

For a provider whose `key_env` is `GEMINI_API_KEY` the pool is, in order and without duplicates:
`GEMINI_API_KEYS` (comma separated), then `GEMINI_API_KEY_1` .. `GEMINI_API_KEY_N` (consecutive from 1), then `GEMINI_API_KEY`.

Rate limits are per PROJECT, not per key: two keys of one Google Cloud project share one quota, so list ONE key per project (each teammate's
own free-tier project). The ledger counts per key; it cannot see that two keys share a project.

A key is never printed, logged, stored or put in a URL. Logs, the ledger and reports name a key by its fingerprint: `k-` plus the first 8 hex
digits of its SHA-256, which is stable and reveals nothing of the key.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass


def fingerprint(key: str) -> str:
    """A short stable name for a key (not part of the key)."""
    return "k-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


@dataclass(frozen=True)
class ApiKey:
    """A key and its fingerprint. `repr` shows the fingerprint only."""

    fp: str
    _value: str

    def __repr__(self) -> str:
        """Never the key."""
        return f"ApiKey({self.fp})"

    __str__ = __repr__

    @property
    def value(self) -> str:
        """The key itself, for the auth header only."""
        return self._value


def pool(key_env: str, environ: dict[str, str] | None = None) -> list[ApiKey]:
    """The keys of a provider (see the module doc), deduplicated, in a stable order."""
    env = os.environ if environ is None else environ
    if not key_env:
        return []
    raw: list[str] = []
    raw += [k for k in (env.get(key_env + "S") or "").split(",")]
    i = 1
    while env.get(f"{key_env}_{i}") is not None:
        raw.append(env.get(f"{key_env}_{i}") or "")
        i += 1
    raw.append(env.get(key_env) or "")
    out: list[ApiKey] = []
    seen: set[str] = set()
    for k in raw:
        k = k.strip()
        if k and k not in seen:
            seen.add(k)
            out.append(ApiKey(fingerprint(k), k))
    return out


def any_key(key_env: str) -> bool:
    """True when at least one key of the pool is set (reveals nothing)."""
    return bool(pool(key_env))


def scrub(text: str, keys: list[ApiKey]) -> str:
    """`text` with every key replaced by its fingerprint."""
    for k in keys:
        if k.value:
            text = text.replace(k.value, f"<{k.fp}>")
    return text
