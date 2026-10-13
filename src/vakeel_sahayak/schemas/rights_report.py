"""RightsReport schema (plan §7.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.ids import CaseId, IsoDate


class RightsCheckResult(BaseModel):
    """Result of one Rights Radar check (plan §7.3)."""

    check: RightsCheckName
    status: RightsStatus
    detail: str | None = None
    uses: list[str] = Field(default_factory=list)  # dossier fields / events used
    rule: str | None = None  # source citation, e.g. 'BNSS s.187(3)'
    rule_text: str | None = None  # the rule as coded (Appendix C), shown with every output (plan §7.3)
    sources: list[str] = Field(default_factory=list)  # full source list for the rule
    dates: dict[str, str] = Field(default_factory=dict)  # the dates the rule used, e.g. {'first_remand': '2024-08-21'}
    last_verified: str | None = None


class RightsReport(BaseModel):
    """Rights Radar output (plan §7.3)."""

    case_id: CaseId
    as_of: IsoDate
    checks: list[RightsCheckResult] = Field(default_factory=list)

    def get(self, check: RightsCheckName | str) -> RightsCheckResult | None:
        """Return the result of one check by name, or None if the report does not hold it."""
        name = RightsCheckName(check)
        return next((c for c in self.checks if c.check == name), None)
