"""The objections sheet: Abhiyojak's objections, Vakeel's replies and the round-2 verdicts (plan §3.1 output, §9)."""

from __future__ import annotations

from vakeel_sahayak.export.docx_style import heading, new_document, paragraph, table
from vakeel_sahayak.schemas.bail_brief import DRAFT_LABEL
from vakeel_sahayak.schemas.sparring import SparringRecord


def _reply(o) -> str:  # noqa: ANN001 - an Objection
    if o.reply is None:
        return "No reply drafted: counsel to answer."
    cites = "; ".join(a.citation or f"{a.doc_id}, para {a.para}" for a in o.reply.authorities)
    return o.reply.text + (f" ({cites})" if cites else "")


def write_objections_docx(sparring: SparringRecord, case_id: str, out_path: str) -> str:
    """One row per objection: what it is against, the objection, the reply and Abhiyojak's verdict.

    Args:
        sparring: the sparring record at Gate 2
        case_id: the case
        out_path: where to write the file

    Returns:
        out_path.
    """
    doc = new_document(title=f"Objections sheet, {case_id}")
    heading(doc, "OBJECTIONS SHEET", size=14, space_before=0)
    paragraph(doc, f"Case {case_id}. Objections the prosecution is likely to raise, as found by sparring over {sparring.rounds} round(s), "
                   "with the drafted replies.", italic=True)
    if sparring.objections:
        rows = [[o.id, "General" if o.against == "general" else f"Ground {o.against}", o.objection, _reply(o),
                 (o.verdict.value.capitalize() if o.verdict is not None else "Not judged") + (f": {o.reason}" if o.reason else "")]
                for o in sparring.objections]  # fmt: skip
        table(doc, ["No.", "Against", "Objection", "Reply", "Verdict"], rows, widths_cm=[1.2, 2.0, 5.0, 5.5, 2.3])
    else:
        paragraph(doc, "Sparring raised no objection.", italic=True)
    paragraph(doc, DRAFT_LABEL, italic=True, align="center")
    doc.save(out_path)
    return out_path
