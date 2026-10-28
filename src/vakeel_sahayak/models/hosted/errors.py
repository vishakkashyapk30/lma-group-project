"""Errors of the generic hosted-provider client. All are `ModelUnavailable`, so the factory's fallback and the labeler treat them as 'model cannot run'.

No message ever carries an API key (only its fingerprint) or any prompt text. The `Gemini*` names are aliases for the Gemini free tier.
"""

from __future__ import annotations

from vakeel_sahayak.models.base import ModelUnavailable


class HostedError(ModelUnavailable):
    """Base class of every hosted-provider failure."""


class HostedUnavailable(HostedError):
    """No key in the environment, an unknown provider or model, or the service could not be reached after the retries."""


class HostedPolicyError(HostedError):
    """The privacy gate forbids this call (data class above what the provider may receive, mode too low, no consent). Nothing was sent."""


class HostedRequestTooLarge(HostedError):
    """The request is larger than the model's tokens-per-minute limit, so the provider would reject it. Refused before sending."""


class HostedQuotaExceeded(HostedError):
    """Every key's daily request cap of every allowed model is used up. Refused BEFORE any HTTP request.

    Attributes:
        provider, model: what was asked for
        remaining: requests left today over all keys (0 when refused)
        reset_at: ISO time (UTC) when the ledger allows requests again
        source: 'ledger' (our own count) or 'server' (the provider answered 429 for a per-day quota)
    """

    def __init__(self, message: str, provider: str = "", model: str = "", remaining: int = 0, reset_at: str = "", source: str = "ledger") -> None:
        """Keep the figures."""
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.remaining = remaining
        self.reset_at = reset_at
        self.source = source


class HostedHttpError(HostedError):
    """The API answered with an error status.

    Attributes:
        status: HTTP status code
        code: the API's status string ('RESOURCE_EXHAUSTED', 'INVALID_ARGUMENT', 'rate_limit_exceeded', ...) when given
        retry_after: seconds the server asked us to wait (Retry-After header or RetryInfo detail), when given
        per_day: True when a 429 names a per-day quota (retrying today cannot help)
    """

    def __init__(self, message: str, status: int, code: str | None = None, retry_after: float | None = None, per_day: bool = False) -> None:
        """Keep the status, code and retry hint."""
        super().__init__(message)
        self.status = status
        self.code = code
        self.retry_after = retry_after
        self.per_day = per_day


class HostedAuthError(HostedHttpError):
    """401/403 on every key: invalid, missing or unauthorised API keys."""


class HostedRateLimited(HostedHttpError):
    """429 or 500/503 that persisted through every retry, or the per-minute wait would exceed `max_wait_s`."""


# The Gemini free tier is the first generic provider; these names read better at its call sites and in its docs.
GeminiError = HostedError
GeminiPolicyError = HostedPolicyError
GeminiQuotaExceeded = HostedQuotaExceeded
GeminiRateLimited = HostedRateLimited
