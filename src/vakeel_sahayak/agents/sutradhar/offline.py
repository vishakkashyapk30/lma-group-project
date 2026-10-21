"""Offline handlers for Sutradhar's model tasks (`sutradhar.plan_factor`, `sutradhar.reword_query`, `sutradhar.free_plan`): rules, no language model.

Planning writes, for every slot of the contract, the call that fills it from the slot's first source, with the first-draft
query and the filters the case allows; rewording picks the next alternative phrasing of the factor from a table of legal synonyms, never one already tried; the
free planner (A7) writes the generic plan a model with no contracts would: a reasoning search and an objection search
per factor, the case's timeline and the sections' text. Both only read the request's data.
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.sutradhar.critique import critique_data
from vakeel_sahayak.agents.sutradhar.planning import PlanContext, make_steps
from vakeel_sahayak.agents.sutradhar.prompts import TASK_CRITIQUE, TASK_FREE_PLAN, TASK_PLAN, TASK_RATE, TASK_REWORD
from vakeel_sahayak.agents.sutradhar.sufficiency import rate_data
from vakeel_sahayak.models.offline_llm import OfflineRequest, register_offline_handler
from vakeel_sahayak.schemas.enums import Factor

REWORDS: dict[str, list[str]] = {
    "gravity_and_punishment": ["seriousness of allegation not sole ground for refusing bail", "bail is the rule jail is the exception offence punishable up to seven years"],
    "custody_period": ["long incarceration undertrial right to speedy trial bail", "period of detention exceeds likely sentence release on bail"],
    "charge_sheet_filed": ["investigation completed charge sheet filed no further custody needed", "bail after filing of final report custody not necessary"],
    "trial_delay": ["unreasonable delay in conclusion of trial liberty under Article 21", "trial not likely to conclude soon accused languishing in jail"],
    "parity_with_co_accused": ["co-accused with similar role released on bail parity", "principle of parity bail granted to co-accused identical allegations"],
    "antecedents": ["pending criminal cases no bar to bail antecedents alone", "previous involvement in other cases not a ground for refusing bail"],
    "flight_risk": ["accused not likely to abscond roots in society bail", "conditions to secure presence of accused surrender passport"],
    "witness_tampering": ["no likelihood of influencing witnesses bail conditions", "witnesses examined risk of tampering diminished"],
    "weak_prima_facie": ["court at bail stage does not weigh evidence meticulously prima facie", "allegations in FIR do not disclose offence bail"],
    "health_age_family": ["bail to sick or infirm person proviso", "grant of bail to woman or aged accused humanitarian grounds"],
    "statutory_bar": ["conditions for grant of bail under special statute reasonable grounds", "rigours of statutory bar relaxed prolonged incarceration"],
    "undertrial_period": ["first time offender released after one third of maximum sentence", "undertrial detained for half of maximum sentence section 479"],
}
SLOT_WORDS: dict[str, str] = {
    "likely_objection": "State objection to bail submissions of the prosecution",
    "conditions": "conditions imposed while granting bail",
}


def next_wording(factor: str, slot: str, query: str, tried: list[str]) -> dict[str, Any]:
    """The next unused alternative wording of the query for this factor and slot (also the agent's fallback when no model answers)."""
    tried_set = {str(t).strip().lower() for t in tried} | {query.strip().lower()}
    prefix = SLOT_WORDS.get(slot)
    options = [f"{prefix} {alt}" if prefix and slot == "likely_objection" else alt for alt in REWORDS.get(factor, [])]
    for alt in options:
        if alt.strip().lower() not in tried_set:
            return {"query": alt, "reason": "a different phrasing of the same legal need"}
    words = query.split()
    shorter = " ".join(words[:5]) if len(words) > 5 else " ".join(reversed(words))
    return {"query": shorter or query, "reason": "the key words of the earlier query"}


def reword_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `sutradhar.reword_query`."""
    case = req.case
    return next_wording(str(case.get("factor") or ""), str(case.get("slot") or ""), str(case.get("query") or ""), list(case.get("tried") or []))


def free_plan_offline(req: OfflineRequest) -> dict[str, Any]:
    """The generic plan of a planner with no contracts: per factor a reasoning and an objection search, plus the case's own records."""
    case = req.case
    before, case_id = case.get("before"), case.get("case_id")
    family = [str(r) for r in case.get("section_family") or []]
    tools = set(case.get("tools") or [])
    steps: list[dict[str, Any]] = []
    first = next((str(f.get("factor")) for f in case.get("factors") or [] if isinstance(f, dict)), "gravity_and_punishment")

    def add(factor: str, tool: str, args: dict[str, Any]) -> None:
        if tool in tools or not tools:
            steps.append({"factor": factor, "tool": tool, "args": args})

    if case_id:
        add(first, "get_timeline", {"case_id": case_id})
        add(first, "search_case_docs", {"case_id": case_id, "query": "bail order charge sheet FIR custody", "k": 5})
    for section in (case.get("sections") or [])[:2]:
        if isinstance(section, (list, tuple)) and len(section) == 2:
            add(first, "get_statute", {"code": section[0], "section": section[1]})
    for entry in case.get("factors") or []:
        factor = str(entry.get("factor"))
        phrase = str(entry.get("phrase") or factor.replace("_", " "))
        base = {"query": phrase, "before": before, "k": 5}
        if family:
            base["section_family"] = family
        add(factor, "search_reasoning", {**base, "factor": factor, "k": 10})
        add(factor, "search_objections", {**base, "factor": factor, "query": f"prosecution opposes bail {phrase}"})
    return {"steps": steps}


def plan_factor_offline(req: OfflineRequest) -> dict[str, Any]:
    """The first plan of a factor as a rule-based planner writes it: for every slot, the call that fills it from its first source.

    Reads only the request: the factor, the slots with their sources, and the case facts (`PlanContext.to_payload`).
    """
    case = req.case
    factor = Factor(str(case.get("factor")))
    ctx = PlanContext.from_payload(dict(case.get("context") or {}))
    steps = []
    for slot in case.get("slots") or []:
        name, sources = str(slot.get("slot")), list(slot.get("sources") or [])
        if not sources:
            continue
        steps += make_steps(factor, name, sources[0], ctx)
        for tool in slot.get("companions") or []:
            steps += make_steps(factor, name, tool, ctx)
    left = case.get("budget_left") or {"store_calls": 8, "tokens": 12000}
    return {"factor": factor.value, "round": int(case.get("round") or 1), "budget_left": left, "steps": [s.model_dump(mode="json") for s in steps], "assessment": {}, "next": None}


def rate_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `sutradhar.rate_sufficiency` (S3): a deterministic text-overlap rule, not a language model."""
    return rate_data(req.case, req.corpus)


def critique_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `sutradhar.critique_slot` (S1): deterministic paragraph verdicts and corrective action, not a language model."""
    return critique_data(req.case, req.corpus)


def register() -> None:
    """Register the handlers with the offline client (the agent module does this at import)."""
    register_offline_handler(TASK_PLAN, plan_factor_offline)
    register_offline_handler(TASK_REWORD, reword_offline)
    register_offline_handler(TASK_FREE_PLAN, free_plan_offline)
    register_offline_handler(TASK_RATE, rate_offline)
    register_offline_handler(TASK_CRITIQUE, critique_offline)


register()
