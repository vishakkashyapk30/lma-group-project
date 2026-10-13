"""Fill the python-docx application template from the brief (plan §8.2). The model writes only synopsis, brief facts and prayer."""

from __future__ import annotations

from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry
from vakeel_sahayak.schemas.store_rows import TimelineEvent


def assemble_application_docx(
    brief: BailBrief,
    dossier: CaseDossier,
    timeline: list[TimelineEvent],
    uploaded_docs: list[DocumentEntry],
    out_path: str,
) -> str:
    """Build the application: cause title (placeholders), s.483 BNSS heading, synopsis, List of Dates, brief facts, earlier bail applications, numbered grounds, statutory position, prayer, verification and affidavit placeholders, annexure index (plan §8.2). Banner: AI-generated draft: check against your court's rules.

    Args:
        brief: see behaviour
        dossier: see behaviour
        timeline: see behaviour
        uploaded_docs: see behaviour
        out_path: see behaviour

    Returns:
        Path of the DOCX.
    """
    raise NotImplementedError
