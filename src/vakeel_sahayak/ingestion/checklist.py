"""Bail-file checklist used for gap checks (plan §4.3 step 4)."""

from __future__ import annotations

from collections.abc import Iterable

from vakeel_sahayak.ingestion.events import field_of_label

BAIL_FILE_CHECKLIST: list[str] = [
    "fir",
    "arrest_date",
    "first_remand",
    "earlier_bail_orders",
    "charge_sheet_status",
    "custody_certificate",
    "co_accused_orders",
]

# What counsel is told about each item, and in what order a limited number of questions is spent on them.
ITEM_NAMES = {
    "fir": "FIR",
    "arrest_date": "arrest date",
    "first_remand": "first remand",
    "earlier_bail_orders": "earlier bail orders",
    "charge_sheet_status": "charge-sheet status",
    "custody_certificate": "custody certificate",
    "co_accused_orders": "co-accused orders",
}
ITEM_QUESTIONS = {
    "fir": "The FIR is not in the file. Can you upload it?",
    "arrest_date": "The file does not show when the accused was arrested. What is the arrest date, or can you upload the arrest memo?",
    "first_remand": "The first remand order is not in the file. Can you upload it?",
    "earlier_bail_orders": "Has any earlier bail application been decided? If so, please upload the order.",
    "charge_sheet_status": "Has the charge sheet been filed? If so, please upload the order.",
    "custody_certificate": "Can you upload the jail custody certificate?",
    "co_accused_orders": "Were any co-accused granted or refused bail? If so, please upload their orders.",
}
QUESTION_PRIORITY = ["fir", "arrest_date", "charge_sheet_status", "first_remand", "earlier_bail_orders", "custody_certificate", "co_accused_orders"]


def missing_items(
    filed_doc_types: list[str], timeline_labels: list[str], stated_facts: Iterable[str] | None = None
) -> list[str]:
    """Compare what is filed with the checklist.

    An item is met when a document of the right type is filed or the timeline holds a matching dated event: FIR (an FIR
    or an FIR-registered event), arrest date (an arrest event; an arrest memo alone gives no date), first remand (a
    dated remand event; a remand order whose date was not read does not count), earlier bail orders (a bail order or a bail outcome event), charge-sheet status (a charge
    sheet cover, a charge-sheet event or a stated status), custody certificate (the certificate) and co-accused orders
    (a stated co-accused outcome or a co-accused event).

    Args:
        filed_doc_types: document type values of what is filed ('FIR', 'REMAND_ORDER', ...)
        timeline_labels: labels of the events on the timeline
        stated_facts: facts the text states without a dated event, e.g. 'charge_sheet_status', 'co_accused_outcome'

    Returns:
        Missing checklist items, in checklist order.
    """
    types = {getattr(t, "value", t) for t in filed_doc_types}
    fields = {f for f in (field_of_label(label) for label in timeline_labels) if f}
    stated = set(stated_facts or [])
    met = {
        "fir": "FIR" in types or "fir_date" in fields,
        "arrest_date": "arrest_date" in fields,
        "first_remand": bool(fields & {"remand", "first_remand"}),
        "earlier_bail_orders": "BAIL_ORDER" in types or "bail_outcome" in fields,
        "charge_sheet_status": "CHARGE_SHEET_COVER" in types or "charge_sheet_date" in fields or "charge_sheet_status" in stated,
        "custody_certificate": "CUSTODY_CERTIFICATE" in types,
        "co_accused_orders": "co_accused_outcome" in stated or any(label.strip().lower().startswith("co-accused") for label in timeline_labels),
    }
    return [item for item in BAIL_FILE_CHECKLIST if not met[item]]
