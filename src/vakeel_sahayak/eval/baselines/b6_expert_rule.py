"""Baseline B6. Expert-rule checklist, no model: the fixed template of standard grounds a legal-aid lawyer puts in every bail application, with statute text from `law.statutes`, `map_section` and the Rights Radar flags (docs/evaluation-plan.md §3.1).

"The simplest rule a domain expert would write" (L12). No model is called: `run_case` never touches `ctx.llm`. It deliberately
does NOT import `pipelines/factor_tagger.py`, `pipelines/gold/*` or `pipelines/order_facts.py` (the code that builds G1 and G3), so it cannot agree
with the gold by construction; the section finder below is its own short regular expression. Its factor recall is not used as evidence
(a template that argues the same grounds in every case has recall by construction); it is scored on factor precision, F1, unsupported-fact
rate and the deterministic Rights checks, not on G3 dossier fields.
"""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.schemas.bail_brief import BailBrief, Ground, OpenIssue, StatutoryPosition
from vakeel_sahayak.schemas.enums import ClaimCheck, Factor, FactorStance, OpenIssueType, RightsStatus

# The template: (factor, stance, wording). Every application argues these; nothing here reads the order's text.
TEMPLATE: list[tuple[Factor, FactorStance, str]] = [
    (Factor.CUSTODY_PERIOD, FactorStance.FAVOURABLE, "The applicant has been in custody since the arrest and further detention before trial serves no investigative purpose."),
    (Factor.CHARGE_SHEET_FILED, FactorStance.FAVOURABLE, "The investigation is complete or the charge sheet is filed; custody is not needed to complete the investigation."),
    (Factor.PARITY_WITH_CO_ACCUSED, FactorStance.FAVOURABLE, "A co-accused alleged to have a similar role has been released on bail; the applicant claims parity."),
    (Factor.ANTECEDENTS, FactorStance.FAVOURABLE, "The applicant has no criminal antecedents."),
    (Factor.FLIGHT_RISK, FactorStance.FAVOURABLE, "The applicant has roots in the community and is not a flight risk."),
    (Factor.WITNESS_TAMPERING, FactorStance.FAVOURABLE, "The applicant will not tamper with evidence or witnesses and will abide by any conditions the court imposes."),
    (Factor.GRAVITY_AND_PUNISHMENT, FactorStance.FAVOURABLE, "The gravity of the offence, read with the punishment the statute provides, does not justify pre-trial detention."),
]
_SECTION = re.compile(r"\b(?:sections?|secs?\.?|u/s|s\.)\s*((?:\d+[A-Za-z]?(?:\(\d+\))?(?:\s*(?:,|and|/|&)\s*)?)+)\s*(?:of\s+(?:the\s+)?)?(IPC|BNSS|BNS|Cr\.?P\.?C\.?|NDPS|UAPA|PMLA)\b", re.IGNORECASE)
_ITEM = re.compile(r"\d+[A-Za-z]?(?:\(\d+\))?")


def find_sections(text: str) -> list[tuple[str, str]]:
    """(code, section) pairs written in a text such as 'Section 318(4) BNS' (own regular expression; first occurrence order, no duplicates)."""
    seen: list[tuple[str, str]] = []
    for m in _SECTION.finditer(text or ""):
        code = re.sub(r"[^A-Za-z]", "", m.group(2)).upper()
        for item in _ITEM.findall(m.group(1)):
            if (code, item) not in seen:
                seen.append((code, item))
    return seen


def _tool(ctx: AgentContext, name: str, **kwargs: Any) -> Any:
    """Call a tool from the context's toolbox (fixtures) or the registry; count it as a store call; None on any failure."""
    from vakeel_sahayak.tools.registry import get_tool

    try:
        fn = ctx.tools.get(name) or get_tool(name)
        out = fn(**kwargs)
    except Exception:  # noqa: BLE001 - a missing store or tool simply gives the template no statute text
        return None
    try:
        ctx.budgets.charge(None, store_calls=1)
    except Exception:  # noqa: BLE001 - minimal budgets
        pass
    return None if getattr(out, "kind", None) and getattr(out, "message", None) else out


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Produce a brief for one T1 case under B6: the fixed template, statute text and Rights flags; no model call.

    Args:
        case: `case_id`, `facts` (or `facts_text`), `before` (the order date; rights are computed as of it)
        ctx: context (only `tools`, `budgets` and `case_id` are used)

    Returns:
        BailBrief (every ground NEEDS_REVIEW: nothing is checked; the draft label is the schema's fixed label).
    """
    facts = str(case.get("facts") or case.get("facts_text") or "")
    refs = find_sections(facts)
    sections, max_punishment, authorities_text = [], None, ""
    for code, section in refs[:3]:
        sections.append(f"{section} {code}")
        row = _tool(ctx, "get_statute", code=code, section=section)
        text = getattr(row, "text", None)
        if text:
            authorities_text = authorities_text or f" Statute: {code} s.{section}: {str(text)[:240]}"
            max_punishment = max_punishment or getattr(row, "max_punishment", None)
        if code == "IPC":
            _tool(ctx, "map_section", code=code, section=section, offence_date=str(case.get("before") or "2024-07-01"))
    report = _tool(ctx, "rights_check", case_id=case["case_id"], as_of=case.get("before"))
    flags = [c for c in getattr(report, "checks", []) if c.status in (RightsStatus.ELIGIBLE, RightsStatus.FLAG)]
    grounds: list[Ground] = []
    for i, (factor, stance, wording) in enumerate(TEMPLATE, start=1):
        extra = authorities_text if factor == Factor.GRAVITY_AND_PUNISHMENT else ""
        grounds.append(Ground(id=f"G{i}", factor=factor, stance=stance, argument=wording + extra, authorities=[], check=ClaimCheck.NEEDS_REVIEW))
    issues = [OpenIssue(type=OpenIssueType.NEEDS_REVIEW, item=f"Rights Radar: {c.check.value} is {c.status.value}" + (f" ({c.rule})" if c.rule else "")) for c in flags]
    position = StatutoryPosition(sections=sections, max_punishment=max_punishment,
                                 rights="; ".join(f"{c.check.value}: {c.status.value}" for c in flags) or None)
    return BailBrief(case_id=case["case_id"], statutory_position=position, grounds=grounds, open_issues=issues)
