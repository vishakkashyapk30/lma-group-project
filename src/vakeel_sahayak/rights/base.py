"""Abstract rule interface (plan §7.3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult


class Rule(ABC):
    """A Rights Radar rule. Every rule shows its rule text, source and the dates used; unsettled law returns CHECK; each rule has a 'last verified' date (plan §7.3, Appendix C)."""

    rule_id: RightsCheckName
    rule_text: str = ""
    sources: list[str] = []
    rule_cite: str = ""  # short citation shown in RightsCheckResult.rule (plan §7.3 example)
    last_verified: str | None = None  # None means UNVERIFIED (shown as 'unverified'). Person task, not to be guessed: Harshita re-checks every rule text against the bare act, then sets it in configs/rights_rules.yaml (docs/handoff/product-complete.md)
    allowed_statuses: list[RightsStatus] = []
    params: dict[str, Any] = {}  # rule parameters from configs/rights_rules.yaml (`params:`)

    @abstractmethod
    def evaluate(self, inputs: RuleInputs) -> RightsCheckResult:
        """Apply the rule deterministically.

        Args:
            inputs: see behaviour

        Returns:
            A result with status, detail, uses, rule and last_verified.
        """
        raise NotImplementedError

    def result(
        self,
        status: RightsStatus,
        detail: str,
        uses: list[str],
        dates: dict[str, str | None] | None = None,
    ) -> RightsCheckResult:
        """Build a result carrying the rule text, sources and the dates used; rejects statuses the rule may not return.

        Args:
            status: must be one of `allowed_statuses`
            detail: human-readable explanation with the numbers behind the status
            uses: dossier fields or events the rule read
            dates: dates used, omitting None values

        Returns:
            RightsCheckResult.
        """
        if status not in self.allowed_statuses:
            raise ValueError(f"{self.rule_id.value} may not return {status.value}")
        return RightsCheckResult(
            check=self.rule_id,
            status=status,
            detail=detail,
            uses=uses,
            rule=self.rule_cite or "; ".join(self.sources),
            rule_text=self.rule_text,
            sources=list(self.sources),
            dates={k: v for k, v in (dates or {}).items() if v},
            last_verified=self.last_verified,
        )
