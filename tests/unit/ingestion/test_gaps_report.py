"""Gap handling and the IngestionReport (plan §4.3 step 4-6, §4.6).

At most 3 questions per round (configs/budgets.yaml `questions_per_round`, shared by Munshi and Peshkar) and all
unreadable pages are grouped into ONE question.
"""

from __future__ import annotations

import pytest

from tests.unit.ingestion._helpers import patch_attr_everywhere
from vakeel_sahayak.ingestion.gaps import resolve_gap
from vakeel_sahayak.ingestion.report import build_report
from vakeel_sahayak.schemas.enums import DocumentType, PageStatus
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry, FiledCounts, Gap, IngestionReport, PageRoute

CHARGE_SHEET_Q = "Has the charge sheet been filed? If so, please upload the order."
CUSTODY_Q = "Is there a jail custody certificate for the accused?"
COACCUSED_Q = "Was any co-accused granted bail? If so, please upload the order."
EXTRA_Q = "What is the name of the police station?"


def fir_with_unreadable(pages: list[int], first: int = 1, last: int = 3) -> DocumentEntry:
    routes = [PageRoute(page=p, kind="scanned", route=["ocr: surya-hi", "vision: qwen3-vl"],
                        status=PageStatus.UNREADABLE if p in pages else PageStatus.OK) for p in range(first, last + 1)]
    return DocumentEntry(doc_id="d1", type=DocumentType.FIR, pages=[first, last], lang="hi", type_confidence=0.94, page_routes=routes)


def per_page_question(page: int) -> str:
    return f"Page {page} of the FIR is unreadable. Can you upload a clearer copy?"


def mentions_all(question: str, pages: list[int]) -> bool:
    return all(f"{p}" in question for p in pages)


# ---- config facts (pass today) -----------------------------------------------------------------------------------
def test_question_limit_is_three_per_round_in_config(load_yaml):
    """Plan §4.3: Munshi and Peshkar share a limit of 3 questions per round."""
    assert load_yaml("budgets.yaml")["questions_per_round"] == 3
    assert load_yaml("thresholds.yaml")["safety"]["max_questions_per_round"] == 3


def test_report_schema_has_the_plan_fields():
    """Plan §4.6: case_id, file, documents, filed, gaps, questions; filed counts timeline events, parties, sections, chunks."""
    assert list(IngestionReport.model_fields) == ["case_id", "file", "documents", "filed", "gaps", "questions"]
    assert list(FiledCounts.model_fields) == ["timeline_events", "parties", "sections", "chunks"]
    assert list(Gap.model_fields) == ["item", "action"]


# ---- build_report ------------------------------------------------------------------------------------------------
def test_report_is_assembled_exactly_as_plan_example():
    """Plan §4.6 example: documents, filed counts, gap and two questions come through unchanged."""
    d1 = fir_with_unreadable([3])
    d2 = DocumentEntry(doc_id="d2", type=DocumentType.REMAND_ORDER, pages=[4, 5], lang="en",
                       page_routes=[PageRoute(page=4, kind="born-digital", route=["text_layer"]),
                                    PageRoute(page=5, kind="born-digital", route=["text_layer"])])
    filed = FiledCounts(timeline_events=6, parties=4, sections=2, chunks=31)
    gaps = [Gap(item="charge-sheet status", action="searched pages 6-14; not found; asked counsel")]
    questions = [per_page_question(3), CHARGE_SHEET_Q]
    report = build_report("case-0007", "bundle_1.pdf", [d1, d2], filed, gaps, questions)
    assert isinstance(report, IngestionReport)
    assert (report.case_id, report.file) == ("case-0007", "bundle_1.pdf")
    assert report.documents == [d1, d2]
    assert report.filed == filed
    assert report.gaps == gaps
    assert report.questions == questions


def test_report_without_problems_has_no_questions():
    """A clean ingestion has empty gaps and questions."""
    doc = fir_with_unreadable([], 1, 2)
    report = build_report("case-0001", "f.pdf", [doc], FiledCounts(), [], [])
    assert report.gaps == [] and report.questions == []


def test_report_round_trips_through_json():
    """The report serialises to JSON and back unchanged (it is the Munshi-to-Peshkar hand-off)."""
    report = build_report("case-0007", "bundle_1.pdf", [fir_with_unreadable([3])], FiledCounts(timeline_events=2),
                          [Gap(item="fir page 3", action="asked counsel")], [per_page_question(3)])
    assert IngestionReport.model_validate_json(report.model_dump_json()) == report


def test_three_unreadable_pages_become_one_grouped_question():
    """Three unreadable pages asked about one by one are grouped into ONE question naming all three pages."""
    # ASSUMPTION: build_report enforces grouping from the page statuses in `documents` (pages 2, 3 and 5 are UNREADABLE).
    doc = fir_with_unreadable([2, 3, 5], 1, 5)
    questions = [per_page_question(2), per_page_question(3), per_page_question(5)]
    report = build_report("case-0007", "bundle_1.pdf", [doc], FiledCounts(), [], questions)
    assert len(report.questions) == 1
    assert mentions_all(report.questions[0], [2, 3, 5])


def test_unreadable_pages_with_no_question_get_one_grouped_question():
    """ASSUMPTION: every unreadable page must be covered by a question, so report building adds one grouped question."""
    doc = fir_with_unreadable([2, 3, 5], 1, 5)
    report = build_report("case-0007", "bundle_1.pdf", [doc], FiledCounts(), [], [])
    assert len(report.questions) == 1
    assert mentions_all(report.questions[0], [2, 3, 5])


def test_other_questions_survive_next_to_the_grouped_one():
    """Grouping unreadable pages leaves room: grouped question + charge-sheet question = 2 questions."""
    doc = fir_with_unreadable([2, 3], 1, 3)
    questions = [per_page_question(2), per_page_question(3), CHARGE_SHEET_Q]
    report = build_report("case-0007", "f.pdf", [doc], FiledCounts(), [], questions)
    assert len(report.questions) == 2
    assert CHARGE_SHEET_Q in report.questions
    assert any(mentions_all(q, [2, 3]) for q in report.questions)


@pytest.mark.parametrize("n_questions", [0, 1, 2, 3])
def test_up_to_three_questions_are_kept_as_given(n_questions):
    """Up to the limit of three, all questions pass through in order."""
    qs = [CHARGE_SHEET_Q, CUSTODY_Q, COACCUSED_Q][:n_questions]
    report = build_report("case-0007", "f.pdf", [fir_with_unreadable([], 1, 2)], FiledCounts(), [], qs)
    assert report.questions == qs


def test_more_than_three_questions_are_cut_to_three_in_order():
    """ASSUMPTION: a fourth and fifth question are deferred (not in this round's report); the first three keep their order."""
    qs = [CHARGE_SHEET_Q, CUSTODY_Q, COACCUSED_Q, EXTRA_Q, "Is the FIR number 112/2024?"]
    report = build_report("case-0007", "f.pdf", [fir_with_unreadable([], 1, 2)], FiledCounts(), [], qs)
    assert report.questions == qs[:3]


def test_grouped_unreadable_question_survives_the_cap():
    """Unreadable pages stay asked about even when other questions would exceed three: total 3, grouped question present."""
    doc = fir_with_unreadable([2, 3], 1, 3)
    qs = [per_page_question(2), per_page_question(3), CHARGE_SHEET_Q, CUSTODY_Q, COACCUSED_Q]
    report = build_report("case-0007", "f.pdf", [doc], FiledCounts(), [], qs)
    assert len(report.questions) == 3
    assert any(mentions_all(q, [2, 3]) for q in report.questions)


# ---- resolve_gap -------------------------------------------------------------------------------------------------
class _Recorder:
    def __init__(self, hits):
        self.hits = hits
        self.searches: list[tuple] = []
        self.asked: list[list[str]] = []

    def search_pages(self, case_id, query, k=5):
        self.searches.append((case_id, query, k))
        return list(self.hits)

    def ask_user(self, questions, case_id):
        self.asked.append(list(questions))
        return ["" for _ in questions]


def _install(monkeypatch, hits):
    rec = _Recorder(hits)
    for mod, attr, fn in [("vakeel_sahayak.tools.intake.documents", "search_pages", rec.search_pages),
                          ("vakeel_sahayak.tools.interaction", "ask_user", rec.ask_user)]:
        patch_attr_everywhere(monkeypatch, mod, attr, fn)
    return rec


def test_gap_not_found_in_remaining_pages_asks_counsel(monkeypatch):
    """Plan §4.3 step 4: search the remaining pages; if the item is not there, ask counsel for the document."""
    rec = _install(monkeypatch, hits=[])
    gap = resolve_gap("charge-sheet status", "case-0007")
    assert isinstance(gap, Gap)
    assert gap.item == "charge-sheet status"
    assert rec.searches, "remaining pages are searched first"
    assert len(rec.asked) == 1
    assert "counsel" in gap.action.lower()


def test_gap_found_in_remaining_pages_does_not_ask_counsel(monkeypatch):
    """If a remaining page holds the item, no question is raised and the action names the page found."""
    rec = _install(monkeypatch, hits=[{"page": 9, "text": "Charge sheet filed on 02.11.2024"}])
    gap = resolve_gap("charge-sheet status", "case-0007")
    assert rec.asked == []
    assert gap.item == "charge-sheet status"
    assert "9" in gap.action
