"""Pieces of the BailBrief that are rules over the dossier and the RightsReport, not model work (plan §8.1, §10).

The statutory position (sections, bailable, maximum punishment, a rights summary), the `depends_on` record of a claim
(the dossier fields it cites with the hash of each value, the timeline events behind them, Radar checks and
authority paragraphs), and the open issues counsel must clear (NEEDS_REVIEW, CHANGED_PROVISION, MISSING_EVIDENCE).
"""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.agents.vakeel.facts import EVENT_FIELDS, FACTOR_RIGHTS, value_hashes
from vakeel_sahayak.ingestion.events import field_of_label
from vakeel_sahayak.schemas.bail_brief import Authority, DependsOn, OpenIssue, StatutoryPosition
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import OpenIssueType, TransferFlag
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.store_rows import TimelineEvent

_YEARS = re.compile(r"(\d+)\s*(?:years?|yrs?)", re.IGNORECASE)
_DEFAULT_BAIL = {
    "WINDOW_CLOSED": "default-bail window closed",
    "ELIGIBLE": "default-bail window open (check the dates)",
    "NOT_YET": "default-bail window not yet reached",
    "CHECK": "default-bail: to be checked",
}
_UNDERTRIAL = {
    "ELIGIBLE": "s.479 threshold reached",
    "NOT_YET": "s.479 not yet reached",
    "CHECK": "s.479: to be checked",
}


def _years(text: str | None) -> int | None:
    if not text:
        return None
    if re.search(r"death", text, re.IGNORECASE):
        return 100
    if re.search(r"life", text, re.IGNORECASE):
        return 99
    found = [int(m) for m in _YEARS.findall(text)]
    return max(found) if found else None


def rights_summary(rights: RightsReport | None) -> str | None:
    """One line on the accused's entitlements, from the RightsReport only ('default-bail window closed; s.479 not yet reached (see RightsReport)')."""
    if rights is None or not rights.checks:
        return None
    parts: list[str] = []
    for check, table in (("default_bail", _DEFAULT_BAIL), ("undertrial_limit", _UNDERTRIAL)):
        res = rights.get(check)
        if res is not None:
            parts.append(table.get(res.status.value, f"{check.replace('_', ' ')}: {res.status.value.lower().replace('_', ' ')}"))
    bar = rights.get("statutory_bar")
    if bar is not None and bar.status.value in ("FLAG", "BAR_APPLIES"):
        parts.append("a statutory bar is flagged")
    antil = rights.get("antil_category")
    if antil is not None and antil.status.value in ("A", "B", "C", "D"):
        parts.append(f"Antil category {antil.status.value}")
    return ("; ".join(parts) + " (see RightsReport)") if parts else "see RightsReport"


def statutory_position(dossier: CaseDossier | None, rights: RightsReport | None, sections: list[dict[str, Any]] | None = None, rights_text: str | None = None) -> StatutoryPosition:
    """The statutory position block.

    Args:
        dossier: the approved dossier (its `sections` field), or None
        rights: the RightsReport, for the rights line
        sections: section rows `{ref, equivalent, bailable, max_punishment}` when there is no dossier (A1)
        rights_text: a ready rights line (A3: written by the model, as the rule tools are off); overrides the report
    """
    refs: list[str] = []
    bail: list[bool | None] = []
    longest: tuple[int, str] | None = None
    rows: list[tuple[str, str | None, bool | None, str | None]] = []
    tracked = dossier.fields.sections if dossier is not None else None
    if tracked is not None and tracked.value:
        for sv in tracked.value:
            base = f"{sv.code} {sv.section}".strip() if sv.code and sv.section else sv.as_written
            rows.append((base, sv.equivalent, sv.bailable, sv.max_punishment))
    for row in sections or []:
        rows.append((str(row.get("ref") or ""), row.get("equivalent"), row.get("bailable"), row.get("max_punishment")))
    for base, equivalent, bailable, punishment in rows:
        if not base:
            continue
        refs.append(f"{base} (≈ {equivalent})" if equivalent else base)
        bail.append(bailable)
        value = _years(punishment)
        if punishment and (longest is None or (value or 0) > longest[0]):
            longest = (value or 0, punishment)
    bailable: bool | None
    if any(b is False for b in bail):
        bailable = False
    elif bail and all(b is True for b in bail):
        bailable = True
    else:
        bailable = None
    return StatutoryPosition(sections=refs, bailable=bailable, max_punishment=longest[1] if longest else None, rights=rights_text or rights_summary(rights))


def events_behind(fields: list[str], timeline: list[TimelineEvent]) -> list[str]:
    """Ids of the timeline events that date the cited dossier fields (by the label's field, ingestion.events.field_of_label)."""
    wanted = {lf for f in fields for lf in EVENT_FIELDS.get(f, ())}
    out: list[str] = []
    for ev in timeline:
        if field_of_label(ev.label) in wanted and ev.event_id not in out:
            out.append(ev.event_id)
    return out


def depends_on(
    factor: str, fields: list[str], dossier: CaseDossier | None, facts_text: str | None, timeline: list[TimelineEvent],
    rights: RightsReport | None, authorities: list[Authority],
) -> DependsOn:
    """The `depends_on` of a claim: cited fields with their value hashes, their events, the Radar checks of the factor, the authority paragraphs."""
    hashes = value_hashes(fields, dossier, facts_text)
    checks = [c for c in FACTOR_RIGHTS.get(factor, ()) if rights is not None and rights.get(c) is not None]
    return DependsOn(facts=hashes, events=events_behind(list(hashes), timeline), rights=checks, authorities=[f"{a.doc_id}#{a.para}" for a in authorities])


def changed_provision_issue(doc_id: str, transfer: dict[str, Any] | None, case_refs: list[str]) -> OpenIssue:
    """'DLHC-2021-0420 interprets IPC 420; BNS 318(4) wording differs: qualify.'"""
    old = (transfer or {}).get("old_ref")
    new = (transfer or {}).get("new_ref") or (case_refs[0] if case_refs else "the charged provision")
    named = f" interprets {old};" if old else " construed an earlier provision;"
    return OpenIssue(type=OpenIssueType.CHANGED_PROVISION, item=f"{doc_id}{named} {new} wording differs: qualify.")


def is_changed(a: Authority) -> bool:
    return a.transfer == TransferFlag.CHANGED


def case_refs_of(dossier: CaseDossier | None, sections: list[dict[str, Any]] | None = None) -> list[str]:
    """The charged sections as written in the brief ('BNS 318(4)')."""
    out: list[str] = []
    tracked = dossier.fields.sections if dossier is not None else None
    for sv in (tracked.value or []) if tracked is not None else []:
        out.append(f"{sv.code} {sv.section}".strip() if sv.code and sv.section else sv.as_written)
    out += [str(r.get("ref")) for r in sections or [] if r.get("ref")]
    return out

