"""How a contract slot becomes tool calls, and how a tool result becomes slot items (plan §6.2, §6.3).

One place knows which tool serves which store, what arguments a slot needs and what a result looks like once it is a
plain dict, so the planner, the fixed router (A6), the free planner (A7) and the baseline (B4) all build calls the same
way. Nothing here calls a tool or a model.

Plan steps may carry references to earlier results of the same plan (`"$authority.top3"`) and `$`-prefixed meta
arguments (`"$only_docs"`) that the runner resolves and strips before the call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vakeel_sahayak.agents.base import jsonable
from vakeel_sahayak.agents.sutradhar.factor_pick import CaseSignals
from vakeel_sahayak.agents.sutradhar.relaxation import offence_group
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import Factor, StoreName
from vakeel_sahayak.schemas.retrieval_plan import PlanStep
from vakeel_sahayak.tools.base import ToolError

SC_COURT = "Supreme Court of India"
AUTHORITY_SLOTS = ("authority", "conditions")  # slots filled from court reasoning
CITATION_SLOTS = ("good_law", "sc_root")
STORE_TOOLS: dict[StoreName, str] = {
    StoreName.CASELAW_REASONING: "search_reasoning",
    StoreName.CASELAW_SIMILAR: "similar_orders",
    StoreName.CASELAW_CITATIONS: "citations",
    StoreName.ADVOCACY_OBJECTIONS: "search_objections",
    StoreName.ADVOCACY_ARGUMENTS: "search_arguments",
    StoreName.CASE_DOCS: "search_case_docs",
    StoreName.CASE_TIMELINE: "get_timeline",
    StoreName.CASE_FACTS: "get_fact",
    StoreName.LAW_STATUTES: "get_statute",
    StoreName.LAW_CONCORDANCE: "map_section",
}
TOOL_STORES: dict[str, StoreName | None] = {
    **{tool: store for store, tool in STORE_TOOLS.items()},
    "search_statutes": StoreName.LAW_STATUTES,
    "transfer_check": StoreName.LAW_CONCORDANCE,
    "good_law_check": StoreName.CASELAW_CITATIONS,
    "rights_check": None,
    "date_calc": StoreName.CASE_TIMELINE,
}
SEARCH_TOOLS = ("search_reasoning", "search_objections", "search_arguments")
FILTERED_TOOLS = SEARCH_TOOLS + ("search_case_docs",)

FACTOR_LABEL: dict[Factor, str] = {
    Factor.GRAVITY_AND_PUNISHMENT: "gravity of the offence and punishment",
    Factor.CUSTODY_PERIOD: "period of custody",
    Factor.CHARGE_SHEET_FILED: "charge sheet filed, investigation complete",
    Factor.TRIAL_DELAY: "delay in trial",
    Factor.PARITY_WITH_CO_ACCUSED: "parity with co-accused",
    Factor.ANTECEDENTS: "criminal antecedents",
    Factor.FLIGHT_RISK: "flight risk",
    Factor.WITNESS_TAMPERING: "witness tampering",
    Factor.WEAK_PRIMA_FACIE: "weak prima facie case",
    Factor.HEALTH_AGE_FAMILY: "health, age, gender or family circumstances",
    Factor.STATUTORY_BAR: "statutory bar on bail",
    Factor.UNDERTRIAL_PERIOD: "undertrial period under section 479 BNSS or 436A CrPC",
}
AUTHORITY_QUERY: dict[Factor, str] = {
    Factor.GRAVITY_AND_PUNISHMENT: "gravity of offence alone is not a ground to refuse bail",
    Factor.CUSTODY_PERIOD: "prolonged custody of undertrial entitles to bail Article 21",
    Factor.CHARGE_SHEET_FILED: "charge sheet filed custodial interrogation no longer required bail",
    Factor.TRIAL_DELAY: "delay in trial violates Article 21 speedy trial bail",
    Factor.PARITY_WITH_CO_ACCUSED: "parity co-accused granted bail similar role",
    Factor.ANTECEDENTS: "criminal antecedents not a ground to deny bail by themselves",
    Factor.FLIGHT_RISK: "flight risk roots in the community bail conditions",
    Factor.WITNESS_TAMPERING: "apprehension of witness tampering bail with conditions",
    Factor.WEAK_PRIMA_FACIE: "scope of bail inquiry prima facie case no mini trial",
    Factor.HEALTH_AGE_FAMILY: "bail on grounds of illness age woman proviso",
    Factor.STATUTORY_BAR: "twin conditions reasonable grounds for believing not guilty bail",
    Factor.UNDERTRIAL_PERIOD: "undertrial detained for one third of maximum sentence released on bail",
}
DOC_QUERY: dict[str, tuple[str, list[str]]] = {  # slot -> (query, document types)
    "co_accused_order": ("co-accused granted bail order", ["BAIL_ORDER", "ORDER_SHEET"]),
    "role_comparison": ("role of the accused and the co-accused as alleged", ["FIR", "BAIL_ORDER"]),
    "charge_sheet_date": ("charge sheet filed final report", ["CHARGE_SHEET_COVER", "ORDER_SHEET"]),
    "trial_stage": ("stage of the trial charges framed witnesses examined", ["ORDER_SHEET"]),
    "witness_examination": ("witnesses examined cross-examination", ["ORDER_SHEET"]),
    "fir_allegations": ("allegations in the FIR", ["FIR"]),
}
FACT_FIELD: dict[str, str] = {"antecedents": "antecedents", "personal_papers": "personal", "community_roots": "personal"}
TIMELINE_SLOTS = ("co_accused_order", "charge_sheet_date", "trial_stage", "custody_days")
SPECIAL_SECTION = {"NDPS": ("NDPS", "37"), "UAPA": ("UAPA", "43D"), "PMLA": ("PMLA", "45")}
ISSUE_TEXT: dict[str, str] = {
    "antecedents": "Antecedents unknown: confirm with counsel whether any other case is pending.",
    "personal_papers": "No medical or personal papers on file: ask counsel for them.",
    "community_roots": "No roots in the community stated: ask counsel for family, work and address.",
}


@dataclass
class PlanContext:
    """The case facts a plan is written from (pseudonymised; nothing here names a person)."""

    case_id: str
    before: str  # the case's order date: every corpus search sees only earlier documents
    as_of: str
    sig: CaseSignals
    switches: Switches = field(default_factory=Switches)
    facts_text: str | None = None

    @property
    def family(self) -> list[str]:
        """The section family of the case, empty under A4 (plain retrieval)."""
        return list(self.sig.refs) if self.switches.retrieval_filters else []

    def facts_summary(self) -> str:
        """A few plain sentences about the case for the whole-order similarity search (no names)."""
        if self.facts_text and not self.switches.uses_dossier:
            return self.facts_text[:1200]
        sig = self.sig
        parts = []
        if sig.refs:
            parts.append("Sections charged: " + ", ".join(sig.refs[:6]) + ".")
        if sig.custody_days is not None:
            parts.append(f"In custody for {sig.custody_days} days.")
        if sig.charge_sheet_filed is not None:
            parts.append("Charge sheet filed." if sig.charge_sheet_filed else "Charge sheet not filed.")
        if sig.co_accused:
            parts.append("Co-accused bail: " + ", ".join(str(c.get("outcome")) for c in sig.co_accused) + ".")
        if sig.trial_stage:
            parts.append(f"Trial stage: {sig.trial_stage}.")
        return " ".join(parts) or "Bail application."


    def to_payload(self) -> dict[str, Any]:
        """The case facts a planning prompt carries (no names: refs, dates and counts)."""
        sig = self.sig
        return _scrub(
            {
                "case_id": self.case_id, "before": self.before, "as_of": self.as_of, "plain": not self.switches.retrieval_filters,
                "no_dossier": not self.switches.uses_dossier, "knockout": self.switches.knockout_store, "sections": sig.sections,
                "custody_days": sig.custody_days, "arrest_date": sig.arrest_date, "charge_sheet_filed": sig.charge_sheet_filed,
                "charge_sheet_date": sig.charge_sheet_date, "trial_stage": sig.trial_stage,
                "co_accused": [{"id": c.get("id"), "outcome": c.get("outcome"), "date": c.get("date")} for c in sig.co_accused],
                "facts_text": self.facts_text if not self.switches.uses_dossier else None,
            }
        )  # fmt: skip

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> PlanContext:
        """Rebuild a context from `to_payload` (what the offline planner does with the prompt's data)."""
        sig = CaseSignals(
            sections=list(data.get("sections") or []), custody_days=data.get("custody_days"), arrest_date=data.get("arrest_date"),
            charge_sheet_filed=data.get("charge_sheet_filed"), charge_sheet_date=data.get("charge_sheet_date"),
            trial_stage=data.get("trial_stage"), co_accused=list(data.get("co_accused") or []),
        )  # fmt: skip
        switches = Switches(plain_retrieval=bool(data.get("plain")), no_dossier=bool(data.get("no_dossier")), knockout_store=data.get("knockout"))
        return cls(case_id=str(data.get("case_id")), before=str(data.get("before")), as_of=str(data.get("as_of")), sig=sig, switches=switches, facts_text=data.get("facts_text"))


def authority_query(factor: Factor, ctx: PlanContext) -> str:
    """The first-draft query of an authority slot; a special-act bar names the act that is charged."""
    base = AUTHORITY_QUERY[Factor(factor)]
    if Factor(factor) == Factor.STATUTORY_BAR:
        codes = [c for c in ctx.sig.codes if c in SPECIAL_SECTION]
        if codes:
            code, section = SPECIAL_SECTION[sorted(codes)[0]]
            return f"{base} {code} section {section}"
    group = offence_group(ctx.sig.refs)
    return f"{base} {group}" if group and Factor(factor) in (Factor.PARITY_WITH_CO_ACCUSED, Factor.TRIAL_DELAY) else base


def objection_query(factor: Factor) -> str:
    """The first-draft query for what the State argues on a factor."""
    return f"prosecution opposes bail {FACTOR_LABEL[Factor(factor)]}"


def base_query(factor: Factor, slot: str, ctx: PlanContext) -> str:
    """First-draft query text for a slot (a rule; rewording is the model's job)."""
    if slot == "likely_objection":
        return objection_query(factor)
    if slot in DOC_QUERY:
        return DOC_QUERY[slot][0]
    return authority_query(factor, ctx)


# ---------------------------------------------------------------------------------------------------------- steps


def _scrub(args: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in args.items() if v not in (None, [], "")}


def search_args(tool: str, factor: Factor, slot: str, query: str, ctx: PlanContext) -> dict[str, Any]:
    """Arguments of a paragraph search: factor, section family and `before`; under A4 the query and `before` only."""
    args: dict[str, Any] = {"query": query, "before": ctx.before, "k": 5 if tool != "search_reasoning" else 10}
    if ctx.switches.retrieval_filters:
        args["factor"] = Factor(factor).value
        args["section_family"] = ctx.family
        if tool == "search_reasoning" and Factor(factor) == Factor.PARITY_WITH_CO_ACCUSED and slot == "authority":
            args["outcome"] = "granted"
    return _scrub(args)


def make_steps(factor: Factor, slot: str, source: str | StoreName, ctx: PlanContext, query: str | None = None) -> list[PlanStep]:
    """The call(s) that fill a slot from one source (a store or a tool name).

    Args:
        factor: the factor
        slot: the slot name
        source: a StoreName, or the name of a tool (`rights_check`, `date_calc`, `search_statutes`)
        ctx: the case facts
        query: query text (default: the slot's first draft)

    Returns:
        One or more plan steps, in call order (empty when the source cannot be asked for this slot).
    """
    factor = Factor(factor)
    q = query or base_query(factor, slot, ctx)
    sig = ctx.sig
    if isinstance(source, str) and not isinstance(source, StoreName):
        try:
            source = StoreName(source)
        except ValueError:
            pass
    if source == "rights_check":
        return [PlanStep(slot=slot, tool="rights_check", args={"case_id": ctx.case_id, "as_of": ctx.as_of})]
    if source == "date_calc":
        return [PlanStep(slot=slot, tool="date_calc", args={"start": sig.arrest_date, "end": ctx.as_of, "rule": "CALENDAR_DAYS_BETWEEN"})] if sig.arrest_date else []
    if source == "search_statutes":
        return [PlanStep(slot=slot, tool="search_statutes", args={"query": q, "k": 5})]
    if source == StoreName.CASELAW_REASONING:
        return [PlanStep(slot=slot, tool="search_reasoning", args=search_args("search_reasoning", factor, slot, q, ctx))]
    if source == StoreName.ADVOCACY_OBJECTIONS:
        return [PlanStep(slot=slot, tool="search_objections", args=search_args("search_objections", factor, slot, q, ctx))]
    if source == StoreName.ADVOCACY_ARGUMENTS:
        return [PlanStep(slot=slot, tool="search_arguments", args=search_args("search_arguments", factor, slot, q, ctx))]
    if source == StoreName.CASELAW_SIMILAR:
        args: dict[str, Any] = {"facts_text": q if len(q) > 80 else ctx.facts_summary(), "before": ctx.before, "k": 10}
        if ctx.switches.retrieval_filters:
            from vakeel_sahayak.pipelines.order_facts import custody_band

            outcome = next((c.get("outcome") for c in sig.co_accused if c.get("outcome")), None)
            args["signature"] = _scrub(
                {
                    "sections": [s["ref"] for s in sig.sections if s.get("ref")],
                    "custody_band": custody_band(sig.custody_days),
                    "charge_sheet_status": None if sig.charge_sheet_filed is None else ("filed" if sig.charge_sheet_filed else "not_filed"),
                    "co_accused_outcome": "granted" if outcome and "grant" in str(outcome).lower() else ("rejected" if outcome else None),
                }
            )
        return [PlanStep(slot=slot, tool="similar_orders", args=_scrub(args))]
    if source == StoreName.CASELAW_CITATIONS:
        want = ["sc_root", "good_law"] if slot == "sc_root" else ["good_law", "sc_root"]
        return [PlanStep(slot=slot, tool="citations", args={"doc_ids": "$authority.top3", "want": want})]
    if source == StoreName.CASE_DOCS:
        text, types = DOC_QUERY.get(slot, (q, []))
        args = {"case_id": ctx.case_id, "query": q if query else text, "k": 5}
        if types and ctx.switches.retrieval_filters:
            args["doc_types"] = types
        return [PlanStep(slot=slot, tool="search_case_docs", args=args)]
    if source == StoreName.CASE_TIMELINE:
        steps = [PlanStep(slot=slot, tool="get_timeline", args={"case_id": ctx.case_id})]
        return steps
    if source == StoreName.CASE_FACTS:
        return [PlanStep(slot=slot, tool="get_fact", args={"case_id": ctx.case_id, "field": FACT_FIELD.get(slot, slot)})]
    if source == StoreName.LAW_STATUTES:
        return _statute_steps(factor, slot, q, ctx)
    return []


def _statute_steps(factor: Factor, slot: str, query: str, ctx: PlanContext) -> list[PlanStep]:
    from vakeel_sahayak.pipelines.concordance.refs import split_ref

    def one(code: str, section: str) -> PlanStep:
        return PlanStep(slot=slot, tool="get_statute", args={"code": code, "section": section})

    if slot == "s480_proviso":
        return [one("BNSS", "480")]
    if slot == "statute_text":
        return [one("BNSS", "479"), one("CrPC", "436A")]
    if slot == "bar_provision":
        codes = [c for c in sorted(ctx.sig.codes) if c in SPECIAL_SECTION]
        if codes:
            return [one(*SPECIAL_SECTION[c]) for c in codes[:2]]
        return [PlanStep(slot=slot, tool="search_statutes", args={"query": "bail restriction twin conditions special act", "k": 5})]
    steps: list[PlanStep] = []
    for s in ctx.sig.sections[:3]:
        try:
            code, section = split_ref(s["ref"])
        except (ValueError, KeyError, TypeError):
            continue
        steps.append(one(code, section))
    return steps or [PlanStep(slot=slot, tool="search_statutes", args={"query": query, "k": 5})]


def slot_sources(contract: Any, slot: str, ctx: PlanContext, unavailable: set[str] | None = None) -> list[str | StoreName]:
    """The sources a slot may use, in the order Sutradhar tries them: a Rights Radar tool first, then the contract's stores.

    Knocked-out or failed stores (A10, store unavailable) are left out; `ask_user` is not Sutradhar's tool (a missing
    antecedents slot becomes a question to counsel in the open issues instead).
    """
    spec = contract.slots[slot]
    gone = unavailable or set()
    out: list[str | StoreName] = []
    if "rights_check" in spec.tools:
        out.append("rights_check")
    for store in spec.stores:
        s = StoreName(store)
        if ctx.switches.store_allowed(s) and s.value not in gone:
            out.append(s)
    return out


def companions(contract: Any, slot: str) -> list[str]:
    """Tools asked alongside the slot's first source (`date_calc` counts the custody days from the timeline's arrest)."""
    return [t for t in contract.slots[slot].tools if t == "date_calc"]


# ------------------------------------------------------------------------------------------------- results to items

_RIGHTS_FOR_SLOT = {"rights_report": "undertrial_limit", "antil_category": "antil_category"}


def item_key(item: dict[str, Any]) -> str:
    """Identity of an item, so the same paragraph, chunk or event is counted once however often it is retrieved."""
    if item.get("para") is not None:
        return f"{item.get('doc_id')}#{item.get('para')}"
    for k in ("chunk_id", "event_id"):
        if item.get(k):
            return str(item[k])
    if item.get("doc_id"):
        return f"{'cite' if 'status' in item else 'doc'}:{item['doc_id']}"
    return repr(sorted((k, str(v)) for k, v in item.items()))[:300]


def _dump(x: Any) -> Any:
    return jsonable(x)


def items_of(step: PlanStep, result: Any, slot: str | None = None, only_docs: list[str] | None = None) -> list[dict[str, Any]]:
    """A tool result as plain dict items for a slot ([] for a ToolError, an unsupported fact or an empty answer)."""
    if result is None or isinstance(result, ToolError):
        return []
    tool = step.tool
    slot = slot or step.slot
    if tool in SEARCH_TOOLS + ("similar_orders", "search_case_docs", "get_timeline", "search_statutes"):
        rows = [_dump(r) for r in (result if isinstance(result, list) else [result])]
        if only_docs is not None:
            rows = [r for r in rows if r.get("doc_id") in set(only_docs)]
        return [r for r in rows if isinstance(r, dict)]
    if tool == "get_statute":
        return [_dump(result)]
    if tool == "get_fact":
        data = _dump(result)
        value, status = data.get("value"), str(data.get("status"))
        if value is None or status in ("UNSUPPORTED",):
            return []
        return [{"field": step.args.get("field"), "value": value, "status": status, "source": data.get("source"), "label": f"{step.args.get('field')}: {value}"}]
    if tool == "citations" and isinstance(result, dict):
        out = []
        for doc_id, rec in result.items():
            rec = _dump(rec)
            if not isinstance(rec, dict) or rec.get("found") is False:
                out.append({"doc_id": doc_id, "status": "UNKNOWN", "found": False})
                continue
            law = rec.get("good_law") if isinstance(rec.get("good_law"), dict) else {}
            out.append(
                {
                    "doc_id": doc_id,
                    "status": str(law.get("status") or ("OVERRULED" if rec.get("overruled_by") else "OK" if "overruled_by" in rec else "UNKNOWN")),
                    "overruled_by": rec.get("overruled_by") or law.get("overruled_by"),
                    "sc_root": rec.get("sc_root") or law.get("sc_root"),
                    "authority": rec.get("authority"),
                    "found": True,
                }
            )
        return out
    if tool == "rights_check":
        data = _dump(result)
        wanted = _RIGHTS_FOR_SLOT.get(slot)
        checks = [c for c in data.get("checks", []) if wanted is None or c.get("check") == wanted]
        return [{**c, "label": f"{c.get('check')}: {c.get('status')} {c.get('detail') or ''}".strip()} for c in checks]
    if tool == "date_calc":
        data = _dump(result)
        return [{**data, "label": f"custody days: {data.get('value')} ({data.get('start')} to {data.get('end')})"}]
    return [_dump(result)] if result else []
