"""Errors of the Sarvam integration. All are `ModelUnavailable`, so tools and the labeler treat them as 'model cannot run'."""

from __future__ import annotations

from vakeel_sahayak.models.base import ModelUnavailable


class SarvamError(ModelUnavailable):
    """Base class of every Sarvam failure."""


class SarvamUnavailable(SarvamError):
    """No API key in the environment (SARVAM_API_KEY), or the service could not be reached after the retries."""


class SarvamPolicyError(SarvamError):
    """The privacy policy forbids this call (mode, data class or missing counsel consent). Nothing was sent."""


class SarvamHttpError(SarvamError):
    """The API answered with an error status.

    Attributes:
        status: HTTP status code
        code: the API's error code ('invalid_request_error', 'rate_limit_exceeded_error', ...) when given
    """

    def __init__(self, message: str, status: int, code: str | None = None) -> None:
        """Keep the status and the API's error code."""
        super().__init__(message)
        self.status = status
        self.code = code


class SarvamAuthError(SarvamHttpError):
    """403: invalid, missing or unknown API key (Sarvam uses 403, not 401)."""


class SarvamRateLimited(SarvamHttpError):
    """429/503 that persisted through every retry."""


class SarvamQuotaError(SarvamHttpError):
    """429 `insufficient_quota_error`: the credits are exhausted. Retrying cannot help, so it is not retried."""


class SarvamBudgetExceeded(SarvamError):
    """The Sarvam spending cap (or the run cap) would be exceeded by this call's worst case. Refused BEFORE any HTTP request.

    A `SarvamError`, so the existing fallback path (`FallbackLLM`, `_Fallback`) answers with the local client instead.

    Attributes:
        spent_micro: micro-INR already spent or reserved
        needed_micro: the worst-case cost of the refused call
        cap_micro: the cap that applied (total or per-run)
        scope: 'total' or 'run'
    """

    def __init__(self, message: str, spent_micro: int = 0, needed_micro: int = 0, cap_micro: int = 0, scope: str = "total") -> None:
        """Keep the figures."""
        super().__init__(message)
        self.spent_micro = spent_micro
        self.needed_micro = needed_micro
        self.cap_micro = cap_micro
        self.scope = scope


BudgetExhausted = SarvamBudgetExceeded
