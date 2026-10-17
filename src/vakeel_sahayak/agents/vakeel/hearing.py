"""Hearing-prep card data (plan §8.3), as plain data; the one-page rendering is Phase 5.

- **concerns from the bench** (`bench_concerns`): the factors that come up most in the retrieved comparable reasoning (paragraphs
  tagged with the factor, recorded State objections), the factors Sutradhar marked adverse and the objections Abhiyojak
  raised, each with a short answer that points at a ground and an authority;
- **three points to lead with**: the strongest SUPPORTED grounds (REPAIRED ones only if fewer than three are SUPPORTED);
- **conditions courts often impose** in similar grants, read off the retrieved paragraphs (passport, staying in the
  city, appearing on every date, the size of the personal bond, not influencing witnesses), each with its source;
- **open issues** to clear before the hearing.

The card says nothing about how a hearing will go and carries no figures about orders (plan §8.3, §16).
"""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.agents.vakeel.claims import split_claim
from vakeel_sahayak.schemas.bail_brief import DRAFT_LABEL, BailBrief, Ground
from vakeel_sahayak.schemas.enums import ClaimCheck, Factor, FactorStance
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack
from vakeel_sahayak.schemas.sparring import SparringRecord

MAX_CONCERNS = 5
MAX_CONDITIONS = 6
LEAD_POINTS = 3
CONDITION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Surrender of passport", re.compile(r"surrender\w*\s+(?:his\s+|her\s+|the\s+)?passport", re.IGNORECASE)),
    ("Not to leave the city or country without the court's permission", re.compile(r"not\s+(?:to\s+)?leave\s+(?:the\s+)?(?:city|country|jurisdiction|state|india)", re.IGNORECASE)),
    ("Appear on every date of hearing", re.compile(r"appear\w*\s+(?:before\s+[^.]{0,40}?)?(?:on\s+)?(?:every|each)\s+(?:date|hearing)", re.IGNORECASE)),
    ("Not to influence witnesses or tamper with evidence", re.compile(r"(?:not\s+(?:to\s+)?)?(?:tamper\w*\s+with\s+(?:the\s+)?evidence|influence\s+(?:the\s+)?witness\w*)", re.IGNORECASE)),
)
_BOND = re.compile(r"personal\s+bond\s+(?:in\s+the\s+sum\s+)?of\s+(?:Rs\.?|₹|INR)\s*([\d,]+)(?:/-)?", re.IGNORECASE)


def factor_label(factor: str) -> str:
    return str(factor).replace("_", " ")


def first_sentence(text: str) -> str:
    """The first sentence of a claim with its markers, the label and notes removed (the short answer on the card)."""
    for s in split_claim(text):
        if not s.is_note and s.readable:
            return s.readable.rstrip(".") + "."
    return ""


def _items(pack: EvidencePack, *slots: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sl in pack.slots:
        if not slots or sl.slot in slots:
            out += [i for i in sl.items if isinstance(i, dict)]
    return out


def _doc_ref(item: dict[str, Any]) -> str | None:
    return f"{item['doc_id']}#{item['para']}" if item.get("doc_id") and item.get("para") is not None else None


def conditions_from(packs: list[EvidencePack]) -> list[dict[str, Any]]:
    """Conditions the retrieved paragraphs record, each with the paragraph it came from (no outcomes, no rates)."""
    found: dict[str, dict[str, Any]] = {}
    for pack in packs:
        for item in _items(pack):
            text, ref = str(item.get("text") or ""), _doc_ref(item)
            if not text or not ref:
                continue
            for name, pattern in CONDITION_PATTERNS:
                if pattern.search(text) and name not in found:
                    found[name] = {"condition": name, "source": ref}
            if m := _BOND.search(text):
                name = f"Personal bond of Rs {m.group(1)}"
                if not any(c.startswith("Personal bond") for c in found):
                    found[name] = {"condition": name, "source": ref}
    return list(found.values())


def _concern_text(factor: str, packs: dict[str, EvidencePack]) -> str:
    """The bench's concern in the State's own words when a recorded objection exists, else the factor."""
    pack = packs.get(factor)
    if pack is not None:
        for item in _items(pack, "likely_objection"):
            text = first_sentence(str(item.get("text") or ""))
            if text:
                return text
    return f"The bench may ask about {factor_label(factor)}."


def _pointer(g: Ground | None, citations: dict[tuple[str, int], str]) -> str | None:
    """The authority a concern's answer points at: its rendered citation, else 'doc#para'."""
    a = g.authorities[0] if g is not None and g.authorities else None
    if a is None:
        return None
    return citations.get((a.doc_id, a.para)) or a.citation or f"{a.doc_id}#{a.para}"


def build_card(
    brief: BailBrief, packs: list[EvidencePack], sparring: SparringRecord | None = None, citations: dict[tuple[str, int], str] | None = None
) -> dict[str, Any]:
    """The hearing-prep card as plain data.

    Args:
        brief: the assembled BailBrief
        packs: Sutradhar's evidence packs (comparable reasoning, recorded objections, conditions)
        sparring: Abhiyojak's record, when sparring ran
        citations: rendered citation text by (doc_id, para) for the pointers

    Returns:
        {"case_id", "label", "bench_concerns" ({factor, concern, answer, ground, authority, source}), "lead_with" (ground ids),
        "lead_points", "conditions" (texts), "condition_sources", "open_issues" (texts)}; the same keys the Phase 5
        renderer reads (export/hearing_card.py).
    """
    citations = citations or {}
    by_factor = {g.factor.value: g for g in brief.grounds}
    pack_of = {p.factor.value: p for p in packs}
    weight: dict[str, int] = {}
    for p in packs:
        for item in _items(p):
            for f in item.get("factors") or []:
                weight[str(getattr(f, "value", f))] = weight.get(str(getattr(f, "value", f)), 0) + 1
        weight[p.factor.value] = weight.get(p.factor.value, 0) + len(_items(p, "likely_objection")) + (3 if p.stance == FactorStance.ADVERSE else 0)
    for g in brief.grounds:
        if g.stance == FactorStance.ADVERSE:
            weight[g.factor.value] = weight.get(g.factor.value, 0) + 3
    order = [f.value for f in Factor]
    concerns: list[dict[str, Any]] = []
    seen: set[str] = set()
    for o in sparring.objections if sparring is not None else []:
        ground = next((g for g in brief.grounds if g.id == o.against), by_factor.get(str(o.factor)))
        answer = first_sentence(o.reply.text) if o.reply is not None else ""
        concerns.append({
            "factor": str(o.factor), "concern": o.objection, "answer": answer or "No reply drafted: counsel to answer.",
            "ground": ground.id if ground is not None else None, "authority": _pointer(ground, citations), "source": "prosecution objection",
        })  # fmt: skip
        seen.add(str(o.factor))
    for factor in sorted(weight, key=lambda f: (-weight[f], order.index(f) if f in order else 99)):
        ground = by_factor.get(factor)
        if factor in seen or ground is None or len(concerns) >= MAX_CONCERNS:
            continue
        concerns.append({
            "factor": factor, "concern": _concern_text(factor, pack_of), "answer": first_sentence(ground.argument) or "No supported answer drafted: see the open issues.",
            "ground": ground.id, "authority": _pointer(ground, citations), "source": "comparable orders",
        })  # fmt: skip
    ranked = [g for g in brief.grounds if g.check == ClaimCheck.SUPPORTED and g.stance == FactorStance.FAVOURABLE]
    ranked += [g for g in brief.grounds if g.check == ClaimCheck.SUPPORTED and g.stance != FactorStance.FAVOURABLE]
    if len(ranked) < LEAD_POINTS:
        ranked += [g for g in brief.grounds if g.check == ClaimCheck.REPAIRED]
    lead = ranked[:LEAD_POINTS]
    found = conditions_from(packs)
    issues = [i.item for i in brief.open_issues]
    for o in sparring.objections if sparring is not None else []:
        if o.verdict is not None and o.verdict.value != "ANSWERED":
            issues.append(f"{o.id} ({str(o.factor).replace('_', ' ')}): {o.objection} ({o.verdict.value.lower()})")
    return {
        "case_id": brief.case_id,
        "label": DRAFT_LABEL,
        "bench_concerns": concerns[:MAX_CONCERNS],
        "lead_with": [g.id for g in lead],
        "lead_points": [lead_point(g) for g in lead],
        "conditions": [c["condition"] for c in found][:MAX_CONDITIONS],
        "condition_sources": found[:MAX_CONDITIONS],
        "open_issues": issues,
    }


def lead_point(g: Ground) -> dict[str, Any]:
    """A point to lead with: the ground's first sentence and where it is argued."""
    return {"ground": g.id, "factor": g.factor.value, "point": first_sentence(g.argument), "check": g.check.value}
