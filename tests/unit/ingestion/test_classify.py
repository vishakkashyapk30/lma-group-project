"""Document labelling and paragraph tagging (plan §4.3 step 2, §4.4).

Labels: FIR, arrest memo, remand order, bail order, order sheet, charge-sheet cover, custody certificate, medical record,
affidavit, other. Paragraph tags: dated event, party, section, earlier outcome, custody, personal circumstance.
"""

from __future__ import annotations

import pytest

from tests.fixtures import pdfgen
from vakeel_sahayak.ingestion.classify import label_document, tag_paragraph
from vakeel_sahayak.schemas.enums import DocumentType as D
from vakeel_sahayak.schemas.enums import InfoKind as I

FIR_EN = ("FIRST INFORMATION REPORT\nFIR No. 112/2024 PS-1\nInformation received under Section 173 BNSS (154 Cr.P.C.)\n"
          "Date of occurrence 10.08.2024. Complainant-1 states that Accused-1 cheated him.")
FIR_HI = "प्रथम सूचना रिपोर्ट\nFIR No. 112/2024 PS-1\nदिनांक 14.08.2024\nधारा 318(4) बी.एन.एस."
ARREST_MEMO = ("ARREST MEMO\nMemo of arrest of Accused-1\nDate and time of arrest 20.08.2024 18:30. Grounds of arrest "
               "communicated. Signature of the arrestee and witness.")
CUSTODY_CERT = ("JAIL CUSTODY CERTIFICATE\nCentral Jail\nIt is certified that Accused-1 has been in judicial custody "
                "since 21.08.2024 in connection with FIR No. 112/2024.\nSuperintendent")
MEDICAL = ("MEDICAL EXAMINATION REPORT\nGovernment Hospital\nPatient Accused-1 is diagnosed with hypertension and "
           "diabetes. Treatment prescribed by the medical officer.")
AFFIDAVIT = ("AFFIDAVIT\nI, resident of Delhi, do hereby solemnly affirm and state on oath as under: that the contents "
             "of this affidavit are true to my knowledge.\nDeponent")
CHARGE_SHEET = ("FINAL REPORT\nCHARGE SHEET\nUnder Section 193 BNSS (173 Cr.P.C.)\nFIR No. 112/2024 PS-1\n"
                "Name of the investigating officer IO-1. Accused sent up for trial.")
UNRECOGNISABLE = "xqzv plmk wrtn bzzq. Lorem ipsum dolor sit amet. 12 34 56."

LABEL_TABLE = [
    pytest.param(FIR_EN, D.FIR, id="fir_english"),
    pytest.param(FIR_HI, D.FIR, id="fir_hindi"),
    pytest.param(ARREST_MEMO, D.ARREST_MEMO, id="arrest_memo"),
    pytest.param(pdfgen.REMAND_PAGE, D.REMAND_ORDER, id="remand_order"),
    pytest.param(pdfgen.BAIL_ORDER_PAGE, D.BAIL_ORDER, id="bail_order"),
    pytest.param(pdfgen.ORDER_SHEET_PAGE, D.ORDER_SHEET, id="order_sheet_mentions_charge_sheet"),
    pytest.param(CHARGE_SHEET, D.CHARGE_SHEET_COVER, id="charge_sheet_cover"),
    pytest.param(CUSTODY_CERT, D.CUSTODY_CERTIFICATE, id="custody_certificate"),
    pytest.param(MEDICAL, D.MEDICAL_RECORD, id="medical_record"),
    pytest.param(AFFIDAVIT, D.AFFIDAVIT, id="affidavit"),
    pytest.param(UNRECOGNISABLE, D.OTHER, id="unrecognisable_is_other"),
]


def test_label_table_covers_every_document_type():
    """The table has one row per DocumentType (plan §4.3: ten labels)."""
    assert {row.values[1] for row in LABEL_TABLE} == set(D)
    assert len(list(D)) == 10


@pytest.mark.parametrize(("text", "expected"), LABEL_TABLE)
def test_label_document(text, expected):
    """Each document kind is recognised from its text; nearby kinds (FIR number in a remand order) do not confuse it."""
    doc_type, _ = label_document(text)
    assert doc_type == expected


@pytest.mark.parametrize("text", [row.values[0] for row in LABEL_TABLE])
def test_confidence_is_a_probability(text):
    """Confidence is always within [0, 1]."""
    _, conf = label_document(text)
    assert 0.0 <= conf <= 1.0


@pytest.mark.parametrize("text", [FIR_EN, pdfgen.REMAND_PAGE, pdfgen.BAIL_ORDER_PAGE, CUSTODY_CERT])
def test_clear_documents_get_confident_labels(text):
    """ASSUMPTION: a document with an explicit title is labelled with confidence >= 0.5."""
    assert label_document(text)[1] >= 0.5


def test_unrecognisable_text_is_not_confidently_labelled():
    """ASSUMPTION: 'other' for unrecognisable text carries confidence at most 0.5, so low confidence can trigger review."""
    doc_type, conf = label_document(UNRECOGNISABLE)
    assert doc_type == D.OTHER and conf <= 0.5


def test_first_page_text_decides_for_headerless_continuation_pages():
    """A later page without a title is labelled from the document's first page (the `first_page_text` argument)."""
    # ASSUMPTION: first_page_text takes precedence when the body alone carries no document-type cue.
    body = "Signature of the Magistrate.\nPage 2 of 2"
    assert label_document(body, first_page_text=pdfgen.REMAND_PAGE)[0] == D.REMAND_ORDER
    assert label_document(body, first_page_text=CUSTODY_CERT)[0] == D.CUSTODY_CERTIFICATE


# ---- tag_paragraph ------------------------------------------------------------------------------------------------
TAG_TABLE = [
    pytest.param("The accused was arrested on 20.08.2024.", {I.DATED_EVENT}, id="dated_event"),
    pytest.param("The offence is punishable under Section 318(4) BNS.", {I.SECTION}, id="section"),
    pytest.param("The learned Sessions Judge held that the bail application is rejected.", {I.EARLIER_OUTCOME}, id="earlier_outcome"),
    pytest.param("Accused-1 has remained in judicial custody since the remand.", {I.CUSTODY}, id="custody"),
    pytest.param("The applicant is the sole earning member of the family.", {I.PERSONAL}, id="personal_circumstance"),
    pytest.param("Accused-1 was named by Complainant-1 in the complaint.", {I.PARTY}, id="party"),
    pytest.param("Accused-1 was arrested on 20.08.2024 under Section 318(4) BNS.", {I.DATED_EVENT, I.SECTION}, id="two_kinds_event_and_section"),
    pytest.param("The bail application was rejected by the Sessions Court on 30.09.2024.", {I.EARLIER_OUTCOME, I.DATED_EVENT}, id="outcome_with_date"),
]


@pytest.mark.parametrize(("text", "expected"), TAG_TABLE)
def test_tag_paragraph_contains_expected_kinds(text, expected):
    """Plan §4.3 step 2: each paragraph is tagged by the kind of information it holds; several kinds are allowed."""
    tags = tag_paragraph(text)
    assert isinstance(tags, list) and all(isinstance(t, I) for t in tags)
    assert expected <= set(tags)


def test_tag_paragraph_has_no_duplicates():
    """A kind appears once even if several cues for it occur."""
    tags = tag_paragraph("Arrested on 20.08.2024, remanded on 21.08.2024 and produced on 22.08.2024.")
    assert len(tags) == len(set(tags))


def test_tag_paragraph_neutral_text_has_no_tags():
    """Text holding none of the six kinds gets no tags."""
    assert tag_paragraph("The matter is listed for hearing.") == []


def test_tag_paragraph_empty_text_is_empty():
    """Empty text has nothing to tag."""
    assert tag_paragraph("") == []


def test_all_six_info_kinds_are_taggable():
    """The six InfoKinds of plan §4.3 are exactly the enum; each has a row in the tag table."""
    assert set(I) == {I.DATED_EVENT, I.PARTY, I.SECTION, I.EARLIER_OUTCOME, I.CUSTODY, I.PERSONAL}
    covered = set().union(*(row.values[1] for row in TAG_TABLE))
    assert covered == set(I)
