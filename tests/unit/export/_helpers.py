"""Helpers for the export tests: case-0007 brief, uploaded-document index and DOCX text extraction.

python-docx is not in the light test venv, so every test that opens a DOCX calls `pytest.importorskip("docx")` first.

ASSUMPTIONS (the plan fixes the *content* of the application, §8.2, not its wording):
* a heading is recognisable by its words (case-insensitive): SYNOPSIS, LIST OF DATES, BRIEF FACTS, EARLIER BAIL, GROUNDS,
  STATUTORY POSITION, PRAYER, VERIFICATION, AFFIDAVIT, ANNEXURE;
* dates are written dd.mm.yyyy (as in the plan's examples, e.g. 05.12.2024); `mentions_date` accepts ISO as well;
* placeholders for real names are square-bracketed capitals, e.g. [APPLICANT NAME];
* `[F:field]` / `[A:doc#para]` tags in a ground are rendered (the DOCX shows the authority's rendered citation, not the tag).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vakeel_sahayak.schemas.bail_brief import Authority, BailBrief, Ground, OpenIssue, StatutoryPosition
from vakeel_sahayak.schemas.enums import (
    ClaimCheck,
    ClaimState,
    DocumentType,
    Factor,
    FactorStance,
    GoodLawStatus,
    OpenIssueType,
    TransferFlag,
)
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry

CASE = "case-0007"

G1_ARGUMENT = "Co-accused-1, with an identical role, was granted bail on 05.12.2024 [F:co_accused_bail]; parity applies [A:DLHC-2022-1187#14]."
G2_ARGUMENT = "The charge sheet was filed on 02.11.2024 [F:charge_sheet], so custodial interrogation is no longer required [A:SC-2014-0463#21]."
G3_ARGUMENT = "The applicant has been in custody for 167 days [F:custody_days] [A:DLHC-2021-0420#11]."
CITATION_G1 = "DLHC-2022-1187, Delhi HC (2022), para 14"
CITATION_G2 = "SC-2014-0463, Supreme Court (2014), para 21"
CITATION_G3 = "DLHC-2021-0420, Delhi HC (2021), para 11"


def make_brief(*, third_needs_review: bool = False, with_issues: bool = True) -> BailBrief:
    g1 = Ground(id="G1", factor=Factor.PARITY_WITH_CO_ACCUSED, stance=FactorStance.FAVOURABLE, argument=G1_ARGUMENT,
                authorities=[Authority(doc_id="DLHC-2022-1187", para=14, citation=CITATION_G1, transfer=TransferFlag.SAME_TEXT,
                                       good_law=GoodLawStatus.OK, sc_root="SC-2014-0463")],
                check=ClaimCheck.SUPPORTED, state=ClaimState.CURRENT)
    g2 = Ground(id="G2", factor=Factor.CHARGE_SHEET_FILED, stance=FactorStance.FAVOURABLE, argument=G2_ARGUMENT,
                authorities=[Authority(doc_id="SC-2014-0463", para=21, citation=CITATION_G2, good_law=GoodLawStatus.OK)],
                check=ClaimCheck.REPAIRED)
    g3 = Ground(id="G3", factor=Factor.CUSTODY_PERIOD, stance=FactorStance.FAVOURABLE, argument=G3_ARGUMENT,
                authorities=[Authority(doc_id="DLHC-2021-0420", para=11, citation=CITATION_G3, transfer=TransferFlag.CHANGED,
                                       good_law=GoodLawStatus.OK)],
                check=ClaimCheck.NEEDS_REVIEW if third_needs_review else ClaimCheck.SUPPORTED)
    issues = [
        OpenIssue(type=OpenIssueType.NEEDS_REVIEW, item="Antecedents unknown: confirm no other pending cases."),
        OpenIssue(type=OpenIssueType.CHANGED_PROVISION, item="DLHC-2021-0420 interprets IPC 420; BNS 318(4) wording differs: qualify."),
        OpenIssue(type=OpenIssueType.MISSING_EVIDENCE, item="No trial-delay authority in the same section family; widened to all cheating offences."),
    ] if with_issues else []
    return BailBrief(
        case_id=CASE,
        statutory_position=StatutoryPosition(sections=["BNS 318(4) (≈ IPC 420)"], bailable=False, max_punishment="7 years",
                                             rights="default-bail window closed; s.479 not yet reached (see RightsReport)"),
        grounds=[g1, g2, g3], open_issues=issues)


def uploaded_docs() -> list[DocumentEntry]:
    """The documents of the 14-page bundle of flow 1: FIR 1-3, two remand orders, the Sessions Court bail rejection."""
    return [
        DocumentEntry(doc_id="d1", type=DocumentType.FIR, pages=[1, 3], lang="hi"),
        DocumentEntry(doc_id="d2", type=DocumentType.REMAND_ORDER, pages=[4, 5], lang="en"),
        DocumentEntry(doc_id="d3", type=DocumentType.REMAND_ORDER, pages=[6, 7], lang="en"),
        DocumentEntry(doc_id="d4", type=DocumentType.BAIL_ORDER, pages=[8, 14], lang="en"),
    ]


def mentions_date(text: str, iso: str) -> bool:
    y, m, d = iso.split("-")
    return iso in text or f"{d}.{m}.{y}" in text or f"{d}/{m}/{y}" in text


def docx_text(path: str | Path) -> str:
    """All paragraph and table-cell text of a DOCX, in document order."""
    docx = pytest.importorskip("docx")
    doc = docx.Document(str(path))
    parts: list[str] = []
    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            parts.append("".join(t.text or "" for t in child.iter() if t.tag.endswith("}t")))
        elif tag == "tbl":
            for row in child.iter():
                if row.tag.endswith("}tr"):
                    parts.append(" | ".join("".join(t.text or "" for t in cell.iter() if t.tag.endswith("}t"))
                                            for cell in row if cell.tag.endswith("}tc")))
    for sec in doc.sections:  # banner and label may sit in header or footer
        parts += [p.text for p in sec.header.paragraphs] + [p.text for p in sec.footer.paragraphs]
    return "\n".join(parts)


def position_of(text: str, *words: str) -> int:
    """Offset of the first line that contains all `words` (case-insensitive); -1 if there is none."""
    offset = 0
    for line in text.splitlines(keepends=True):
        if all(w.lower() in line.lower() for w in words):
            return offset
        offset += len(line)
    return -1


class Spy:
    """Records which writers ran; each writes a small file where it is told to."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def application(self, brief, dossier, timeline, uploaded_docs, out_path, rights=None):  # RECONCILED: the exporter passes the case's RightsReport (design review item 7)
        self.calls.append("application")
        Path(out_path).write_bytes(b"docx")
        return out_path

    def card(self, brief, sparring, case_id):
        self.calls.append("card")
        return {"lead_with": ["G1"], "bench_concerns": [], "conditions": [], "open_issues": []}

    def pdf(self, docx_path):
        self.calls.append("pdf")
        out = str(Path(docx_path).with_suffix(".pdf"))
        Path(out).write_bytes(b"pdf")
        return out
