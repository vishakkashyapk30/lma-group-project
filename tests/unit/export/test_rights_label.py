"""Every Rights rule not yet checked against the bare act carries a visible negative label in the exports (design review
2026-10-27, item 7): bracketed notes under the application's statutory position, a column on the hearing-prep card."""

from __future__ import annotations

import pytest

from tests.unit.export._helpers import docx_text, make_brief, uploaded_docs
from vakeel_sahayak.export.application import assemble_application_docx
from vakeel_sahayak.export.hearing_card import write_hearing_card_docx
from vakeel_sahayak.export.rights import UNVERIFIED_LABEL, rights_rows, unverified_notes
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult, RightsReport


def report() -> RightsReport:
    return RightsReport(case_id="case-0007", as_of="2026-10-29", checks=[
        RightsCheckResult(check=RightsCheckName.DEFAULT_BAIL, status=RightsStatus.NOT_YET, rule="BNSS s.187(3)"),
        RightsCheckResult(check=RightsCheckName.NOTICE_OF_APPEARANCE, status=RightsStatus.OK, rule="BNSS s.35(3)", last_verified="2026-10-27"),
    ])


def test_label_text():
    assert UNVERIFIED_LABEL == "Not yet checked against the bare act"


def test_rows_label_unverified_and_date_verified():
    rows = {r[0]: r for r in rights_rows(report())}
    assert rows["default bail"][3] == UNVERIFIED_LABEL
    assert "2026-10-27" in rows["notice of appearance"][3] and UNVERIFIED_LABEL not in rows["notice of appearance"][3]


def test_notes_only_for_unverified_checks():
    notes = unverified_notes(report())
    assert len(notes) == 1 and UNVERIFIED_LABEL in notes[0] and "default bail" in notes[0]
    assert unverified_notes(None) == [] and rights_rows(None) == []


def test_application_carries_the_label_under_the_statutory_position(tmp_path, dossier, timeline):
    pytest.importorskip("docx")
    path = assemble_application_docx(make_brief(), dossier, timeline, uploaded_docs(), str(tmp_path / "a.docx"), rights=report())
    text = docx_text(path)
    at = text.find(UNVERIFIED_LABEL)
    assert at > text.lower().find("statutory position") >= 0
    assert text.count(UNVERIFIED_LABEL) == 1  # the verified rule gets no note


def test_application_without_a_report_is_unchanged(tmp_path, dossier, timeline):
    pytest.importorskip("docx")
    path = assemble_application_docx(make_brief(), dossier, timeline, uploaded_docs(), str(tmp_path / "a.docx"))
    assert UNVERIFIED_LABEL not in docx_text(path)


def test_hearing_card_lists_every_check_with_its_verification(tmp_path):
    pytest.importorskip("docx")
    card = {"lead_points": [], "bench_concerns": [], "conditions": [], "open_issues": []}
    text = docx_text(write_hearing_card_docx(card, "case-0007", str(tmp_path / "c.docx"), rights=report()))
    assert "Rights checks" in text and UNVERIFIED_LABEL in text and "2026-10-27" in text
    plain = docx_text(write_hearing_card_docx(card, "case-0007", str(tmp_path / "d.docx")))
    assert "Rights checks" not in plain
