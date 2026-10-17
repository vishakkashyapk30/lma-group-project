"""Fixed filter-relaxation order: factor, then section family, then court (plan §6.2 step 2.4).

`relax(args, step)` drops or widens exactly one filter of a search call and never touches the others; the agent chains
the steps (0, 1, 2) one round at a time, so the order is fixed and every round says which filter it gave up. Widening
the section family goes to the offence group when the sections are in one ("BNS 318(4)" and "IPC 420" -> all cheating
offences), else the filter is dropped.
"""

from __future__ import annotations

import re
from typing import Any

RELAXATION_ORDER: list[str] = ["factor", "section_family", "court"]

# Offence groups by (code, first section, last section); used to widen a section family and to word the open issue.
_RANGES: dict[str, list[tuple[str, int, int]]] = {
    "cheating": [("IPC", 415, 420), ("BNS", 318, 318)],
    "theft": [("IPC", 378, 382), ("BNS", 303, 306)],
    "extortion": [("IPC", 383, 389), ("BNS", 308, 308)],
    "robbery and dacoity": [("IPC", 390, 402), ("BNS", 309, 313)],
    "criminal breach of trust": [("IPC", 405, 409), ("BNS", 314, 316)],
    "forgery": [("IPC", 463, 471), ("BNS", 336, 340)],
    "homicide": [("IPC", 299, 304), ("BNS", 100, 105)],
    "hurt": [("IPC", 319, 338), ("BNS", 114, 125)],
    "sexual offences": [("IPC", 375, 376), ("BNS", 63, 71)],
    "cruelty to a married woman": [("IPC", 498, 498), ("BNS", 85, 86)],
}
_REF = re.compile(r"^\s*([A-Za-z\.]+)\s+(\d+)")
_SUBSECTIONS = {("BNS", 318): 5, ("BNS", 316): 5, ("BNS", 303): 5, ("BNS", 308): 5}


def _parse(ref: str) -> tuple[str, int] | None:
    m = _REF.match(str(ref))
    return (m.group(1).upper().replace(".", ""), int(m.group(2))) if m else None


def offence_group(section_family: list[str] | None) -> str | None:
    """The offence group ('cheating', 'theft', ...) the first matching section of a family belongs to, else None."""
    for ref in section_family or []:
        parsed = _parse(ref)
        if parsed is None:
            continue
        code, number = parsed
        for name, ranges in _RANGES.items():
            if any(code == c and lo <= number <= hi for c, lo, hi in ranges):
                return name
    return None


def group_members(name: str) -> list[str]:
    """Section references of an offence group, in both codes ('IPC 415' ... 'BNS 318', 'BNS 318(1)' ...)."""
    out: list[str] = []
    for code, lo, hi in _RANGES.get(name, []):
        for n in range(lo, hi + 1):
            out.append(f"{code} {n}")
            out.extend(f"{code} {n}({i})" for i in range(1, _SUBSECTIONS.get((code, n), 0) + 1))
    return out


def relax(args: dict[str, Any], step: int) -> dict[str, Any]:
    """Give up filters in the fixed order, up to and including step `step` (cumulative).

    Step 0 drops the factor filter. Step 1 also widens the section family to its offence group (a superset of the family;
    dropped altogether when the sections belong to no group; for a case-document search the document-type filter goes too).
    Step 2 also drops the court filter. Past step 2 nothing more can be relaxed, so the result is that of step 2. The other
    arguments (above all `before`, the case date, which is never relaxed) are left as they are, a step with nothing to
    relax changes nothing, and the caller's dict is never modified.

    Args:
        args: the call's arguments
        step: index into `RELAXATION_ORDER`; negative relaxes nothing

    Returns:
        New args.
    """
    new = {k: (list(v) if isinstance(v, list) else v) for k, v in args.items()}
    for i in range(min(step, len(RELAXATION_ORDER) - 1) + 1):
        name = RELAXATION_ORDER[i]
        if name == "factor":
            new.pop("factor", None)
        elif name == "section_family":
            family = new.get("section_family")
            if family:
                group = offence_group(family)
                widened = sorted(set(family) | set(group_members(group))) if group else None
                if widened and set(widened) != set(family):
                    new["section_family"] = widened
                else:
                    new.pop("section_family", None)
            new.pop("doc_types", None)
        else:
            new.pop("court", None)
    return new


def describe(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """What a relaxation gave up, in words for the trace and for the open issue ('widened to all cheating offences')."""
    said: list[str] = []
    if "factor" in before and "factor" not in after:
        said.append("factor filter dropped")
    fam_before, fam_after = before.get("section_family"), after.get("section_family")
    if fam_before and fam_before != fam_after:
        group = offence_group(fam_before)
        said.append(f"widened to all {group} offences" if fam_after and group else "widened to all sections")
    if before.get("doc_types") and not after.get("doc_types"):
        said.append("document-type filter dropped")
    if "court" in before and "court" not in after:
        said.append("court filter dropped")
    return said
