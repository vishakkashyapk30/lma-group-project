"""Rights Radar rule 'production_24h' (plan §7.3, Appendix C)."""

from __future__ import annotations

from datetime import datetime

from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.day_count import parse_date
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult


class Production24hRule(Rule):
    """Rights Radar rule: production_24h (plan §7.3, Appendix C)."""

    rule_id = RightsCheckName.PRODUCTION_24H
    rule_text = "Arrested person must be produced before a magistrate within 24 hours of arrest, excluding travel time."
    sources = ["Art. 22(2)", "BNSS s.58 (CrPC s.57)"]
    rule_cite = "Art. 22(2); BNSS s.58"
    last_verified = None  # TODO: date of week-0 check against the bare act
    allowed_statuses = [RightsStatus.FLAG, RightsStatus.OK, RightsStatus.CHECK]

    def evaluate(self, inputs: RuleInputs) -> RightsCheckResult:
        """Evaluate 'production_24h'. Allowed statuses: FLAG, OK, CHECK. Output must include the rule text, source and dates used.

        Args:
            inputs: see behaviour

        Returns:
            RightsCheckResult.
        """
        uses = ["arrest_date", "production_date"]
        arrest = _stamp(inputs.arrest_date, inputs.arrest_time)
        produced = _stamp(inputs.production_date, inputs.production_time)
        dates = {"arrest_date": inputs.arrest_date, "production_date": inputs.production_date}
        if arrest and produced:
            hours = (produced - arrest).total_seconds() / 3600
            if hours > 24:
                return self.result(
                    RightsStatus.FLAG,
                    f"Produced {hours:.1f} hours after arrest, more than 24 hours. Travel time is excluded, so check the travel time.",
                    uses + ["arrest_time", "production_time"],
                    dates,
                )
            return self.result(
                RightsStatus.OK,
                f"Produced {hours:.1f} hours after arrest, within 24 hours.",
                uses + ["arrest_time", "production_time"],
                dates,
            )
        if inputs.arrest_date and inputs.production_date:
            gap = (parse_date(inputs.production_date) - parse_date(inputs.arrest_date)).days
            if gap >= 2:
                return self.result(
                    RightsStatus.FLAG,
                    f"Produced {gap} calendar days after arrest, which is more than 24 hours whatever the times. Travel time is excluded, so check the travel time.",
                    uses,
                    dates,
                )
            if gap == 0:
                return self.result(RightsStatus.OK, "Produced on the day of arrest, so within 24 hours.", uses, dates)
            return self.result(RightsStatus.CHECK, "Produced the next day; times not on record.", uses, dates)
        return self.result(RightsStatus.CHECK, "Arrest or production date is not on record.", uses, dates)


def _stamp(day: str | None, clock: str | None) -> datetime | None:
    """Combine a date and a time of day (or accept a full ISO date-time in `clock`); None if either is missing."""
    if not clock:
        return None
    try:
        if "T" in clock or " " in clock.strip():
            return datetime.fromisoformat(clock.strip())
        if not day:
            return None
        return datetime.fromisoformat(f"{day}T{clock.strip()}")
    except ValueError:
        return None
