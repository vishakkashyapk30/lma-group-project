"""OpenAI integration (external API; OFF by default; hard spending cap). See `ledger` for the cap, `sarvam.policy` for the shared privacy gate, and configs/models.yaml `openai:`."""

from vakeel_sahayak.models.openai.config import HARD_MAX_USD, effective_cap_usd, key_is_set, openai_config
from vakeel_sahayak.models.openai.errors import (
    BudgetExceeded,
    OpenAIAuthError,
    OpenAIError,
    OpenAIHttpError,
    OpenAIPolicyError,
    OpenAIQuotaError,
    OpenAIRateLimited,
    OpenAIUnavailable,
)
from vakeel_sahayak.models.openai.ledger import Ledger, ResponseCache, report

__all__ = [
    "HARD_MAX_USD", "BudgetExceeded", "Ledger", "OpenAIAuthError", "OpenAIError", "OpenAIHttpError", "OpenAIPolicyError", "OpenAIQuotaError",
    "OpenAIRateLimited", "OpenAIUnavailable", "ResponseCache", "effective_cap_usd", "key_is_set", "openai_config", "report",
]  # fmt: skip
