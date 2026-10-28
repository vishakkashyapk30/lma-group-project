"""Generic hosted LLM providers configured in configs/models.yaml `providers:` (models/registry.py): the client, key pool, request ledger,
model planner and probe. Free tiers (the Gemini API's, for one) are PUBLIC data only; see `sarvam.policy.authorize`."""

from vakeel_sahayak.models.hosted.errors import (
    GeminiQuotaExceeded,
    HostedAuthError,
    HostedError,
    HostedHttpError,
    HostedPolicyError,
    HostedQuotaExceeded,
    HostedRateLimited,
    HostedRequestTooLarge,
    HostedUnavailable,
)

__all__ = [
    "GeminiQuotaExceeded", "HostedAuthError", "HostedError", "HostedHttpError", "HostedPolicyError", "HostedQuotaExceeded", "HostedRateLimited",
    "HostedRequestTooLarge", "HostedUnavailable",
]  # fmt: skip
