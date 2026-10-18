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
