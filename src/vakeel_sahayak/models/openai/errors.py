"""Errors of the OpenAI integration. All are `ModelUnavailable`, so tools and the labeler treat them as 'model cannot run'.

No message ever carries the API key or any prompt text.
"""

from __future__ import annotations

from vakeel_sahayak.models.base import ModelUnavailable


class OpenAIError(ModelUnavailable):
    """Base class of every OpenAI failure."""


class OpenAIUnavailable(OpenAIError):
    """No API key in the environment (OPENAI_API_KEY), no price for the model, or the service could not be reached after the retries.

    Attributes:
        maybe_billed: True when the request may have reached OpenAI (a timeout), so the ledger keeps its reservation.
    """

    def __init__(self, message: str, maybe_billed: bool = False) -> None:
        """Keep whether the call could have been billed."""
        super().__init__(message)
        self.maybe_billed = maybe_billed


class OpenAIPolicyError(OpenAIError):
    """The privacy policy forbids this call (mode, data class or missing counsel consent). Nothing was sent."""


class BudgetExceeded(OpenAIError):
    """The spending cap would be exceeded by this call's worst case (or the run cap). Refused BEFORE any HTTP request.

    Attributes:
        spent_micro: micro-USD already spent or reserved
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


class OpenAIHttpError(OpenAIError):
    """The API answered with an error status.

    Attributes:
        status: HTTP status code
        code: the API's error code ('invalid_api_key', 'insufficient_quota', ...) when given
        param: the offending request parameter when the API names it
    """

    def __init__(self, message: str, status: int, code: str | None = None, param: str | None = None) -> None:
        """Keep the status, code and parameter."""
        super().__init__(message)
        self.status = status
        self.code = code
        self.param = param


class OpenAIAuthError(OpenAIHttpError):
    """401/403: invalid, missing or unauthorised API key."""


class OpenAIRateLimited(OpenAIHttpError):
    """429 or 5xx that persisted through every retry."""


class OpenAIQuotaError(OpenAIHttpError):
    """429 `insufficient_quota`: the account credit is exhausted. Retrying cannot help, so it is not retried."""
