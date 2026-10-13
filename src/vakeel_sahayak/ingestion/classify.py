"""Document labelling and paragraph information tagging (plan §4.3 step 2)."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import DocumentType, InfoKind


def label_document(text: str, first_page_text: str | None = None) -> tuple[DocumentType, float]:
    """Label as FIR, arrest memo, remand order, bail order, order sheet, charge-sheet cover, custody certificate, medical record, affidavit or other.

    Args:
        text: see behaviour
        first_page_text: see behaviour

    Returns:
        (type, confidence).
    """
    raise NotImplementedError


def tag_paragraph(text: str) -> list[InfoKind]:
    """Tag by information kind: dated event, party, section, earlier outcome, custody, personal circumstance.

    Args:
        text: see behaviour

    Returns:
        InfoKinds.
    """
    raise NotImplementedError
