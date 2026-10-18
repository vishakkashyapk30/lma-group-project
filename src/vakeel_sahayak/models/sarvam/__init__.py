"""Sarvam AI integration (external API; OFF by default; see `policy` for the privacy rules and configs/models.yaml `sarvam:`)."""

from vakeel_sahayak.models.sarvam.errors import (
    SarvamAuthError,
    SarvamError,
    SarvamHttpError,
    SarvamPolicyError,
    SarvamQuotaError,
    SarvamRateLimited,
    SarvamUnavailable,
)
from vakeel_sahayak.models.sarvam.policy import (
    DataClass,
    SarvamMode,
    SarvamScope,
    authorize,
    current_scope,
    has_consent,
    public_scope,
    record_consent,
    sarvam_mode,
    sarvam_scope,
)

__all__ = [
    "DataClass", "SarvamAuthError", "SarvamError", "SarvamHttpError", "SarvamMode", "SarvamPolicyError", "SarvamQuotaError",
    "SarvamRateLimited", "SarvamScope", "SarvamUnavailable", "authorize", "current_scope", "has_consent", "public_scope",
    "record_consent", "sarvam_mode", "sarvam_scope",
]  # fmt: skip
