"""One-page hearing-prep card (plan §8.3). No outcome prediction, no grant rates.

The content is Vakeel's card data (`agents/vakeel/hearing.build_card`), computed from the brief, the sparring record and the
evidence packs Sutradhar wrote to the case's event log, so the export shows what was actually retrieved and never searches
again. On the exported card every bench concern points at a ground and an authority; a concern that has neither (a general
objection with no ground) is left to the open issues, where an unanswered one already appears.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from vakeel_sahayak.agents.vakeel.hearing import MAX_CONDITIONS, build_card
from vakeel_sahayak.export.docx_style import heading, new_document, paragraph, table
from vakeel_sahayak.schemas.bail_brief import DRAFT_LABEL, BailBrief
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack
from vakeel_sahayak.schemas.sparring import SparringRecord

MAX_CONCERNS = 6


def recorded_packs(case_id: str) -> list[EvidencePack]:
    """The latest evidence packs Sutradhar wrote to this case's event log (empty before retrieval ran)."""
    from vakeel_sahayak.record import views
    from vakeel_sahayak.tools.runtime import get_runtime

    raw = views._latest(get_runtime().event_log(case_id).read(case_id), "evidence_packs") or []
    packs = []
    for item in raw if isinstance(raw, list) else []:
        try:
            packs.append(EvidencePack.model_validate(item))
        except ValidationError:
            continue
    return packs


def _pointer(authority: str | None, ground_id: str, brief: BailBrief) -> str | None:
    """The concern's authority with its paragraph named, so counsel can find it ('..., para 14' or 'doc#para')."""
    if not authority:
        return None
    if "#" in authority or "para" in authority.lower():
        return authority
    ground = next((g for g in brief.grounds if g.id == ground_id), None)
    first = ground.authorities[0] if ground is not None and ground.authorities else None
    return f"{authority}, para {first.para}" if first is not None else None


def build_hearing_card(brief: BailBrief, sparring: SparringRecord, case_id: str) -> dict[str, Any]:
    """Likely bench concerns (caselaw.similar and same-section-family reasoning), three points to lead with, conditions courts impose in similar grants, open issues.

    Args:
        brief: the brief at Gate 2
        sparring: Abhiyojak's record (answered objections become concerns, unanswered ones open issues)
        case_id: the case whose recorded evidence packs supply comparable reasoning and conditions

    Returns:
        Card content: case_id, label, bench_concerns ({factor, concern, answer, ground, authority, source}), lead_with
        (ground ids), lead_points, conditions (texts), condition_sources, open_issues (texts).
    """
    citations = {(a.doc_id, a.para): a.citation for g in brief.grounds for a in g.authorities if a.citation}
    card = build_card(brief, recorded_packs(case_id), sparring, citations)
    concerns = []
    for c in card["bench_concerns"]:
        pointer = _pointer(c.get("authority"), str(c.get("ground")), brief) if c.get("ground") else None
        if pointer and c.get("answer"):
            concerns.append({**c, "authority": pointer})
    card["bench_concerns"] = concerns[:MAX_CONCERNS]
    card["conditions"] = card["conditions"][:MAX_CONDITIONS]
    return card


def write_hearing_card_docx(card: dict[str, Any], case_id: str, out_path: str) -> str:
    """The card as a one-page DOCX: points to lead with, likely concerns, conditions, open issues.

    Args:
        card: `build_hearing_card` output (missing blocks are shown as empty)
        case_id: the case
        out_path: where to write the file

    Returns:
        out_path.
    """
    doc = new_document(title=f"Hearing-prep card, {case_id}")
    heading(doc, "HEARING-PREP CARD", size=14, space_before=0)
    paragraph(doc, f"Case {case_id}. For counsel's preparation only; this card says nothing about how the hearing will go.", italic=True, align="center")

    heading(doc, "Points to lead with")
    points = card.get("lead_points") or [{"ground": g, "point": ""} for g in card.get("lead_with", [])]
    for n, p in enumerate(points, 1):
        paragraph(doc, f"{n}. Ground {p['ground']}" + (f": {p['point']}" if p.get("point") else ""), indent_cm=0.8, hanging_cm=0.8)
    if not points:
        paragraph(doc, "No ground passed every check: see the open issues.", italic=True)

    heading(doc, "Likely concerns from the bench")
    concerns = card.get("bench_concerns", [])
    if concerns:
        rows = [[c.get("concern") or str(c.get("factor", "")).replace("_", " "), c["answer"], f"Ground {c['ground']}; {c['authority']}"] for c in concerns]
        table(doc, ["Concern", "Short answer", "Where it is argued"], rows, widths_cm=[5.0, 6.5, 4.5])
    else:
        paragraph(doc, "No concern was found in the comparable orders or the sparring record.", italic=True)

    heading(doc, "Conditions courts often impose in similar grants")
    conditions = card.get("conditions", [])
    for c in conditions:
        paragraph(doc, f"• {c}", indent_cm=0.8, hanging_cm=0.4, justify=False)
    if not conditions:
        paragraph(doc, "None recorded in the retrieved orders.", italic=True)

    heading(doc, "Open issues to clear before the hearing")
    issues = card.get("open_issues", [])
    for i in issues:
        paragraph(doc, f"• {i}", indent_cm=0.8, hanging_cm=0.4, justify=False)
    if not issues:
        paragraph(doc, "None.", italic=True)

    paragraph(doc, card.get("label") or DRAFT_LABEL, italic=True, align="center")
    doc.save(out_path)
    return out_path
