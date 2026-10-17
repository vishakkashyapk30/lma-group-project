"""Rule checks that assess a slot: court reasoning, factor tag, section-family overlap, date before the case (plan §6.2 step 2.3).

The checks are rules, not a model: a paragraph counts toward an authority slot only if it is court reasoning (never a
submission), carries the factor's tag, shares a section with the case's section family, and is dated before the case.
When Sutradhar has relaxed a filter, the check that filter stands for is not applied (a widened search would otherwise
reject its own results); the agent says in the slot's note what was widened. Case-document, timeline and fact slots
need a result that mentions what the slot is about.
"""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.schemas.enums import Factor, SlotStatus
from vakeel_sahayak.schemas.retrieval_plan import SlotResult

REASONING = "reasoning"
# Slots filled from submissions: the part a paragraph must be in (everything else must be court reasoning).
SUBMISSION_SLOTS: dict[str, str] = {"likely_objection": "prosecution_submissions", "argument_patterns": "defense_submissions"}
KNOWN_GOOD_LAW = {"OK", "OVERRULED", "DISTINGUISHED"}
SOFT = "~"  # marks a reason that keeps the item as weak support instead of rejecting it (another offence family)
# What a case-store result must mention to count for the slot (case-insensitive substrings).
SLOT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "co_accused_order": ("co-accused", "co accused", "bail"),
    "role_comparison": ("role", "co-accused", "co accused", "accused"),
    "charge_sheet_date": ("charge sheet", "chargesheet", "charge-sheet", "final report"),
    "trial_stage": ("trial", "charge", "framed", "witness", "evidence", "investigation"),
    "witness_examination": ("witness", "examined", "pw-", "pw "),
    "fir_allegations": ("fir", "allege", "complaint", "information"),
    "custody_days": ("arrest", "custody", "remand"),
}
# When the factor filter has been given up, a paragraph with no factor tag still counts if its text is about the factor.
FACTOR_TERMS: dict[str, tuple[str, ...]] = {
    "gravity_and_punishment": ("gravity", "serious", "punish", "severity", "heinous", "grave"),
    "custody_period": ("custody", "incarcerat", "detention", "detained", "jail", "undertrial"),
    "charge_sheet_filed": ("charge sheet", "chargesheet", "charge-sheet", "investigation", "interrogation", "final report"),
    "trial_delay": ("delay", "speedy", "article 21", "languish", "expedit", "conclusion of trial"),
    "parity_with_co_accused": ("parity", "co-accused", "co accused", "similarly placed", "same role", "identical role"),
    "antecedents": ("antecedent", "criminal history", "previous case", "pending case", "other case"),
    "flight_risk": ("flight", "abscond", "roots", "surrender", "passport", "presence of the accused"),
    "witness_tampering": ("witness", "tamper", "influence", "intimidat"),
    "weak_prima_facie": ("prima facie", "allegation", "mini trial", "mini-trial"),
    "health_age_family": ("health", "illness", "medical", "infirm", "sick", "disease", "woman", "women", "aged", "elderly"),
    "statutory_bar": ("twin condition", "section 37", "43d", "section 45", "reasonable grounds", "statutory bar", "special act"),
    "undertrial_period": ("undertrial", "479", "436a", "one-third", "one third", "first offender", "first-time"),
}
_TEXT_KEYS = ("text", "text_en", "label", "quote", "value", "detail")
_BASE = re.compile(r"\([^)]*\)")


def _base(ref: str) -> str:
    return re.sub(r"\s+", " ", _BASE.sub("", str(ref))).strip().upper()


def _family_overlap(item_family: list[str], family: list[str]) -> bool:
    exact = {re.sub(r"\s+", " ", str(r)).strip().upper() for r in family}
    if any(re.sub(r"\s+", " ", str(r)).strip().upper() in exact for r in item_family):
        return True
    bases = {_base(r) for r in family}
    return any(_base(r) in bases for r in item_family)


def _blob(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(k)) for k in _TEXT_KEYS if item.get(k) is not None).lower()


def _part_of(item: dict[str, Any]) -> str:
    return str(getattr(item.get("part"), "value", item.get("part")))


def _check_item(
    slot: str, item: dict[str, Any], case_date: str, factor: Factor, family: list[str], relaxed: tuple[str, ...], keywords: tuple[str, ...]
) -> str | None:
    """None when the item counts for the slot, else the reason it does not."""
    if slot == "good_law":
        return None if str(item.get("status") or item.get("good_law") or "").upper() in KNOWN_GOOD_LAW else "good-law status unknown"
    if slot == "sc_root":
        return None if item.get("sc_root") else "no Supreme Court root in the citation graph"
    if item.get("via"):  # reached through the citation graph (the SC root of an authority): found by identity, not by tag or family
        relaxed = tuple(relaxed) + ("factor", "section_family")
    corpus = "chunk_id" not in item and "event_id" not in item and ("court" in item or "para" in item or "doc_id" in item)
    if corpus:
        if "part" in item:
            part, wanted = _part_of(item), SUBMISSION_SLOTS.get(slot)
            if wanted is None and part != REASONING:
                return f"not court reasoning ({part})"
            if wanted is not None and part != wanted:
                return f"not a {wanted.split('_')[0]} submission ({part})"
        if case_date and item.get("date") and str(item["date"]) >= str(case_date):
            return f"dated {item['date']}, not before the case ({case_date})"
        if "factor" not in relaxed and "factors" in item:
            tags = {str(getattr(f, "value", f)) for f in item.get("factors") or []}
            if Factor(factor).value not in tags:
                return f"not tagged {Factor(factor).value}"
        if "factor" in relaxed and "plain" not in relaxed and not item.get("via") and "factors" in item and Factor(factor).value not in {str(getattr(f, "value", f)) for f in item.get("factors") or []}:
            text = str(item.get("text") or "").lower()
            if not any(t in text for t in FACTOR_TERMS.get(Factor(factor).value, ())):
                return f"untagged and not about {Factor(factor).value.replace('_', ' ')}"
        if "section_family" not in relaxed and family and "section_family" in item and not _family_overlap(item.get("section_family") or [], family):
            return SOFT + "no section in the case's section family"
        return None
    if keywords and ("chunk_id" in item or "event_id" in item) and not any(k in _blob(item) for k in keywords):
        return f"does not mention {slot.replace('_', ' ')}"
    return None


def assess_slot(
    slot: str,
    items: list[dict[str, Any]],
    need: str | int,
    case_date: str,
    factor: Factor,
    section_family: list[str],
    *,
    relaxed: tuple[str, ...] = (),
    keywords: tuple[str, ...] | None = None,
) -> SlotResult:
    """Return FILLED, WEAK or MISSING with a reason.

    FILLED when at least `need` items pass the rule checks (1 for 'required'; an 'optional' slot is FILLED by any
    passing item); WEAK when some pass but fewer than needed (the note says '1 of 2'), or when the only candidates are
    otherwise good paragraphs of another offence family (kept, flagged `outside_family`); MISSING when nothing usable
    came back. A FILLED result carries the passing items; a WEAK one also the outside-family paragraphs; the note lists
    why the others were rejected.

    Args:
        slot: slot name of the contract (`likely_objection` and `argument_patterns` are the submission slots)
        items: raw results of the slot as dicts (paragraph records, case chunks, timeline events, facts, citation rows)
        need: 'required', 'optional' or the number of items needed
        case_date: the case's order date; corpus items dated on or after it are rejected (leakage rule, plan §2)
        factor: the factor the slot serves
        section_family: the case's section references ('BNS 318(4)', 'IPC 420'); empty skips the overlap check
        relaxed: filters already given up ('factor', 'section_family', 'court'); their checks are skipped
        keywords: override of what a case-store result must mention (default: `SLOT_KEYWORDS[slot]`)

    Returns:
        SlotResult.
    """
    from vakeel_sahayak.agents.sutradhar.contracts_runtime import required_count

    want = required_count(need)
    kw = tuple(keywords) if keywords is not None else SLOT_KEYWORDS.get(slot, ())
    good: list[dict[str, Any]] = []
    soft: list[dict[str, Any]] = []
    why: dict[str, int] = {}
    seen: set[str] = set()
    for item in items:
        key = f"{item.get('doc_id')}#{item.get('para')}" if item.get("para") is not None else repr(sorted((k, str(v)) for k, v in item.items()))[:300]
        if key in seen:
            continue
        seen.add(key)
        reason = _check_item(slot, item, case_date, factor, list(section_family or []), tuple(relaxed), kw)
        if reason is None:
            good.append(item)
        elif reason.startswith(SOFT):  # a good paragraph from another offence family: weak support, never FILLED, not discarded
            soft.append({**item, "outside_family": True})
            why[reason[len(SOFT) :]] = why.get(reason[len(SOFT) :], 0) + 1
        else:
            why[reason] = why.get(reason, 0) + 1
    rejected = "; ".join(f"{n} {r}" for r, n in why.items())
    tag = Factor(factor).value
    good.sort(key=lambda i: 0 if tag in {str(getattr(f, "value", f)) for f in i.get("factors") or []} else 1)  # tagged first, stable
    n = len(good)
    if n == 0 and not soft:
        note = "no results" if not items else f"all {len(items)} result(s) rejected: {rejected}"
        return SlotResult(slot=slot, status=SlotStatus.MISSING, items=[], note=note)
    if want == 0 and n == 0:
        return SlotResult(slot=slot, status=SlotStatus.MISSING, items=[], note=f"only weak support: {rejected}")
    if n >= max(want, 1):
        return SlotResult(slot=slot, status=SlotStatus.FILLED, items=good, note=(f"{n} passed; rejected {rejected}" if rejected else None))
    note = f"{n} of {max(want, 1)}" + (f"; rejected {rejected}" if rejected else "")
    return SlotResult(slot=slot, status=SlotStatus.WEAK, items=good + soft, note=note)
