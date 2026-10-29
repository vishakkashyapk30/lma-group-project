"""Rights Radar results as the exports show them (design review 2026-10-27, item 7).

A rule nobody has checked against the bare act carries a visible negative label, never just the absence of a "checked"
mark: counsel must see on paper which entitlements rest on an unchecked rule.
"""

from __future__ import annotations

from vakeel_sahayak.schemas.rights_report import RightsCheckResult, RightsReport

UNVERIFIED_LABEL = "Not yet checked against the bare act"


def check_name(check: RightsCheckResult) -> str:
    """'default bail' for `default_bail`."""
    return check.check.value.replace("_", " ")


def verification_text(check: RightsCheckResult) -> str:
    """'Checked against the bare act on <date>' or the unverified label."""
    return f"Checked against the bare act on {check.last_verified}" if check.last_verified else UNVERIFIED_LABEL


def rights_rows(report: RightsReport | None) -> list[list[str]]:
    """One row per check: name, status, rule cited, verification text."""
    if report is None:
        return []
    return [[check_name(c), c.status.value.replace("_", " "), c.rule or "; ".join(c.sources), verification_text(c)] for c in report.checks]


def unverified_notes(report: RightsReport | None) -> list[str]:
    """Bracketed notes for counsel, one per unverified check (the application's placeholder convention)."""
    if report is None:
        return []
    return [f"[{UNVERIFIED_LABEL}: {check_name(c)}" + (f" ({c.rule})" if c.rule else "") + ". Counsel to verify before relying on it.]"
            for c in report.checks if not c.last_verified]
