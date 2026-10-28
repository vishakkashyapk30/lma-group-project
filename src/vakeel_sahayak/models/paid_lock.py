"""The paid-provider lock: OpenAI and Sarvam cost money, and by the owner's decision of 2026-10-28 they are LOCKED.

No request may reach a paid provider (chat, translate, speech-to-text, text-to-speech, vision, language id; agents, labeler, teacher,
evaluation driver, baselines, sweep scripts) unless the operator names it in the unlock variable:

    VS_ALLOW_PAID=openai          # unlock OpenAI only
    VS_ALLOW_PAID=openai,sarvam   # unlock both

Default (unset or empty) = every paid provider locked. Do not unlock without the owner's go-ahead.

The lock is checked before anything else, in four places, so a locked call never touches the network and never writes a ledger row:
the shared privacy gate (`sarvam.policy.authorize`), the spend-ledger entry points (`OpenAIApi._begin`, Sarvam `Meter.begin_*`), and the
HTTP transports (`OpenAIHttp`, `SarvamHttp`). The factory treats a locked provider like one that is off, so the agent roles answer from
their local client; the hosted labeler and teacher, the driver and the sweep scripts refuse at once with `lock_message`.

The refusal is `OpenAILocked` / `SarvamLocked`, each a subclass of the provider's policy error (so every existing fallback catches it) and
of `PaidProviderLocked`.
"""

from __future__ import annotations

import os
import sys

from vakeel_sahayak.models.base import ModelUnavailable

UNLOCK_ENV = "VS_ALLOW_PAID"
PAID_PROVIDERS = ("openai", "sarvam")
DECISION = "paid providers are locked by the owner's decision of 2026-10-28; do not unlock without the owner"


class PaidProviderLocked(ModelUnavailable):
    """A paid provider was asked for while it is locked. Nothing was sent and nothing was recorded."""


def _paid_set() -> set[str]:
    """Paid providers: the built-in two plus any registry entry marked `paid: true` (configs/models.yaml `providers:`)."""
    names = set(PAID_PROVIDERS)
    try:
        from vakeel_sahayak.models.registry import paid_provider_names

        names |= set(paid_provider_names())
    except Exception:  # noqa: BLE001 - the registry is optional here; the two built-in paid providers stay locked regardless
        pass
    return names


_NEVER_PAID = ("", "offline", "local", "vllm", "mistral")  # local runtimes (mistral: the teacher's own API option, outside this lock's scope)


def is_paid(provider: str) -> bool:
    """True when `provider` costs money (and therefore sits behind the lock)."""
    p = (provider or "").strip().lower()
    if p in PAID_PROVIDERS:
        return True
    if p in _NEVER_PAID:
        return False
    return p in _paid_set()


def unlocked() -> set[str]:
    """Provider names listed in `VS_ALLOW_PAID` (lower case)."""
    raw = os.environ.get(UNLOCK_ENV) or ""
    return {p.strip().lower() for p in raw.replace(";", ",").split(",") if p.strip()}


def paid_unlocked(provider: str) -> bool:
    """True when `provider` is free, or paid and named in `VS_ALLOW_PAID`."""
    p = (provider or "").strip().lower()
    return not is_paid(p) or p in unlocked()


def lock_message(provider: str) -> str:
    """The refusal text: names the provider, the decision and the unlock variable."""
    p = (provider or "").strip().lower()
    return (
        f"{p} is a paid provider and is LOCKED ({DECISION}). Nothing was sent and nothing was recorded. "
        f"To unlock, the operator sets {UNLOCK_ENV}={p} (comma-separate several), only with the owner's go-ahead"
    )


def _error_class(provider: str) -> type[PaidProviderLocked]:
    if provider == "openai":
        from vakeel_sahayak.models.openai.errors import OpenAILocked

        return OpenAILocked
    if provider == "sarvam":
        from vakeel_sahayak.models.sarvam.errors import SarvamLocked

        return SarvamLocked
    return PaidProviderLocked


def assert_unlocked(provider: str) -> None:
    """Raise the provider's lock error when `provider` is paid and not unlocked.

    Raises:
        OpenAILocked, SarvamLocked, PaidProviderLocked: the provider is locked.
    """
    p = (provider or "").strip().lower()
    if not paid_unlocked(p):
        raise _error_class(p)(lock_message(p))


def main(argv: list[str] | None = None) -> int:
    """`python -m vakeel_sahayak.models.paid_lock check <provider>...`: exit 3 with the lock message when any is locked (for shell scripts)."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != "check":
        print(f"usage: python -m vakeel_sahayak.models.paid_lock check <provider>...   (unlock with {UNLOCK_ENV})", file=sys.stderr)
        return 2
    locked = [p for p in args[1:] if not paid_unlocked(p)]
    for p in locked:
        print(lock_message(p), file=sys.stderr)
    return 3 if locked else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
