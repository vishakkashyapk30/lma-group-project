"""Until a person re-checks the rule texts, every Rights result reads 'unverified' (never an invented date)."""

from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult, RightsReport


def test_unverified_until_a_date_is_set():
    a = RightsCheckResult(check=RightsCheckName.DEFAULT_BAIL, status=RightsStatus.CHECK)
    b = RightsCheckResult(check=RightsCheckName.STATUTORY_BAR, status=RightsStatus.CHECK, last_verified="2026-10-01")
    assert a.verification == "unverified" and b.verification == "2026-10-01"
    rep = RightsReport(case_id="case-0007", as_of="2026-10-27", checks=[a, b])
    assert rep.unverified_checks == [RightsCheckName.DEFAULT_BAIL.value]
    assert "verification" not in a.model_dump()
