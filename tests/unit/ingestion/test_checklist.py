"""Bail-file checklist and gap detection (plan §4.3 step 4).

Checklist: FIR, arrest date, first remand, earlier bail orders, charge-sheet status, custody certificate, co-accused orders.
"""

from __future__ import annotations

import pytest

from vakeel_sahayak.ingestion.checklist import BAIL_FILE_CHECKLIST, missing_items
from vakeel_sahayak.schemas.enums import DocumentType as D

# ASSUMPTION on evidence per item (the plan gives only the item names):
#   fir -> a FIR document;  earlier_bail_orders -> a BAIL_ORDER document;  custody_certificate -> a CUSTODY_CERTIFICATE document;
#   arrest_date / first_remand / charge_sheet_status -> a timeline label mentioning arrest / first remand / charge sheet;
#   co_accused_orders -> a timeline label mentioning the co-accused (there is no document type for co-accused orders).
ALL_DOCS = [D.FIR.value, D.REMAND_ORDER.value, D.BAIL_ORDER.value, D.CUSTODY_CERTIFICATE.value]
ALL_LABELS = ["Arrest", "First remand", "Charge sheet filed", "Co-accused-1 granted bail"]


def test_checklist_is_the_plan_list_in_order():
    """Plan §4.3 step 4: the seven checklist items, in the plan's order."""
    assert BAIL_FILE_CHECKLIST == [
        "fir", "arrest_date", "first_remand", "earlier_bail_orders", "charge_sheet_status", "custody_certificate",
        "co_accused_orders",
    ]


def test_checklist_has_no_duplicates():
    """Each item appears once."""
    assert len(BAIL_FILE_CHECKLIST) == len(set(BAIL_FILE_CHECKLIST)) == 7


def test_empty_file_is_missing_everything():
    """Nothing filed: every checklist item is missing, in checklist order."""
    assert missing_items([], []) == BAIL_FILE_CHECKLIST


def test_complete_file_has_no_gaps():
    """Everything filed and every dated event on the timeline: no gaps."""
    assert missing_items(ALL_DOCS, ALL_LABELS) == []


def test_case_0007_style_file_misses_custody_certificate_and_co_accused_orders():
    """FIR, remand, bail order and order sheet filed; timeline has arrest, first remand, charge sheet -> two gaps."""
    docs = [D.FIR.value, D.REMAND_ORDER.value, D.BAIL_ORDER.value, D.ORDER_SHEET.value]
    labels = ["Arrest", "First remand", "Charge sheet filed"]
    assert missing_items(docs, labels) == ["custody_certificate", "co_accused_orders"]


@pytest.mark.parametrize(
    ("drop_doc", "drop_label", "missing"),
    [
        (D.FIR.value, None, "fir"),
        (D.BAIL_ORDER.value, None, "earlier_bail_orders"),
        (D.CUSTODY_CERTIFICATE.value, None, "custody_certificate"),
        (None, "Arrest", "arrest_date"),
        (None, "First remand", "first_remand"),
        (None, "Charge sheet filed", "charge_sheet_status"),
        (None, "Co-accused-1 granted bail", "co_accused_orders"),
    ],
)
def test_removing_one_source_reveals_exactly_that_gap(drop_doc, drop_label, missing):
    """Dropping the single document or timeline event behind one item makes exactly that item missing."""
    docs = [d for d in ALL_DOCS if d != drop_doc]
    labels = [l for l in ALL_LABELS if l != drop_label]
    assert missing_items(docs, labels) == [missing]


def test_timeline_labels_match_case_insensitively():
    """Labels are matched case-insensitively ('arrest' satisfies the arrest-date item)."""
    labels = [l.lower() for l in ALL_LABELS]
    assert missing_items(ALL_DOCS, labels) == []


def test_missing_items_only_returns_checklist_keys():
    """Whatever is filed, the result is a sub-list of the checklist in checklist order."""
    out = missing_items([D.FIR.value], ["Arrest"])
    assert out == [i for i in BAIL_FILE_CHECKLIST if i in out]
    assert "fir" not in out and "arrest_date" not in out
