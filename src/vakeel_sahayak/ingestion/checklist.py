"""Bail-file checklist used for gap checks (plan §4.3 step 4)."""

from __future__ import annotations

BAIL_FILE_CHECKLIST: list[str] = [
    "fir",
    "arrest_date",
    "first_remand",
    "earlier_bail_orders",
    "charge_sheet_status",
    "custody_certificate",
    "co_accused_orders",
]


def missing_items(filed_doc_types: list[str], timeline_labels: list[str]) -> list[str]:
    """Compare what is filed with the checklist.

    Args:
        filed_doc_types: see behaviour
        timeline_labels: see behaviour

    Returns:
        Missing checklist items.
    """
    raise NotImplementedError
