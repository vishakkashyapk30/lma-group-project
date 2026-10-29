"""Fill the python-docx application from the brief (plan §8.2).

The application is assembled, never generated: the grounds are the brief's text word for word, every date in the List of
Dates comes from `case.timeline` with its source, and the synopsis, brief facts and prayer are written from dossier fields
that are on record (VERIFIED, COMPUTED or edited by counsel; a USER_STATED fact keeps the per-counsel label). Real names
never enter the file: the cause title, verification and affidavit carry bracketed placeholders that counsel fills in on
their own machine. Authority markers are replaced by the citation text rendered from corpus metadata (plan §8.1).
"""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.agents.vakeel.facts import PER_COUNSEL
from vakeel_sahayak.export.docx_style import court_date, heading, new_document, paragraph, table
from vakeel_sahayak.export.list_of_dates import add_list_of_dates, build_list_of_dates
from vakeel_sahayak.export.rights import unverified_notes
from vakeel_sahayak.schemas.bail_brief import BailBrief, Ground
from vakeel_sahayak.schemas.common import TrackedField
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import ClaimCheck, ClaimState, DocumentType, FieldStatus
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.store_rows import TimelineEvent

HEADING = "Application under Section 483 BNSS for grant of regular bail"
SECTION_HEADINGS = {  # the heading line of each section after the cause title and the s.483 heading (order: export/sections.py)
    "synopsis": "SYNOPSIS",
    "list_of_dates_and_events": "LIST OF DATES AND EVENTS",
    "brief_facts": "BRIEF FACTS",
    "earlier_bail_applications": "EARLIER BAIL APPLICATIONS",
    "grounds": "GROUNDS",
    "statutory_position": "STATUTORY POSITION",
    "prayer": "PRAYER",
    "verification_and_affidavit": "VERIFICATION AND AFFIDAVIT",
    "annexure_index": "INDEX OF ANNEXURES",
}
SHOWETH = "MOST RESPECTFULLY SHOWETH:"
ON_RECORD = (FieldStatus.VERIFIED, FieldStatus.COMPUTED, FieldStatus.USER_EDITED)
LANGUAGES = {"en": "English", "hi": "Hindi", "mixed": "Hindi and English"}
_MARKER = re.compile(r"\[\s*(F|A)\s*:\s*([^\]]+?)\s*\]")


def _value(f: TrackedField[Any]) -> tuple[Any, bool]:
    """(value, stated_by_counsel) for a field that may be stated in the application; (None, False) otherwise."""
    if f.value in (None, [], ""):
        return None, False
    if f.status in ON_RECORD:
        return f.value, False
    if f.status == FieldStatus.USER_STATED:
        return f.value, True
    return None, False  # UNSUPPORTED and AMBIGUOUS values are for counsel to settle, not for the court


def _sections(dossier: CaseDossier) -> str:
    value, _ = _value(dossier.fields.sections)
    parts = [f"{s.as_written}" + (f" (corresponding to {s.equivalent})" if s.equivalent else "") for s in value or []]
    return ", ".join(parts)


def _fir(dossier: CaseDossier) -> str:
    fir, _ = _value(dossier.fields.fir)
    if fir is None or not fir.number:
        return "FIR No. [FIR NUMBER]"
    return f"FIR No. {fir.number}" + (f" dated {court_date(fir.date)}" if fir.date else "")


def render_ground(ground: Ground) -> str:
    """The ground's argument with `[F:...]` markers taken out and `[A:doc#para]` replaced by the rendered citation."""
    from vakeel_sahayak.tools.drafting.claims import parse_ref

    cites = {(a.doc_id, a.para): a.citation or f"{a.doc_id}, para {a.para}" for a in ground.authorities}

    def swap(m: re.Match[str]) -> str:
        if m.group(1) == "F":
            return ""
        try:
            _, doc_id, para = parse_ref(m.group(0))
        except ValueError:
            return ""
        return f" ({cites.get((doc_id, para or 0), f'{doc_id}, para {para}')})"

    text = _MARKER.sub(swap, ground.argument)
    text = re.sub(r"\s+([.,;:!?])", r"\1", re.sub(r"\s+", " ", text)).strip()
    cited = {(d, p) for d, p in cites if f"{d}#{p}" in ground.argument.replace(" ", "")}
    extra = [c for k, c in cites.items() if k not in cited]
    if extra:
        text += f" Reliance is placed on {'; '.join(extra)}."
    return text


def _ground_flags(ground: Ground) -> str:
    """Visible marks for counsel on a ground that is not settled; nothing is dropped silently (plan §8.1)."""
    flags = []
    if ground.check == ClaimCheck.NEEDS_REVIEW:
        flags.append("[NEEDS REVIEW: COUNSEL TO VERIFY THIS GROUND BEFORE FILING]")
    if ground.state != ClaimState.CURRENT:
        flags.append(f"[{ground.state.value}: REDRAFT PENDING AFTER A CHANGE IN THE RECORD]")
    return " ".join(flags)


def _cause_title(doc: Any, dossier: CaseDossier) -> None:
    court = (dossier.court or "").strip()
    m = re.fullmatch(r"(.+?)\s+High Court", court, re.IGNORECASE)
    title = f"IN THE HIGH COURT OF {m.group(1).upper()}" if m else (f"IN THE {court.upper()}" if court else "IN THE HIGH COURT OF [STATE]")
    heading(doc, f"{title} AT [PLACE]", size=13, space_before=0)
    paragraph(doc, "CRIMINAL MISCELLANEOUS (BAIL) APPLICATION NO. [NUMBER] OF [YEAR]", bold=True, align="center")
    paragraph(doc, "IN THE MATTER OF:", bold=True, justify=False)
    paragraph(doc, "[APPLICANT NAME], [PARENTAGE], [ADDRESS]          ... Applicant", justify=False)
    paragraph(doc, "VERSUS", bold=True, align="center")
    paragraph(doc, "[STATE / RESPONDENT]          ... Respondent", justify=False)
    sections = _sections(dossier)
    paragraph(doc, f"{_fir(dossier)}, Police Station [POLICE STATION]" + (f", under Section(s) {sections}" if sections else ""), align="center")


def _synopsis(dossier: CaseDossier) -> list[str]:
    f = dossier.fields
    out: list[str] = []
    arrest, _ = _value(f.arrest_date)
    sections = _sections(dossier)
    lead = "The applicant" + (f" has been in custody since {court_date(arrest)}" if arrest else " is in custody")
    out.append(f"{lead} in connection with {_fir(dossier)}" + (f", registered under Section(s) {sections}." if sections else "."))
    days, _ = _value(f.custody_days)
    if days is not None:
        out.append(f"As on {court_date(dossier.as_of)}, the applicant has spent {days} days in custody." if dossier.as_of else f"The applicant has spent {days} days in custody.")
    cs, _ = _value(f.charge_sheet)
    if cs is not None:
        out.append(f"The charge sheet was filed on {court_date(cs.date)}." if cs.filed and cs.date else ("The charge sheet has been filed." if cs.filed else "The charge sheet has not yet been filed."))
    stage, by_counsel = _value(f.trial_stage)
    if stage:
        out.append(f"Present stage of the trial: {stage}" + (f" ({PER_COUNSEL})." if by_counsel else "."))
    co, by_counsel = _value(f.co_accused_bail)
    for c in co or []:
        if c.outcome.lower().startswith("grant"):
            out.append(f"{c.id} has been granted bail" + (f" on {court_date(c.date)}" if c.date else "") + (f" ({PER_COUNSEL})." if by_counsel else "."))
    prev, _ = _value(f.previous_bail)
    for p in prev or []:
        out.append(f"The {p.court} {p.outcome} the applicant's bail application on {court_date(p.date)}.")
    out.append("The applicant seeks regular bail under Section 483 BNSS.")
    return out


def _brief_facts(dossier: CaseDossier, timeline: list[TimelineEvent]) -> list[str]:
    out = [f"That on {court_date(r['date'])}: {r['event']}" + (f" ({r['source']})." if r["source"] else ".") for r in build_list_of_dates(timeline)]
    stage, by_counsel = _value(dossier.fields.trial_stage)
    if stage:
        out.append(f"That the present stage of the trial is: {stage}" + (f" ({PER_COUNSEL})." if by_counsel else "."))
    personal, by_counsel = _value(dossier.fields.personal)
    if personal:
        out.append("That the applicant's personal circumstances are: " + "; ".join(personal) + (f" ({PER_COUNSEL})." if by_counsel else "."))
    antecedents, by_counsel = _value(dossier.fields.antecedents)
    if antecedents:
        out.append("That as to antecedents: " + "; ".join(antecedents) + (f" ({PER_COUNSEL})." if by_counsel else "."))
    return out or ["[COUNSEL TO STATE THE FACTS OF THE CASE]"]


def _earlier_applications(dossier: CaseDossier) -> list[str]:
    field = dossier.fields.previous_bail
    prev, by_counsel = _value(field)
    if prev:
        rows = [f"{i}. {p.court}, order dated {court_date(p.date)}: application {p.outcome}" + (f" ({PER_COUNSEL})." if by_counsel else ".") for i, p in enumerate(prev, 1)]
        return rows + ["Apart from the above, no bail application has been filed by the applicant in this matter before any court."]
    if field.status in ON_RECORD:
        return ["No bail application has been filed by the applicant in this matter before any court."]
    return ["[COUNSEL TO DISCLOSE EVERY EARLIER BAIL APPLICATION AND ITS OUTCOME, OR STATE THAT NONE WAS FILED]"]


def _statutory_position(brief: BailBrief, dossier: CaseDossier, rights: RightsReport | None = None) -> list[str]:
    sp = brief.statutory_position
    out = []
    sections = ", ".join(sp.sections) or _sections(dossier)
    if sections:
        out.append(f"Section(s) charged: {sections}.")
    if sp.bailable is not None:
        out.append(f"Nature of the offence: {'bailable' if sp.bailable else 'non-bailable'}.")
    if sp.max_punishment:
        out.append(f"Maximum punishment: {sp.max_punishment}.")
    if sp.rights:
        out.append(f"Procedural rights: {sp.rights}.".replace("..", "."))
    out += unverified_notes(rights)
    return out or ["[COUNSEL TO STATE THE STATUTORY POSITION]"]


def _annexure_rows(uploaded_docs: list[DocumentEntry]) -> list[list[str]]:
    rows = []
    for i, d in enumerate(sorted(uploaded_docs, key=lambda d: (d.pages[0] if d.pages else 0, d.doc_id)), 1):
        kind = "FIR" if d.type == DocumentType.FIR else d.type.value.replace("_", " ").capitalize()
        first, last = (d.pages[0], d.pages[-1]) if d.pages else (None, None)
        pages = "" if first is None else (f"{first}" if first == last else f"{first}–{last}")
        rows.append([f"A-{i}", f"{kind} ({d.doc_id})", LANGUAGES.get(d.lang, d.lang), pages])
    return rows


def assemble_application_docx(
    brief: BailBrief,
    dossier: CaseDossier,
    timeline: list[TimelineEvent],
    uploaded_docs: list[DocumentEntry],
    out_path: str,
    rights: RightsReport | None = None,
) -> str:
    """Build the application: cause title (placeholders), s.483 BNSS heading, synopsis, List of Dates, brief facts, earlier bail applications, numbered grounds, statutory position, prayer, verification and affidavit placeholders, annexure index (plan §8.2). Banner: AI-generated draft: check against your court's rules.

    Args:
        brief: Vakeel's brief; grounds are copied word for word, markers rendered
        dossier: the approved dossier; only fields on record are stated
        timeline: `case.timeline`, the only source of the List of Dates
        uploaded_docs: documents Munshi found in the uploaded files, one annexure each
        out_path: where to write the DOCX
        rights: the case's RightsReport; each rule not yet checked against the bare act gets a bracketed note under the statutory position

    Returns:
        Path of the DOCX.
    """
    doc = new_document(title=f"Bail application, {brief.case_id}")
    _cause_title(doc, dossier)
    heading(doc, HEADING, size=13)
    paragraph(doc, brief.label, italic=True, align="center")

    heading(doc, SECTION_HEADINGS["synopsis"])
    paragraph(doc, " ".join(_synopsis(dossier)))

    heading(doc, SECTION_HEADINGS["list_of_dates_and_events"])
    add_list_of_dates(doc, build_list_of_dates(timeline))

    heading(doc, SECTION_HEADINGS["brief_facts"])
    paragraph(doc, SHOWETH, bold=True, justify=False)
    for n, text in enumerate(_brief_facts(dossier, timeline), 1):
        paragraph(doc, f"{n}. {text}", indent_cm=0.8, hanging_cm=0.8)

    heading(doc, SECTION_HEADINGS["earlier_bail_applications"])
    for text in _earlier_applications(dossier):
        paragraph(doc, text)

    heading(doc, SECTION_HEADINGS["grounds"])
    if brief.grounds:
        for n, g in enumerate(brief.grounds, 1):
            flags = _ground_flags(g)
            paragraph(doc, f"{n}. {render_ground(g)}" + (f" {flags}" if flags else ""), indent_cm=0.8, hanging_cm=0.8)
    else:
        paragraph(doc, "[NO GROUND HAS BEEN DRAFTED: COUNSEL TO ADD THE GROUNDS]")

    heading(doc, SECTION_HEADINGS["statutory_position"])
    for text in _statutory_position(brief, dossier, rights):
        paragraph(doc, text)

    heading(doc, SECTION_HEADINGS["prayer"])
    paragraph(doc, "In view of the facts and grounds stated above, it is most respectfully prayed that this Hon'ble Court may be pleased to:")
    paragraph(doc, f"(a) release the applicant on regular bail in {_fir(dossier)}, on such terms and conditions as this Hon'ble Court may deem fit; and", indent_cm=0.8)
    paragraph(doc, "(b) pass any other order that this Hon'ble Court may deem fit and proper in the facts and circumstances of the case.", indent_cm=0.8)
    paragraph(doc, "Filed by: [COUNSEL NAME], Advocate for the Applicant, [ENROLMENT NUMBER]. Place: [PLACE]. Date: [DATE].", justify=False)

    heading(doc, SECTION_HEADINGS["verification_and_affidavit"])
    paragraph(doc, "Verification. Verified at [PLACE] on [DATE] that the contents of this application are true and correct to the "
                   "knowledge of the deponent, derived from the records of the case, and that nothing material has been concealed.")
    paragraph(doc, "[DEPONENT NAME]", align="right")
    paragraph(doc, "Affidavit. I, [DEPONENT NAME], [RELATIONSHIP TO THE APPLICANT], aged about [AGE] years, resident of [ADDRESS], "
                   "do hereby solemnly affirm and declare that the contents of the accompanying application have been read over to me, "
                   "that they are true and correct to my knowledge and belief, and that no part of it is false.")
    paragraph(doc, "[DEPONENT SIGNATURE]", align="right")

    heading(doc, SECTION_HEADINGS["annexure_index"])
    rows = _annexure_rows(uploaded_docs)
    if rows:
        table(doc, ["No.", "Document", "Language", "Pages"], rows, widths_cm=[1.8, 8.0, 3.2, 3.0])
    else:
        paragraph(doc, "No documents were uploaded with this case.", italic=True)

    doc.save(out_path)
    return out_path
