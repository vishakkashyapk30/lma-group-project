"""Sutradhar agent (plan §3.2). Orchestrator: evidence contracts, retrieval plans, sufficiency checks, budget, delegation, chat routing (plan §6). Qwen3-14B on Ada.

Sutradhar decides what evidence each bail ground needs and where to look, and says when it has enough:

1. **Pick factors** (§6.2 step 1): each of the 12 factors is favourable, adverse or not applicable, with a reason read off
   the dossier and the RightsReport (`factor_pick.py`).
2. **Per factor** (steps 2.1-2.5), all factors in lock-step rounds so a run is reproducible: plan a `RetrievalPlan` for the
   unfilled slots of the factor's evidence contract, run it through `call_tool` (independent calls concurrent), assess every
   slot FILLED / WEAK / MISSING by rule checks (`slot_rules.py`), then re-plan the slots that fell short: reword the query,
   relax filters in the fixed order factor, section family, court (`relaxation.py`), follow the citation graph to the
   Supreme Court root, or try another allowed store. A factor stops when its required slots are filled, its budget is spent
   or nothing is left to try; slots still short become open issues in the plan's wording. A paragraph tagged with two
   factors serves both (a shared pool, merged between rounds).
3. **Delegate** (step 3): evidence packs go to Vakeel, the draft to Abhiyojak, objections back to Vakeel; a failed claim is
   either re-retrieved (a new plan for its slot) or reworded (`resolve_failed_claim`).
4. **After a change set** (step 4): only the affected factors are re-run (`reopen_after_change`).

It also routes counsel's chat questions (§6.4) and runs the variants of the evaluation: A6 (fixed router), A7 (free planner),
B4 (every store, fused), A4 (plain retrieval) and A10 (a store knocked out is an unavailable store).

Every plan, call, assessment, re-plan and budget hit is an event with actor SUTRADHAR (tool `plan`, `assess`, `replan`,
`budget_hit`, ...), so the UI trace can show them. Sutradhar is callable on its own:

    agent = SutradharAgent(case_id="case-0007", log=log)
    state = agent.run(CaseGraphState(case_id="case-0007", before="2025-02-03"))
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from vakeel_sahayak.agents.base import AgentContext, BaseAgent, jsonable, prediction_language
from vakeel_sahayak.agents.sutradhar import critique as critic
from vakeel_sahayak.agents.sutradhar import depth as depth_rules
from vakeel_sahayak.agents.sutradhar import offline  # noqa: F401  (importing `offline` registers the offline handlers)
from vakeel_sahayak.agents.sutradhar import skew as skew_rules
from vakeel_sahayak.agents.sutradhar.chat_router import (
    CHAT_ROUTES,
    NALSA_HELPLINE,
    REFUSE_ADVICE,
    REFUSE_PREDICTION,
    classify_question,
    is_lay_advice,
)
from vakeel_sahayak.agents.sutradhar.contracts_runtime import allowed_stores, contract_for, unfilled_slots  # noqa: F401
from vakeel_sahayak.agents.sutradhar.factor_pick import (
    CaseSignals,
    pick_stances,
    signals_from_dossier,
    signals_from_text,
)
from vakeel_sahayak.agents.sutradhar.planning import (
    AUTHORITY_SLOTS,
    FILTERED_TOOLS,
    SC_COURT,
    SEARCH_TOOLS,
    TOOL_STORES,
    PlanContext,
    authority_query,
    base_query,
    companions,
    item_key,
    items_of,
    make_steps,
    slot_sources,
)
from vakeel_sahayak.agents.sutradhar.prompts import (
    SYSTEM_PROMPT,
    TASK_PLAN,
    TASK_REWORD,
    USER_PROMPT_TEMPLATES,
    Reworded,
)
from vakeel_sahayak.agents.sutradhar.relaxation import RELAXATION_ORDER, describe, relax
from vakeel_sahayak.agents.sutradhar.slot_rules import assess_slot
from vakeel_sahayak.agents.sutradhar.sufficiency import rate, signals_of
from vakeel_sahayak.agents.sutradhar.work import FactorWork, SlotWork, open_issue, plan_assessment
from vakeel_sahayak.contracts.loader import ALLOWED_STORES
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.models.offline_llm import OfflineRequest
from vakeel_sahayak.orchestration.budgets import BudgetExhausted
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.orchestration.structured_output import StructuredOutputError
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.chat import ChatMessage, ToolChip
from vakeel_sahayak.schemas.enums import AgentName, ClaimCheck, EventKind, Factor, FactorStance, SlotStatus, StoreName
from vakeel_sahayak.schemas.retrieval_plan import BudgetLeft, EvidencePack, PlanStep, RetrievalPlan, SlotResult
from vakeel_sahayak.schemas.sparring import SparringRecord
from vakeel_sahayak.tools.base import ToolError

MAX_ROUNDS = 6  # plan rounds per factor; the store-call budget normally stops a factor sooner
TRANSFER_LIMIT = 3  # authorities per factor that get a transfer flag
_CHANGED_FIELD_FACTORS: dict[str, tuple[Factor, ...]] = {
    "fir": (Factor.GRAVITY_AND_PUNISHMENT, Factor.WEAK_PRIMA_FACIE),
    "offence_date": tuple(Factor),  # the era of the law decides the section family of every search
    "sections": tuple(Factor),
    "arrest_date": (Factor.CUSTODY_PERIOD, Factor.TRIAL_DELAY, Factor.UNDERTRIAL_PERIOD),
    "first_remand": (Factor.CUSTODY_PERIOD, Factor.UNDERTRIAL_PERIOD),
    "custody_days": (Factor.CUSTODY_PERIOD, Factor.TRIAL_DELAY, Factor.UNDERTRIAL_PERIOD),
    "charge_sheet": (Factor.CHARGE_SHEET_FILED, Factor.TRIAL_DELAY, Factor.WITNESS_TAMPERING),
    "trial_stage": (Factor.TRIAL_DELAY, Factor.WITNESS_TAMPERING),
    "previous_bail": (Factor.ANTECEDENTS, Factor.PARITY_WITH_CO_ACCUSED),
    "co_accused_bail": (Factor.PARITY_WITH_CO_ACCUSED,),
    "antecedents": (Factor.ANTECEDENTS,),
    "personal": (Factor.FLIGHT_RISK, Factor.HEALTH_AGE_FAMILY),
}
_CHANGED_RIGHTS_FACTORS: dict[str, tuple[Factor, ...]] = {
    "undertrial_limit": (Factor.UNDERTRIAL_PERIOD,),
    "default_bail": (Factor.CHARGE_SHEET_FILED, Factor.CUSTODY_PERIOD),
    "antil_category": (Factor.GRAVITY_AND_PUNISHMENT,),
    "statutory_bar": (Factor.STATUTORY_BAR,),
}


@dataclass
class StepOutcome:
    """What one plan step returned."""

    step: PlanStep
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    items: list[dict[str, Any]] = field(default_factory=list)
    error: ToolError | None = None
    skipped: str | None = None


@dataclass
class ClaimDecision:
    """Sutradhar's answer to a claim that failed its check: new evidence for its slot, or let Vakeel reword."""

    decision: str  # 're-retrieve' | 'reword'
    reason: str
    factor: Factor
    slots: list[str] = field(default_factory=list)
    pack: EvidencePack | None = None


def _dependent(step: PlanStep) -> bool:
    return any(isinstance(v, str) and v.startswith("$") for v in step.args.values()) or any(k.startswith("$") for k in step.args)


class SutradharAgent(BaseAgent):
    """Orchestrator: evidence contracts, retrieval plans, sufficiency checks, budget, delegation, chat routing (plan §6). Qwen3-14B on Ada."""

    NAME = AgentName.SUTRADHAR
    ROLE_MODEL = "agents_14b"
    SYSTEM_PROMPT = SYSTEM_PROMPT

    def __init__(
        self,
        ctx: AgentContext | None = None,
        *,
        case_id: str | None = None,
        log: EventLog | None = None,
        switches: Switches | None = None,
        llm: Any = None,
        cache: Any = None,
        tools: dict[str, Any] | None = None,
        cases_dir: str | None = None,
        before: str | None = None,
        mode: str | None = None,
        max_rounds: int = MAX_ROUNDS,
        parallel_steps: bool = False,
    ) -> None:
        """Create Sutradhar, from an AgentContext or from plain arguments (the graph is optional).

        Args:
            ctx: the injected context; its case id, log, budget, switches, LLM, retrieval cache and toolbox are used
            case_id: the case (needed when there is no context)
            log: the case's event log (default: the configured per-case log)
            switches: ablation switches (A4, A6, A7, A10 are read here)
            llm: the `agents_14b` client, used only to reword queries (and by A7's planner)
            cache: the shared retrieval cache (`batch.cache.RetrievalCache`); tool calls use it through `call_tool`
            tools: a toolbox that replaces the registry's tools (fakes in tests)
            cases_dir: cases folder for the event log
            before: the case's order date when the graph state carries none
            mode: None for the full system, 'B4' for the every-store baseline
            max_rounds: plan rounds per factor
            parallel_steps: run the independent calls of one plan concurrently (default: in plan order, so the log reads like the plan)
        """
        if ctx is None:
            if not case_id:
                raise ValueError("Sutradhar needs a case_id or an AgentContext")
            ctx = AgentContext(
                case_id=case_id, log=log, switches=switches or Switches(), llm=llm, cache=cache,
                tools=dict(tools or {}), cases_dir=cases_dir, before=before,
            )  # fmt: skip
        super().__init__(ctx)
        self.mode = (mode or "").upper() or None
        self.max_rounds = max_rounds
        self.parallel_steps = parallel_steps
        self._pctx: PlanContext | None = None
        self._stances: dict[Factor, tuple[FactorStance, str]] = {}
        self._work: dict[Factor, FactorWork] = {}
        self._pool: dict[str, dict[str, Any]] = {}  # reasoning paragraphs any factor retrieved, shared across factors
        self._transfer: dict[tuple[str, str], dict[str, Any]] = {}
        self._plans_log: list[RetrievalPlan] = []
        self._last_state: CaseGraphState | None = None
        self.latest_state: CaseGraphState | None = None  # state after the latest `reopen_after_change`
        self._peers: dict[AgentName, BaseAgent] = {}
        self._prior: Any = None  # S6 / B5: the learned store prior (loaded on first use, or set with `set_store_prior`)
        self.retrieval_signals: dict[str, dict[str, Any]] = {}  # per factor, filled when a stopping variant (S3) is on

    # ------------------------------------------------------------------ small plumbing

    def store_prior_model(self) -> Any:
        """The learned store prior (S6, B5): the one set with `set_store_prior`, else the artefact at the default path, else the neutral prior."""
        if self._prior is None:
            from vakeel_sahayak.agents.sutradhar.store_prior import StorePrior

            self._prior = StorePrior.load()
        return self._prior

    def set_store_prior(self, prior: Any) -> None:
        """Use this `StorePrior` instead of loading the default artefact."""
        self._prior = prior

    def _decision(self, tool: str, text: str = "", **outputs: Any) -> None:
        """One event for a decision (actor SUTRADHAR; tool `pick_factors`, `plan`, `assess`, `replan`, `budget_hit`, ...)."""
        self.emit(EventKind.AGENT_MESSAGE, {"tool": tool, "outputs": {"type": tool, "text": text, **outputs}})

    def _tool(self, name: str, budget_factor: Any = None, /, **kwargs: Any) -> Any:
        """call_tool, with a refused or failed call coming back as a ToolError rather than an exception."""
        from vakeel_sahayak.tools.registry import ToolPermissionError

        try:
            return self.call_tool(name, budget_factor=budget_factor, **kwargs)
        except ToolPermissionError as exc:
            return ToolError(tool=name, kind="permission_denied", message=str(exc), retryable=False)

    def _signals(self, state: CaseGraphState) -> CaseSignals:
        """What the picker and the planner read: the approved dossier and RightsReport (A1: the raw facts text)."""
        rights, dossier = state.rights, state.dossier
        if rights is None or (dossier is None and self.switches.uses_dossier):
            try:
                cs = self.case_state()
                rights = rights or cs.rights_report()
                dossier = dossier or (cs.dossier() if self.switches.uses_dossier else None)
            except Exception:  # noqa: BLE001 - a case with no log yet simply has no dossier
                pass
        if not self.switches.uses_dossier:
            return signals_from_text(state.facts_text, state.before, rights)
        return signals_from_dossier(dossier, rights)

    def plan_context(self, state: CaseGraphState) -> PlanContext:
        """The case facts plans are written from: order date, as-of date, section family, signals.

        The order date (`before`) is the state's, else the context's, else the dossier's as-of date, else today; the as-of
        date the Rights Radar counts to is the state's, else the dossier's, else today.
        """
        today = date.today().isoformat()
        sig = self._signals(state)
        before = state.before or getattr(self.ctx, "before", None) or sig.as_of or today
        return PlanContext(
            case_id=self.case_id, before=before, as_of=state.as_of or sig.as_of or today, sig=sig,
            switches=self.switches, facts_text=state.facts_text,
        )  # fmt: skip

    def _context_for(self, state: CaseGraphState | None) -> PlanContext:
        if state is not None:
            self._last_state = state
        if self._pctx is None or self._pctx.case_id != self.case_id:
            self._pctx = self.plan_context(state or self._last_state or CaseGraphState(case_id=self.case_id, switches=self.switches))
        return self._pctx

    def _left(self, factor: Factor) -> BudgetLeft:
        left = getattr(self.budgets, "left", None)
        if left is not None:
            try:
                return left(Factor(factor).value)
            except Exception:  # noqa: BLE001
                pass
        b = contract_for(factor).budget
        return BudgetLeft(store_calls=b.store_calls, tokens=b.tokens)

    def _budget_spent(self, work: FactorWork) -> bool:
        left = self._left(work.factor)
        return work.budget_hit or left.store_calls <= 0 or left.tokens <= 0

    # ------------------------------------------------------------------ the run

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Sutradhar's full job for the current graph state.

        Picks the factors, retrieves evidence for each chosen factor (the full loop, or A6's fixed router, A7's free planner
        or B4's every-store baseline) and leaves one `EvidencePack` per chosen factor in `state.evidence_packs`, with every
        plan round in `state.plans`. When `state.reopened_factors` is set and packs already exist, only those factors are
        re-run (plan §10). The stage is left for the graph to advance.

        Args:
            state: see behaviour

        Returns:
            Updated state: evidence_packs, plans, budget.
        """
        self._last_state = state
        self._pctx = None
        self._plans_log = []
        self.retrieval_signals = {}
        if self.mode == "B4":
            from vakeel_sahayak.agents.sutradhar.baselines import run_b4

            packs = run_b4(self, state)
        elif self.switches.store_prior == "only":
            from vakeel_sahayak.agents.sutradhar.store_prior import run_prior_only

            packs = run_prior_only(self, state, self.store_prior_model())
        elif self.switches.fixed_router:
            from vakeel_sahayak.agents.sutradhar.fixed_router import run_fixed_router

            packs = run_fixed_router(state, agent=self)
        elif not self.switches.uses_contracts:
            from vakeel_sahayak.agents.sutradhar.baselines import run_free_planner

            packs = run_free_planner(self, state)
        elif state.reopened_factors and state.evidence_packs:
            return self.rerun_factors(state, list(state.reopened_factors))
        else:
            packs = self.retrieve(state)
        return self._with_packs(state, packs, state.plans + self._plans_log)

    def _with_packs(self, state: CaseGraphState, packs: list[EvidencePack], plans: list[RetrievalPlan]) -> CaseGraphState:
        self.write_view("evidence_packs", packs)
        update: dict[str, Any] = {"evidence_packs": packs, "plans": plans}
        if self.retrieval_signals:
            update["retrieval_signals"] = dict(self.retrieval_signals)
        snap = getattr(self.budgets, "snapshot", None)
        if snap is not None:
            update["budget"] = snap()
        to_dict = getattr(self.budgets, "to_dict", None)
        if to_dict is not None:
            update["budget_tracker"] = to_dict()
        return state.model_copy(update=update)

    # ------------------------------------------------------------------ step 1: pick factors

    def pick_factors(self, state: CaseGraphState) -> list[EvidencePack]:
        """Mark each of the 12 factors favourable, adverse or not applicable with a reason (plan §6.2 step 1).

        Reads the approved dossier and the RightsReport (A1: the raw facts) by rules, so every reason names the field or
        Radar check it rests on. The decisions are logged (tool `pick_factors`) and kept as the `factor_decisions` view.

        Args:
            state: see behaviour

        Returns:
            One pack shell per factor, in Appendix A order (no slots yet).
        """
        self._last_state = state
        self._pctx = self.plan_context(state)
        picks = pick_stances(self._pctx.sig)
        self._stances = {f: (stance, reason) for f, stance, reason in picks}
        packs = [EvidencePack(factor=f, stance=stance, reason=reason) for f, stance, reason in picks]
        decisions = [{"factor": f.value, "stance": stance.value, "reason": reason} for f, stance, reason in picks]
        self.write_view("factor_decisions", decisions)
        counts = {s.value: sum(1 for p in packs if p.stance == s) for s in FactorStance}
        self._decision("pick_factors", "Picked the factors: " + ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in counts.items()), decisions=decisions, source=self._pctx.sig.source)
        return packs

    # ------------------------------------------------------------------ step 2: plan, run, assess, re-plan

    def plan_factor(self, factor: Factor, state: CaseGraphState) -> RetrievalPlan:
        """Write a RetrievalPlan for unfilled slots (step 2.1).

        Starts the factor afresh. The model (offline: the rule-based planner) is asked once for the plan, with the slots
        of the factor's contract, their allowed stores and tools and the case facts; the agent then checks what came back:
        a step outside the contract (an unknown slot, a store the slot may not use, a knocked-out store) is dropped and
        logged, `before` (the case date) is filled in or clamped on every shared-store step, the case id is the case's own,
        A4 strips the factor and section-family filters, and a required slot the model gave no call gets the first call a
        rule would write. `budget_left` comes from the budget tracker, never from the model.

        Args:
            factor: see behaviour
            state: see behaviour

        Returns:
            RetrievalPlan (round 1).
        """
        factor = Factor(factor)
        pctx = self._context_for(state)
        work = self._new_work(factor, pctx)
        self._work[factor] = work
        left = self._left(factor)  # read before the planning call, which itself costs tokens
        plan = self._check_plan(work, self._ask_plan(work, left), 1, left)
        self._adopt_plan(work, plan)
        work.plans.append(plan)
        self._decision(
            "plan", f"Round 1 for {factor.value}: {len(plan.steps)} call(s).", factor=factor.value, round=1,
            steps=[s.model_dump() for s in plan.steps], budget_left=left.model_dump(),
        )  # fmt: skip
        return plan

    def _ask_plan(self, work: FactorWork, left: BudgetLeft) -> RetrievalPlan:
        """The model's plan for a factor; with `Switches.plan_cache` (S14) a stored template of the same signature is reused instead (`batch.cache.PlanCache`)."""
        plans = self._plan_cache()
        if plans is None:
            return self._ask_plan_model(work, left)
        key = plans.signature(work, self.switches)
        fresh = {(st.slot, st.tool): st for sw in work.slots.values() for st in self._rule_steps(work, sw)}
        if (hit := plans.lookup(key, fresh)) is not None:
            self._decision("plan_cache", f"Reused a stored plan for {work.factor.value}.", factor=work.factor.value, hit=True, tokens_saved=hit["tokens_saved"])
            return RetrievalPlan(factor=work.factor, round=1, budget_left=left, steps=[PlanStep(**s) for s in hit["steps"]])
        before = self.budgets.spent(Factor(work.factor).value)[0] if self.budgets is not None else 0
        plan = self._ask_plan_model(work, left)
        spent = (self.budgets.spent(Factor(work.factor).value)[0] - before) if self.budgets is not None else 0
        plans.store(key, [s.model_dump() for s in plan.steps], max(0, spent))
        self._decision("plan_cache", f"Stored the plan for {work.factor.value}.", factor=work.factor.value, hit=False, tokens=max(0, spent))
        return plan

    def _plan_cache(self) -> Any:
        """The plan cache riding on the shared retrieval cache, or None (S14 off, or no shared cache)."""
        cache = getattr(self.ctx, "cache", None)
        if not self.switches.plan_cache or cache is None:
            return None
        from vakeel_sahayak.batch.cache import plans_of

        return plans_of(cache)

    def _ask_plan_model(self, work: FactorWork, left: BudgetLeft) -> RetrievalPlan:
        slots = [
            {
                "slot": name, "need": sw.need, "sources": [str(getattr(s, "value", s)) for s in sw.sources],
                "stores": [StoreName(s).value for s in work.contract.slots[name].stores], "tools": list(work.contract.slots[name].tools),
                "companions": companions(work.contract, name),
            }
            for name, sw in work.slots.items()
            if sw.sources
        ]  # fmt: skip
        case = {"factor": work.factor.value, "round": 1, "stance": work.stance.value, "budget_left": left.model_dump(), "slots": slots, "context": work.pctx.to_payload()}
        try:
            out = self.ask(
                TASK_PLAN, USER_PROMPT_TEMPLATES[TASK_PLAN].format(factor=work.factor.value), case=case, schema=RetrievalPlan,
                factor=work.factor, max_tokens=1500,
            )  # fmt: skip
            return out if isinstance(out, RetrievalPlan) else RetrievalPlan.model_validate(out)
        except (BudgetExhausted, StructuredOutputError, ModelUnavailable, PrivacyBoundaryError, ValueError):
            from vakeel_sahayak.agents.sutradhar.offline import plan_factor_offline

            self._decision("plan_fallback", "The model gave no usable plan; the rule-based planner wrote it.", factor=work.factor.value)
            return RetrievalPlan.model_validate(plan_factor_offline(OfflineRequest(task=TASK_PLAN, instructions="", data={"case": case}, prompt="", schema=None)))

    def _step_problem(self, work: FactorWork, step: PlanStep) -> str | None:
        """Why a planned step is not allowed (None when it is): the slot must exist and the tool read only stores the slot may use."""
        if step.slot.startswith("_"):  # the citation-graph hop of a re-plan: the factor must be allowed the citation store
            ok = step.tool == "citations" and StoreName.CASELAW_CITATIONS in ALLOWED_STORES[work.factor] and self.switches.store_allowed(StoreName.CASELAW_CITATIONS)
            return None if ok else f"{step.tool} is not allowed for the citation-graph hop of {work.factor.value}"
        slot = work.contract.slots.get(step.slot)
        if slot is None:
            return f"slot '{step.slot}' is not in the contract"
        if step.tool in slot.tools:
            return None
        if step.tool not in TOOL_STORES:
            return f"unknown tool '{step.tool}'"
        store = TOOL_STORES[step.tool]
        if store is None or StoreName(store) not in [StoreName(s) for s in slot.stores]:
            return f"{step.tool} may not fill slot '{step.slot}' (stores {[StoreName(s).value for s in slot.stores]})"
        if not self.switches.store_allowed(store):
            return f"{StoreName(store).value} is unavailable in this run (A10)"
        return None

    def _tidy_step(self, work: FactorWork, step: PlanStep) -> PlanStep:
        """The fixed parts of a step the model must not decide: the case's own id, the leakage date, A4's plain retrieval."""
        args = dict(step.args)
        ctx = work.pctx
        if step.tool in ("search_reasoning", "search_objections", "search_arguments", "similar_orders"):
            given = str(args.get("before") or "")
            args["before"] = ctx.before if not given or given > ctx.before else given
        if "case_id" in args or step.tool in ("get_timeline", "get_fact", "search_case_docs", "rights_check"):
            args["case_id"] = self.case_id
        if not self.switches.retrieval_filters:
            for key in ("factor", "section_family", "outcome", "doc_types", "signature"):
                args.pop(key, None)
        if self._expands(work, step):
            args["expand_graph"] = True  # S5: seed a personalised PageRank over the citation graph from the plain results
        if self.switches.weak_signal == "skew" and step.tool == "search_reasoning" and not any(k.startswith("$") for k in step.args):
            args["with_scores"] = True  # S4: the results carry their hybrid score, so the skew of the list can be measured
        return PlanStep(slot=step.slot, tool=step.tool, args=args)

    def _expands(self, work: FactorWork, step: PlanStep) -> bool:
        """S5: an authority-slot search of court reasoning, when the citation store may be used and the step is not the SC-root fetch."""
        return (
            self.switches.graph_expansion and step.tool == "search_reasoning" and step.slot in AUTHORITY_SLOTS
            and not any(k.startswith("$") for k in step.args)
            and StoreName.CASELAW_CITATIONS in ALLOWED_STORES[work.factor] and self.switches.store_allowed(StoreName.CASELAW_CITATIONS)
        )  # fmt: skip

    def _rule_steps(self, work: FactorWork, sw: SlotWork) -> list[PlanStep]:
        if not sw.sources:
            return []
        steps = make_steps(work.factor, sw.name, sw.sources[0], work.pctx)
        for tool in companions(work.contract, sw.name):
            steps += make_steps(work.factor, sw.name, tool, work.pctx)
        return steps

    def _check_plan(self, work: FactorWork, plan: RetrievalPlan, round_: int, left: BudgetLeft, *, complete: bool = True) -> RetrievalPlan:
        kept: list[PlanStep] = []
        for step in plan.steps:
            problem = self._step_problem(work, step)
            if problem:
                self._decision("plan_step_dropped", f"Dropped a planned step: {problem}.", factor=work.factor.value, step=step.model_dump(), reason=problem)
                continue
            tidy = self._tidy_step(work, step)
            if tidy not in kept:
                kept.append(tidy)
        planned = {s.slot for s in kept}
        for name, sw in work.slots.items():
            if complete and name not in planned and sw.required and sw.sources:
                kept.extend(self._tidy_step(work, s) for s in self._rule_steps(work, sw))
        calls = left.store_calls
        final: list[PlanStep] = []
        for step in kept:  # never plan more store calls than the factor has left
            if TOOL_STORES.get(step.tool) is not None:
                if calls <= 0:
                    continue
                calls -= 1
            final.append(step)
        if len(final) < len(kept):
            work.budget_hit = True
            self._decision("budget_hit", f"Budget of {work.factor.value}: {len(kept) - len(final)} planned call(s) dropped.", factor=work.factor.value, dropped=[s.tool for s in kept if s not in final])
        return RetrievalPlan(factor=work.factor, round=round_, budget_left=left, steps=final)

    def _adopt_plan(self, work: FactorWork, plan: RetrievalPlan) -> None:
        """Remember each slot's calls as first planned (the base the re-plan relaxes from) and which source they use."""
        by_slot: dict[str, list[PlanStep]] = {}
        for st in plan.steps:
            if not st.slot.startswith("_"):
                by_slot.setdefault(st.slot, []).append(PlanStep(slot=st.slot, tool=st.tool, args=dict(st.args)))
        for name, steps in by_slot.items():
            sw = work.slots.get(name)
            if sw is None or sw.orig is not None:
                continue
            sw.orig, sw.pending = steps, False
            for i, src in enumerate(sw.sources):
                if steps[0].tool == src or TOOL_STORES.get(steps[0].tool) == src:
                    sw.src_idx = i
                    break

    def _new_work(self, factor: Factor, pctx: PlanContext, *, adaptive: bool = True) -> FactorWork:
        stance, reason = self._stances.get(factor) or next(((s, r) for f, s, r in pick_stances(pctx.sig) if f == factor), (FactorStance.FAVOURABLE, None))
        contract = contract_for(factor)
        set_limits = getattr(self.budgets, "set_factor_limits", None)
        if set_limits is not None:
            set_limits(factor.value, store_calls=contract.budget.store_calls, tokens=contract.budget.tokens)
        work = FactorWork(factor=factor, stance=stance, reason=reason, contract=contract, pctx=pctx)
        knocked = self.switches.knockout_store
        for name, slot in contract.slots.items():
            sources = slot_sources(contract, name, pctx)
            sw = SlotWork(name=name, need=slot.need, sources=sources)
            if knocked and any(str(getattr(s, "value", s)) == knocked for s in slot.stores):
                work.unavailable.add(knocked)
            if not sources:
                sw.pending, sw.exhausted = False, True
                sw.result = SlotResult(slot=name, status=SlotStatus.MISSING, note="no allowed store is available in this run")
            work.slots[name] = sw
        if self.switches.store_prior == "order":
            self._apply_prior(work)
        if adaptive and self.switches.retrieval_policy == "adaptive":
            self._apply_depth(work)
        return work

    def _apply_prior(self, work: FactorWork) -> None:
        """S6: inside each slot, try the contract's allowed stores in the learned prior's order (tools stay first; no store is removed, weak ones are deferred)."""
        from vakeel_sahayak.agents.sutradhar.store_prior import context_for

        prior = self.store_prior_model()
        ctx = context_for(work.factor, work.sig)
        for name, sw in work.slots.items():
            stores = [s for s in sw.sources if isinstance(s, StoreName)]
            if len(stores) < 2:
                continue
            ranking = prior.rank(ctx, stores)
            by_name = {s.value: s for s in stores}
            ordered = iter(by_name[n] for n in ranking.order)
            sw.sources = [next(ordered) if isinstance(s, StoreName) else s for s in sw.sources]
            work.prior_trace[name] = {"contract": [s.value for s in stores], "prior": list(ranking.order), "deferred": list(ranking.deferred)}

    def _apply_depth(self, work: FactorWork) -> None:
        """S2: classify the factor (none / single / multi), cap its rounds and store calls, and skip the corpus slots of a 'none' factor."""
        depth = depth_rules.classify(work.factor, work.contract, work.stance, work.sig)
        work.depth, work.round_cap = depth, depth.max_rounds
        if depth.store_calls is not None:
            set_limits = getattr(self.budgets, "set_factor_limits", None)
            if set_limits is not None:
                set_limits(work.factor.value, store_calls=min(depth.store_calls, work.contract.budget.store_calls))
        if depth.skip_corpus:
            for name in depth_rules.corpus_slot_names(work.contract):
                sw = work.slots[name]
                sw.skipped, sw.need, sw.pending, sw.exhausted, sw.sources = True, "optional", False, True, []
                sw.result = SlotResult(slot=name, status=SlotStatus.MISSING, note=f"not retrieved: adaptive depth 'none' ({depth.reasons[0]})")
        self._decision("depth", f"{work.factor.value}: retrieval depth {depth.level} ({'; '.join(depth.reasons)}).", factor=work.factor.value, **depth.as_signal())

    def _ensure_work(self, factor: Factor) -> FactorWork:
        factor = Factor(factor)
        if factor not in self._work:
            self._work[factor] = self._new_work(factor, self._context_for(None))
        return self._work[factor]

    @staticmethod
    def _query_of(sw: SlotWork) -> str | None:
        """The query text of the slot's first call that has one."""
        for st in sw.orig or []:
            if st.args.get("query"):
                return str(st.args["query"])
        return None

    def _sc_steps(self, work: FactorWork, sw: SlotWork) -> list[PlanStep]:
        """Follow the citation graph from the High Court paragraphs to the SC judgment behind them, then fetch its paragraphs."""
        ctx = work.pctx
        steps: list[PlanStep] = []
        if not work.roots:
            steps.append(PlanStep(slot="_sc_follow", tool="citations", args={"doc_ids": "$authority.top3", "want": ["sc_root"]}))
        query = self._query_of(sw) or authority_query(work.factor, ctx)
        args: dict[str, Any] = {"query": query, "court": SC_COURT, "before": ctx.before, "k": 10, "$only_docs": "$sc_roots", "$via": "sc_root"}
        steps.append(PlanStep(slot=sw.name, tool="search_reasoning", args=args))
        return steps

    def _slot_steps(self, work: FactorWork, sw: SlotWork) -> list[PlanStep]:
        """The slot's calls for the next round: its first plan with the filters relaxed to `sw.level` (or the special modes)."""
        if sw.mode == "sc_follow":
            return self._sc_steps(work, sw)
        if sw.orig is None:
            sw.orig = [self._tidy_step(work, s) for s in self._rule_steps_from(work, sw)]
        again = sw.calls > 0 or bool(sw.done)  # a retry repeats only the searches: lookups of the case's own records return the same
        repeat = (*SEARCH_TOOLS, "search_case_docs", "search_statutes", "similar_orders", "citations")
        steps: list[PlanStep] = []
        for st in sw.orig:
            if again and st.tool not in repeat:
                continue
            args = dict(st.args)
            if st.tool in FILTERED_TOOLS and sw.level >= 0:
                args = relax(args, sw.level)
            if st.tool == "citations" and sw.docs_level != 3:
                args["doc_ids"] = f"$authority.top{sw.docs_level}"
            steps.append(PlanStep(slot=st.slot, tool=st.tool, args=args))
        return steps

    def _rule_steps_from(self, work: FactorWork, sw: SlotWork) -> list[PlanStep]:
        src = sw.source
        if src is None:
            return []
        steps = make_steps(work.factor, sw.name, src, work.pctx)
        if sw.src_idx == 0:
            for tool in companions(work.contract, sw.name):
                steps += make_steps(work.factor, sw.name, tool, work.pctx)
        return steps

    def _build_plan(self, work: FactorWork, round_: int | None = None) -> RetrievalPlan:
        """The next round's plan from the slots waiting for a call (rule-based: the re-plan moves have already been applied)."""
        steps: list[PlanStep] = []
        for sw in work.slots.values():
            if not sw.pending:
                continue
            if work.only is not None and sw.name not in work.only:
                sw.pending = False
                continue
            steps.extend(self._slot_steps(work, sw))
            sw.mode, sw.pending = "normal", False
        left = self._left(work.factor)
        plan = self._check_plan(work, RetrievalPlan(factor=work.factor, round=round_ or work.round, budget_left=left, steps=steps), round_ or work.round, left, complete=False)
        work.plans.append(plan)
        self._decision(
            "plan", f"Round {plan.round} for {work.factor.value}: {len(plan.steps)} call(s).", factor=work.factor.value, round=plan.round,
            steps=[s.model_dump() for s in plan.steps], budget_left=plan.budget_left.model_dump(),
        )  # fmt: skip
        return plan

    def run_plan(self, plan: RetrievalPlan) -> list[SlotResult]:
        """Execute calls (step 2.2).

        The calls of a plan run in plan order, so the log reads like the plan (factors run concurrently with one another;
        set `parallel_steps` to run the independent calls of one plan concurrently too). A call that refers to an earlier
        result (`$authority.top3`) waits until that result exists. A refused or failed call is recorded (an unavailable
        store is remembered, a spent budget is logged and stops the factor); it never raises.

        Args:
            plan: see behaviour

        Returns:
            Slot results in plan order (status is provisional until `assess`; items are what this plan retrieved).
        """
        work = self._ensure_work(plan.factor)
        self._adopt_plan(work, plan)
        fresh: dict[str, list[dict[str, Any]]] = {}
        notes: dict[str, list[str]] = {}

        def refs(tok: str) -> Any:
            return self._resolve(work, tok)

        with self.factor_scope(plan.factor):
            if self.parallel_steps:
                independent = [s for s in plan.steps if not _dependent(s)]
                dependent = [s for s in plan.steps if _dependent(s)]
                for out in self.parallel(independent, lambda s: self.exec_step(s, plan.factor, refs=refs)):
                    self._absorb(work, out, fresh, notes)
                for step in dependent:
                    self._absorb(work, self.exec_step(step, plan.factor, refs=refs), fresh, notes)
            else:
                deferred: list[PlanStep] = []
                for step in plan.steps:
                    if _dependent(step) and not self._ready(work, step):
                        deferred.append(step)
                        continue
                    self._absorb(work, self.exec_step(step, plan.factor, refs=refs), fresh, notes)
                for step in deferred:
                    self._absorb(work, self.exec_step(step, plan.factor, refs=refs), fresh, notes)
        results = []
        for slot in dict.fromkeys(s.slot for s in plan.steps if not s.slot.startswith("_")):
            items = fresh.get(slot, [])
            results.append(
                SlotResult(slot=slot, status=SlotStatus.WEAK if items else SlotStatus.MISSING, items=items, note="; ".join(dict.fromkeys(notes.get(slot, []))) or None)
            )
        return results

    def _ready(self, work: FactorWork, step: PlanStep) -> bool:
        """True when every reference of a step can be resolved from what has been retrieved so far."""
        tokens = [v for v in [*step.args.values()] if isinstance(v, str) and v.startswith("$")]
        return all(self._resolve(work, t) for t in tokens if t != "$sc_roots") and (
            "$sc_roots" not in tokens or bool(work.roots)
        )

    def exec_step(self, step: PlanStep, factor: Any, *, refs: Any = None) -> StepOutcome:
        """Run one plan step: resolve its `$` references, strip meta arguments, call the tool, turn the result into items."""
        args = {k: v for k, v in step.args.items() if not k.startswith("$")}
        meta = {k: v for k, v in step.args.items() if k.startswith("$")}
        for k, v in list(args.items()):
            if isinstance(v, str) and v.startswith("$"):
                value = refs(v) if refs else None
                if not value:
                    return StepOutcome(step=step, args=args, skipped="no authority found to check yet" if "authority" in v else f"nothing to resolve {v} yet")
                args[k] = value
        only: list[str] | None = None
        if "$only_docs" in meta:
            only = refs(meta["$only_docs"]) if refs else None
            if not only:
                return StepOutcome(step=step, args=args, skipped="no Supreme Court root found to fetch")
        result = self._tool(step.tool, factor, **args)
        error = result if isinstance(result, ToolError) else None
        items = items_of(step, result, only_docs=only)
        via = meta.get("$via")
        for it in items:
            if via:
                it["via"] = via
        return StepOutcome(step=step, args=args, result=result, items=items, error=error)

    def _resolve(self, work: FactorWork, token: str) -> Any:
        """Value of a plan reference: `$authority.topN` (doc ids of the best authorities so far) or `$sc_roots`."""
        if token == "$sc_roots":
            return sorted(work.roots)
        m = re.fullmatch(r"\$authority\.top(\d+)", token)
        if not m:
            return None
        sw = work.slots.get("authority")
        if sw is None:
            return None
        valid = assess_slot("authority", self._merged(work, sw), 1, work.pctx.before, work.factor, work.pctx.family, relaxed=self._relaxed(work, sw)).items
        docs = [d for d in dict.fromkeys(str(it["doc_id"]) for it in valid if it.get("doc_id")) if d not in work.overruled and d not in work.avoid]
        return docs[: int(m.group(1))]

    def _relaxed(self, work: FactorWork, sw: SlotWork) -> tuple[str, ...]:
        extra = () if self.switches.retrieval_filters else ("factor", "section_family", "plain")
        return tuple(dict.fromkeys(sw.relaxed_names + extra))

    def _absorb(self, work: FactorWork, out: StepOutcome, fresh: dict[str, list[dict[str, Any]]], notes: dict[str, list[str]]) -> None:
        """Fold one step's outcome into the factor's working state (items, SC roots, overruled authorities, unavailable stores)."""
        step, slot = out.step, out.step.slot
        sw = work.slots.get(slot)
        if out.skipped:
            notes.setdefault(slot, []).append(out.skipped)
            if sw:
                sw.errors.append(out.skipped)
            return
        if sw:
            sw.calls += 1
        if out.error is not None:
            kind = out.error.kind
            store = TOOL_STORES.get(step.tool)
            if kind == "store_unavailable" and store is not None:
                work.unavailable.add(store.value)
            if kind == "budget_exhausted":
                work.budget_hit = True
            msg = f"{step.tool}: {kind}"
            notes.setdefault(slot, []).append(msg)
            if sw:
                sw.errors.append(msg)
            return
        if step.tool == "citations":
            for it in out.items:
                if it.get("sc_root"):
                    work.roots.add(str(it["sc_root"]))
                if it.get("status") == "OVERRULED" and it.get("doc_id"):
                    work.overruled[str(it["doc_id"])] = str(it.get("overruled_by") or "a later judgment")
        if slot.startswith("_"):
            return
        fresh.setdefault(slot, []).extend(out.items)
        if sw is not None:
            sw.items.extend(out.items)
        if step.tool == "search_reasoning":
            work.fresh.extend(i for i in out.items if i.get("para") is not None)
            if sw is not None and self.switches.weak_signal == "skew" and out.args.get("with_scores"):
                stats = skew_rules.skew_of(skew_rules.scores_of(out.items))
                sw.skew_last = stats
                trace = work.skew
                trace["scored_calls"] += 1
                trace["weak_flags"] += int(stats["weak"])
                trace["calls"].append({"slot": slot, "round": work.round, **stats})
            if out.args.get("expand_graph"):
                hits = [i for i in out.items if i.get("expanded")]
                g = work.graph
                g["calls"] += 1
                g["hits"] += len(hits)
                g["sc_hits"] += sum(1 for i in hits if "supreme" in str(i.get("court") or "").lower())
                g["docs"].update(str(i["doc_id"]) for i in hits)

    def _merged(self, work: FactorWork, sw: SlotWork) -> list[dict[str, Any]]:
        """The slot's own items plus, for reasoning slots, paragraphs another factor retrieved that carry this factor's tag."""
        items = list(sw.items)
        slot = work.contract.slots.get(sw.name)
        if slot is not None and StoreName.CASELAW_REASONING in [StoreName(s) for s in slot.stores] and sw.name in AUTHORITY_SLOTS:
            seen = {item_key(i) for i in items}
            tag = work.factor.value
            for key in sorted(self._pool):
                rec = self._pool[key]
                if key not in seen and tag in (rec.get("factors") or []):
                    items.append({**rec, "shared": True})
        return items

    def _pool_add(self, items: list[dict[str, Any]]) -> None:
        for it in items:
            if it.get("part") == "reasoning" and it.get("para") is not None:
                self._pool.setdefault(item_key(it), it)

    def assess(self, factor: Factor, results: list[SlotResult]) -> list[SlotResult]:
        """Mark each slot FILLED/WEAK/MISSING using rule checks (step 2.3).

        A paragraph counts toward an authority slot only if it is court reasoning, carries the factor's tag, shares a
        section with the case's section family and is dated before the case (`slot_rules.assess_slot`); filters already
        relaxed are not checked. Items from earlier rounds are kept; an authority found to be overruled is left out.

        Args:
            factor: see behaviour
            results: see behaviour

        Returns:
            Assessed slots (the passing items, with the reason in the note).
        """
        work = self._ensure_work(factor)
        fresh, work.fresh = work.fresh, []
        self._pool_add(fresh)
        pctx = work.pctx
        for r in results:  # standalone use: results handed in that `run_plan` did not record
            sw = work.slots.get(r.slot)
            if sw is not None:
                have = {item_key(i) for i in sw.items}
                sw.items.extend(i for i in r.items if item_key(i) not in have)
        for sw in work.slots.values():
            for it in sw.items:
                if sw.name in ("good_law", "sc_root"):
                    if it.get("sc_root"):
                        work.roots.add(str(it["sc_root"]))
                    if it.get("status") == "OVERRULED" and it.get("doc_id"):
                        work.overruled.setdefault(str(it["doc_id"]), str(it.get("overruled_by") or "a later judgment"))
        assessed: list[SlotResult] = []
        for r in results:
            sw = work.slots.get(r.slot)
            need = sw.need if sw else (work.contract.slots[r.slot].need if r.slot in work.contract.slots else "required")
            items = self._merged(work, sw) if sw else list(r.items)
            dropped = 0
            if r.slot not in ("good_law", "sc_root"):
                kept = [i for i in items if str(i.get("doc_id")) not in work.overruled and str(i.get("doc_id")) not in work.avoid]
                dropped, items = len(items) - len(kept), kept
            res = None
            if self.switches.retrieval_policy == "self_critique" and sw is not None and critic.is_corpus_slot(sw, items):
                res = critic.critique_assess(self, work, sw, items)  # S1: the critic replaces the rule checks (hard guards stay rules)
            if res is None:
                res = assess_slot(r.slot, items, need, pctx.before, work.factor, pctx.family, relaxed=self._relaxed(work, sw) if sw else ())
            if self.switches.weak_signal == "skew" and sw is not None:
                res = self._apply_skew(work, sw, res)
            extra = []
            if dropped:
                extra.append(f"{dropped} overruled or rejected authority left out")
            if sw and sw.widened:
                extra.append("; ".join(sw.widened))
            if r.note and not res.items:
                extra.append(r.note)
            if extra:
                res = res.model_copy(update={"note": "; ".join([n for n in [res.note, *extra] if n])})
            if sw is not None:
                sw.result = res
            assessed.append(res)
        if work.plans:
            work.plans[-1].assessment = plan_assessment(work)
        self._decision(
            "assess", f"Round {work.round} for {work.factor.value}: " + ", ".join(f"{k} {v}" for k, v in plan_assessment(work).items()),
            factor=work.factor.value, round=work.round, assessment=plan_assessment(work),
        )  # fmt: skip
        return assessed

    def _apply_skew(self, work: FactorWork, sw: SlotWork, res: SlotResult) -> SlotResult:
        """S4: a slot the rules call FILLED becomes WEAK when its latest scored search had a flat score list and a filter relaxation is left.

        WEAK makes the re-plan relax a filter first (see `_ladder`). Never downgrades once the last relaxation is used, so it cannot loop.
        """
        stats = sw.skew_last
        if res.status != SlotStatus.FILLED or not stats or not stats["weak"] or sw.level >= len(RELAXATION_ORDER) - 1:
            return res
        work.skew["downgrades"] += 1
        note = f"score skew flat (gini {stats['gini']}, top gap {stats['top_gap']}, {stats['n']} scores): treated as weak"
        self._decision(
            "skew_weak", f"{work.factor.value}/{sw.name}: {note}.", factor=work.factor.value, slot=sw.name, round=work.round, **stats,
        )  # fmt: skip
        return res.model_copy(update={"status": SlotStatus.WEAK, "note": "; ".join(n for n in [res.note, note] if n)})

    # -- moves of the re-plan ladder ------------------------------------------------------------------

    def _reword(self, work: FactorWork, sw: SlotWork) -> str | None:
        """A new wording of the slot's query (the model, else the next alternative in the synonym table); None when none is new."""
        from vakeel_sahayak.agents.sutradhar.offline import next_wording

        if sw.orig is None:
            sw.orig = [self._tidy_step(work, s) for s in self._rule_steps_from(work, sw)]
        current = self._query_of(sw) or base_query(work.factor, sw.name, work.pctx)
        tried = [*sw.tried_queries, current]
        new: str | None = None
        try:
            out = self.ask(
                TASK_REWORD, USER_PROMPT_TEMPLATES[TASK_REWORD].format(slot=sw.name, factor=work.factor.value),
                case={"factor": work.factor.value, "slot": sw.name, "query": current, "tried": tried}, schema=Reworded, factor=work.factor, max_tokens=200,
            )  # fmt: skip
            new = (out.query if isinstance(out, Reworded) else str(dict(out).get("query") or "")).strip()
        except (BudgetExhausted, StructuredOutputError, ModelUnavailable, PrivacyBoundaryError, ValueError, AttributeError):
            new = None
        seen = {t.strip().lower() for t in tried}
        if not new or new.lower() in seen:
            new = str(next_wording(work.factor.value, sw.name, current, tried)["query"]).strip()
        if not new or new.lower() in seen:
            return None
        sw.tried_queries.append(current)
        sw.orig = [PlanStep(slot=st.slot, tool=st.tool, args={**st.args, "query": new}) if "query" in st.args else st for st in sw.orig]
        return new

    def _apply_move(self, work: FactorWork, sw: SlotWork, move: str) -> str | None:
        """Apply one re-plan move to a slot; the move's description, or None when it does not apply."""
        src = sw.source
        if move == "reword":
            if src == StoreName.LAW_STATUTES and "to_search" not in sw.done:
                sw.sources.insert(sw.src_idx + 1, "search_statutes")
                sw.src_idx += 1
                sw.orig, sw.level = None, -1
                sw.done.add("to_search")
                return "searched the statutes by text instead of by section"
            if len(sw.tried_queries) >= 2 or not self._query_of(sw) and sw.orig is not None:
                return None
            if sw.orig is not None and not any("query" in st.args for st in sw.orig):
                return None
            new = self._reword(work, sw)
            return f"reworded the query to '{new}'" if new else None
        if move.startswith("relax:"):
            k = int(move.split(":")[1])
            if sw.level >= k:
                return None
            before = [s for s in self._slot_steps(work, sw) if s.tool in FILTERED_TOOLS]
            sw.level = k  # the filters up to k are given up, whether or not this call carried them
            after = [s for s in self._slot_steps(work, sw) if s.tool in FILTERED_TOOLS]
            changed = [(b, a) for b, a in zip(before, after, strict=False) if b.args != a.args]
            if not changed:
                return None
            words: list[str] = []
            for b, a in changed:
                words += [w for w in describe(b.args, a.args) if w not in words]
            sw.widened.extend(w for w in words if w not in sw.widened)
            sw.done.add(move)
            return f"relaxed {RELAXATION_ORDER[k]}" + (f" ({'; '.join(words)})" if words else "")
        if move == "sc_follow":
            allowed = StoreName.CASELAW_CITATIONS in ALLOWED_STORES[work.factor] and self.switches.store_allowed(StoreName.CASELAW_CITATIONS)
            if not allowed or sw.name != "authority" or "sc_follow" in sw.done or not any(i.get("court") != SC_COURT and i.get("para") is not None for i in sw.items):
                return None
            sw.mode = "sc_follow"
            sw.done.add("sc_follow")
            return "following the citation graph to the Supreme Court root"
        if move == "more_docs":
            if sw.docs_level >= 6 or "more_docs" in sw.done:
                return None
            sw.docs_level = 6
            sw.done.add("more_docs")
            return "checking more authorities"
        if move == "other_store":
            for idx in range(sw.src_idx + 1, len(sw.sources)):
                nxt = sw.sources[idx]
                if str(getattr(nxt, "value", nxt)) in work.unavailable:
                    continue
                sw.src_idx, sw.orig, sw.level, sw.mode, sw.docs_level = idx, None, -1, "normal", 3
                sw.done.add(f"store:{idx}")
                return f"trying {getattr(nxt, 'value', nxt)}"
            return None
        return None

    def _ladder(self, sw: SlotWork) -> list[str]:
        """The moves to try for a slot, best first: a WEAK slot (some results) relaxes first, a MISSING one is reworded first."""
        src, weak = sw.source, sw.status == SlotStatus.WEAK
        if src == StoreName.CASELAW_CITATIONS:
            return ["more_docs", "other_store"]
        if sw.name in AUTHORITY_SLOTS or src in (StoreName.CASELAW_REASONING, StoreName.ADVOCACY_OBJECTIONS, StoreName.ADVOCACY_ARGUMENTS, StoreName.CASELAW_SIMILAR):
            relaxing = ["relax:0", "relax:1", "relax:2"]
            return [*relaxing, "reword", "sc_follow", "other_store"] if weak else ["reword", *relaxing, "sc_follow", "other_store"]
        return ["reword", "relax:1", "other_store"]

    def _next_move(self, work: FactorWork, sw: SlotWork) -> str | None:
        ladder = self._ladder(sw)
        action = sw.critic_action if self.switches.retrieval_policy == "self_critique" else None
        if action:
            ladder = critic.reorder(ladder, action)  # S1: the critic's corrective action picks the next move
        for move in ladder:
            if move in sw.done and not move.startswith("reword"):
                continue
            said = self._apply_move(work, sw, move)
            if said:
                sw.pending = True
                if action:
                    sw.critic_used.append(action)
                    work.critique.re_retrievals += 1
                    self._decision("critic_action", f"{work.factor.value}/{sw.name}: critic chose {action}; {said}.", factor=work.factor.value, slot=sw.name, action=action, move=move)
                return said
        return None

    def replan(self, plan: RetrievalPlan, results: list[SlotResult]) -> RetrievalPlan | None:
        """Reword, relax filters in order (factor, section family, court), follow citations to SC, try another allowed store; None when stopped (step 2.4-2.5).

        The next plan is derived from the plan that ran: each slot still short keeps its calls with one more move applied.
        A slot that came back WEAK (some results, too few) relaxes first, in the fixed order, one filter per round (`before`
        is never relaxed); a MISSING slot is reworded first; then the citation graph is followed to the Supreme Court root and
        another allowed store is tried. Stops (None) when every required slot is FILLED, the factor's budget is spent
        (logged as a budget hit), the rounds are used, or nothing is left to try; the slots still short are then open issues.

        Args:
            plan: the plan that ran
            results: its assessed slots

        Returns:
            Next plan or None.
        """
        work = self._ensure_work(plan.factor)
        self._adopt_plan(work, plan)
        for r in results:
            sw = work.slots.get(r.slot)
            if sw is not None:
                sw.result = r
        known = [sw.result for sw in work.slots.values() if sw.result is not None]
        short = [n for n in unfilled_slots(work.contract, known) if work.slots[n].result is not None and not work.slots[n].skipped and (work.only is None or n in work.only)]
        plan.assessment = plan_assessment(work)
        moves: list[str] = []
        if not short and work.stopping.rule_pass_calls is None:
            work.stopping.rule_pass_calls = self._store_calls_spent(work)
        if self.switches.stopping != "rules":
            short = self._apply_rater(work, short)
        if not short:
            work.stopped, plan.next = ("rater_sufficient" if work.stopping.rater_stop else "filled"), None
        elif self._budget_spent(work):
            work.stopped, plan.next = "budget", "stop: the factor's budget is spent"
            self._budget_hit(work)
        elif plan.round >= (self.max_rounds if work.round_cap is None else min(self.max_rounds, work.round_cap)):
            capped = work.round_cap is not None and work.round_cap < self.max_rounds
            work.stopped, plan.next = ("depth_cap", f"stop: adaptive depth '{work.depth.level}' allows {work.round_cap} round(s)") if capped else ("max_rounds", "stop: the plan rounds are used")
        else:
            with self.factor_scope(plan.factor):
                for name in short:
                    sw = work.slots[name]
                    if sw.exhausted:
                        continue
                    said = self._next_move(work, sw)
                    if said is None:
                        sw.exhausted = True
                    else:
                        moves.append(f"{name}: {said}")
            if moves:
                plan.next = "; ".join(moves)
            else:
                work.stopped, plan.next = "exhausted", "stop: nothing left to try"
        self.write_view("retrieval_plan", plan)
        self._plans_log.append(plan)
        self._decision(
            "replan" if moves else "stop", plan.next or "", factor=plan.factor.value, round=plan.round, next=plan.next,
            assessment=plan.assessment, stopped=work.stopped,
        )  # fmt: skip
        if not moves:
            return None
        work.round = plan.round + 1
        return self._build_plan(work, plan.round + 1)

    def _store_calls_spent(self, work: FactorWork) -> int:
        spent = getattr(self.budgets, "spent", None)
        return int(spent(work.factor.value)[1]) if spent else 0

    def _apply_rater(self, work: FactorWork, short: list[str]) -> list[str]:
        """S3: the slots still to work on after the sufficiency rater has had its say (see `sufficiency.py`).

        'rules_llm': asked only when the rules say every required slot is FILLED; an 'insufficient' verdict reopens the slots it
        names. 'llm': asked every round, its verdict alone decides; 'sufficient' stops the factor even if the rules still see a slot
        short (recorded), 'insufficient' continues. Never asked once the factor's budget is spent, and a failed call falls back to the rules.
        """
        trace, mode = work.stopping, self.switches.stopping
        if self._budget_spent(work) or (mode == "rules_llm" and short):
            return short
        verdict = rate(self, work)
        if verdict is None:
            trace.rater_failures += 1
            self._decision("rater_unavailable", f"{work.factor.value}: no sufficiency verdict; the rules decide.", factor=work.factor.value)
            return short
        trace.judgments.append({"round": work.round, "sufficient": verdict.sufficient, "missing": list(verdict.missing), "reason": verdict.reason, "rules_short": list(short)})
        self._decision(
            "sufficiency", f"Round {work.round} for {work.factor.value}: evidence {'sufficient' if verdict.sufficient else 'not sufficient'}.",
            factor=work.factor.value, round=work.round, sufficient=verdict.sufficient, missing=verdict.missing, rules_short=short, mode=mode,
        )  # fmt: skip
        if verdict.sufficient:
            trace.rater_stop, trace.rules_short_at_stop = True, bool(short)
            return []
        named = [n for n in verdict.missing if n in work.slots and (work.only is None or n in work.only)]
        return short or named or [sw.name for sw in work.unfilled_required()] or [n for n, sw in work.slots.items() if sw.required]

    def _budget_hit(self, work: FactorWork) -> None:
        left = self._left(work.factor)
        short = [sw.name for sw in work.unfilled_required()]
        self._decision(
            "budget_hit", f"Budget of {work.factor.value} is spent; unfilled: {', '.join(short) or 'none'}.", factor=work.factor.value,
            budget_left=left.model_dump(), unfilled=short,
        )  # fmt: skip

    # -- driving all factors ------------------------------------------------------------------------

    def retrieve(self, state: CaseGraphState, factors: list[Factor] | None = None) -> list[EvidencePack]:
        """Picks the factors and retrieves evidence for the chosen ones (all, or only `factors`); packs in Appendix A order.

        Factors run in lock-step rounds: every factor's calls of a round run concurrently, the paragraphs they found are
        shared, then each factor is assessed and re-planned. That keeps a run reproducible.
        """
        shells = self.pick_factors(state)
        want = None if factors is None else {Factor(f) for f in factors}
        chosen = [p for p in shells if p.stance != FactorStance.NOT_APPLICABLE and (want is None or p.factor in want)]
        self._pool.clear()
        self._work.clear()
        plans = {p.factor: self.plan_factor(p.factor, state) for p in chosen}
        done = self._drive(plans)
        return [done[p.factor] for p in shells if p.factor in done]

    def _drive(self, plans: dict[Factor, RetrievalPlan]) -> dict[Factor, EvidencePack]:
        done: dict[Factor, EvidencePack] = {}
        while plans:
            order = [f for f in Factor if f in plans]
            outcomes = self.parallel(order, lambda f, current=plans: self.run_plan(current[f]))
            for f in order:  # the barrier: share what every factor found, in a fixed order
                self._pool_add(self._work[f].fresh)
            nxt: dict[Factor, RetrievalPlan] = {}
            for f, results in zip(order, outcomes, strict=False):
                assessed = self.assess(f, results)
                new = self.replan(plans[f], assessed)
                if new is None:
                    done[f] = self._finish(self._work[f])
                else:
                    nxt[f] = new
            plans = nxt
        return done

    def _finish(self, work: FactorWork) -> EvidencePack:
        """The factor's evidence pack: assessed slots, open issues, transfer flags on the best authorities."""
        with self.factor_scope(work.factor):
            self._attach_transfer(work)
        slots = []
        for name, sw in work.slots.items():
            slots.append(sw.result or SlotResult(slot=name, status=SlotStatus.MISSING, note="not retrieved"))
        issues = [t for sw in work.slots.values() if (t := open_issue(work, sw))]
        pack = EvidencePack(factor=work.factor, stance=work.stance, reason=work.reason, slots=slots, open_issues=issues)
        spent = getattr(self.budgets, "spent", None)
        sig = self._variant_signals(work, spent)
        if sig is not None:
            self.retrieval_signals[work.factor.value] = sig
            self._decision("retrieval_signals", f"{work.factor.value}: retrieval variant signals.", **sig)
        self._decision(
            "factor_done", f"{work.factor.value}: " + ", ".join(f"{k} {v}" for k, v in plan_assessment(work).items()), factor=work.factor.value,
            stopped=work.stopped, rounds=work.round, open_issues=issues, spent=list(spent(work.factor.value)) if spent else None,
        )  # fmt: skip
        return pack

    def _variant_signals(self, work: FactorWork, spent: Any) -> dict[str, Any] | None:
        """The per-factor signals of the active retrieval variants (S3 stopping, S1 critique); None when every one is off."""
        sw = self.switches
        if sw.stopping == "rules" and sw.retrieval_policy == "contract" and not sw.graph_expansion and sw.weak_signal == "rules" and sw.store_prior == "off":
            return None
        tokens, calls = spent(work.factor.value) if spent else (0, 0)
        sig: dict[str, Any] = signals_of(work, sw.stopping, int(calls), int(tokens)) if sw.stopping != "rules" else {"factor": work.factor.value}
        if sw.retrieval_policy == "self_critique":
            sig["retrieval_policy"] = sw.retrieval_policy
            sig["critique"] = critic.signals(work)
        if sw.weak_signal == "skew":
            t = work.skew
            sig["skew"] = {"scored_calls": t["scored_calls"], "weak_flags": t["weak_flags"], "downgrades": t["downgrades"], "calls": list(t["calls"])}
        if sw.graph_expansion:
            g = work.graph
            kept = [i for r in work.slots.values() if r.result for i in r.result.items if i.get("expanded")]
            sig["graph"] = {
                "expand_calls": g["calls"], "expansion_hits": g["hits"], "expansion_sc_hits": g["sc_hits"], "expanded_docs": sorted(g["docs"]),
                "expansion_hits_in_pack": len(kept),
            }  # fmt: skip
        if sw.retrieval_policy == "adaptive" and work.depth is not None:
            sig["retrieval_policy"] = sw.retrieval_policy
            sig["depth"] = depth_rules.signals(work, int(calls), int(tokens))
        if sw.store_prior == "order":
            from vakeel_sahayak.agents.sutradhar.store_prior import order_signals

            sig["store_prior"] = order_signals(work, self.store_prior_model(), int(calls))
        return sig

    def _attach_transfer(self, work: FactorWork) -> None:
        """Flag each top authority whose section was recodified (IPC/CrPC to BNS/BNSS) as SAME_TEXT, CHANGED or NEW (plan §5.4)."""
        sw = work.slots.get("authority")
        if sw is None or sw.result is None or not self.switches.retrieval_filters or not self.switches.uses_rule_tools:
            return
        pairs: list[tuple[str, str]] = []
        for s in work.sig.sections:
            ref, eq, code = s.get("ref"), s.get("equivalent"), str(s.get("code") or "").upper()
            if ref and eq:
                pairs.append((ref, eq) if code in ("IPC", "CRPC") else (eq, ref))
        if not pairs:
            return
        base = lambda r: re.sub(r"\([^)]*\)", "", str(r)).strip().upper()  # noqa: E731
        for it in [i for i in sw.result.items if i.get("para") is not None][:TRANSFER_LIMIT]:
            family = {base(r) for r in it.get("section_family") or []}
            pair = next(((o, n) for o, n in pairs if base(o) in family and base(n) not in family), None)
            if pair is None:
                continue
            if pair not in self._transfer:
                if self._left(work.factor).store_calls <= 0:
                    return
                res = self._tool("transfer_check", work.factor, old_ref=pair[0], new_ref=pair[1])
                if isinstance(res, ToolError):
                    self._transfer[pair] = {}
                    continue
                self._transfer[pair] = {"flag": getattr(res.flag, "value", res.flag), "qualification": res.qualification, "old_ref": pair[0], "new_ref": pair[1]}
            if self._transfer[pair]:
                it["transfer"] = self._transfer[pair]

    # ------------------------------------------------------------------ re-running factors

    def rerun_factors(self, state: CaseGraphState, factors: list[Factor]) -> CaseGraphState:
        """Re-pick the factors and re-run retrieval for only these (the rest of the packs are kept as they are).

        A factor that is no longer applicable loses its pack; one that has become applicable gets one.
        """
        want = [Factor(f) for f in factors]
        self._plans_log = []
        packs = self.retrieve(state, want)
        merged: dict[Factor, EvidencePack] = {p.factor: p for p in state.evidence_packs if p.factor not in want}
        for p in packs:
            merged[p.factor] = p
        for f in want:
            if self._stances[f][0] == FactorStance.NOT_APPLICABLE:
                merged.pop(f, None)
        ordered = [merged[f] for f in Factor if f in merged]
        out = self._with_packs(state, ordered, state.plans + self._plans_log)
        return out.model_copy(update={"reopened_factors": want})

    def reopen_after_change(self, state: CaseGraphState, change_set: ChangeSet) -> list[Factor]:
        """Re-run only affected factors (step 4; plan §10).

        The factors to reopen are the ones `truth_maintenance.factors_to_reopen` names, those that read a changed dossier
        field or Radar check, and those whose stance changed (a factor may become available, e.g. a charge sheet filed, or
        drop out). Their retrieval is re-run; the updated state is kept in `self.latest_state`.

        Args:
            state: see behaviour
            change_set: see behaviour

        Returns:
            Factors reopened, in Appendix A order.
        """
        affected: set[Factor] = set()
        try:
            from vakeel_sahayak.truth_maintenance.staleness import factors_to_reopen

            brief = state.brief or BailBrief(case_id=state.case_id)
            affected.update(Factor(f) for f in factors_to_reopen(brief, change_set))
        except NotImplementedError:
            pass
        for f in change_set.fields:
            affected.update(_CHANGED_FIELD_FACTORS.get(f.field, ()))
        for name in change_set.rights_changed:
            affected.update(_CHANGED_RIGHTS_FACTORS.get(str(name), ()))
        before = {p.factor: p.stance for p in state.evidence_packs}
        fresh = state
        if state.log_path is not None or getattr(self.log, "path", None) is not None:
            try:
                fresh = state.refresh_from_log()
            except Exception:  # noqa: BLE001
                fresh = state
        self._pctx = None
        now = {f: s for f, s, _ in pick_stances(self.plan_context(fresh).sig)}
        for f, stance in now.items():
            if f in before and before[f] != stance or f not in before and stance != FactorStance.NOT_APPLICABLE and state.evidence_packs:
                affected.add(f)
        ordered = [f for f in Factor if f in affected]
        self._decision("reopen", "Reopened: " + (", ".join(f.value for f in ordered) or "no factor"), factors=[f.value for f in ordered], trigger=change_set.trigger)
        if ordered:
            self.latest_state = self.rerun_factors(fresh, ordered)
        else:
            self.latest_state = state.model_copy(update={"reopened_factors": []})
        return ordered

    # ------------------------------------------------------------------ step 3: delegate

    def _peer(self, name: AgentName) -> BaseAgent:
        if name not in self._peers:
            from vakeel_sahayak.agents.registry import create_agent

            self._peers[name] = create_agent(name, self.ctx)
        return self._peers[name]

    def _peer_call(self, name: AgentName, method: str, *args: Any, default: Any = None) -> Any:
        """Call a method of another agent; one that is not built yet (NotImplementedError) is logged and skipped."""
        try:
            return getattr(self._peer(name), method)(*args)
        except NotImplementedError:
            self._decision("delegate_skipped", f"{name.value}.{method} is not available yet.", agent=name.value, method=method)
            return default

    def delegate(self, state: CaseGraphState, packs: list[EvidencePack]) -> CaseGraphState:
        """Hand packs to Vakeel; send draft to Abhiyojak; route objections back; decide re-retrieve vs reword on failed claims (step 3).

        Vakeel drafts and checks from the packs. A ground that failed its check goes through `resolve_failed_claim`: a new
        retrieval plan for the slot behind it, then Vakeel drafts again from the new pack, or Vakeel rewords. Then
        Abhiyojak's objections are routed to Vakeel for replies, and Abhiyojak judges the replies. An agent that is not
        built yet is skipped and logged, so Sutradhar stays callable on its own. A10 stops after retrieval (no drafting).

        Args:
            state: see behaviour
            packs: see behaviour

        Returns:
            Updated state.
        """
        state = state.model_copy(update={"evidence_packs": list(packs)})
        if not self.switches.drafting:
            self._decision("delegate_skipped", "Retrieval only in this run (A10): nothing is drafted.", agent=AgentName.VAKEEL.value)
            return state
        self._decision("delegate", "Evidence packs handed to Vakeel.", agent=AgentName.VAKEEL.value, factors=[p.factor.value for p in packs])
        out = self._peer_call(AgentName.VAKEEL, "run", state, default=None)
        if out is not None:
            state = out
        state = self._handle_failed_claims(state)
        if self.switches.sparring and state.brief is not None and state.brief.grounds:
            state = self._spar(state)
        return state

    def _handle_failed_claims(self, state: CaseGraphState) -> CaseGraphState:
        brief = state.brief
        if brief is None:
            return state
        redo = False
        for g in brief.grounds:
            if g.check != ClaimCheck.NEEDS_REVIEW:
                continue
            decision = self.resolve_failed_claim(state, g.factor, "claim needs review", claim_id=g.id, bad_docs=[f"{a.doc_id}" for a in g.authorities if a.good_law.value == "OVERRULED"])
            if decision.decision == "re-retrieve" and decision.pack is not None:
                state = state.model_copy(update={"evidence_packs": [decision.pack if p.factor == g.factor else p for p in state.evidence_packs]})
                redo = True
        if redo:
            out = self._peer_call(AgentName.VAKEEL, "run", state, default=None)
            if out is not None:
                state = out
        return state

    def _spar(self, state: CaseGraphState) -> CaseGraphState:
        """Abhiyojak raises objections, they go back to Vakeel for replies, Abhiyojak judges the replies (plan §9)."""
        objections = self._peer_call(AgentName.ABHIYOJAK, "raise_objections", state, default=None)
        if objections is None:
            return state
        replies = self._peer_call(AgentName.VAKEEL, "reply_to_objections", state, objections, default=None)
        if replies is None:
            return state
        self._decision("route_objections", f"{len(objections)} objection(s) routed back to Vakeel.", count=len(objections))
        paired = [o.model_copy(update={"reply": r}) for o, r in zip(objections, replies, strict=False)] + list(objections[len(replies):])
        judged = self._peer_call(AgentName.ABHIYOJAK, "judge_replies", state, paired, default=None)
        if judged is None:
            return state
        record = SparringRecord(case_id=state.case_id, rounds=2, objections=judged, discarded=list(state.sparring.discarded) if state.sparring else [])
        self.write_view("sparring", record)
        return state.model_copy(update={"sparring": record})

    def resolve_failed_claim(
        self, state: CaseGraphState, factor: Factor, reason: str, *, claim_id: str | None = None, bad_docs: list[str] | None = None
    ) -> ClaimDecision:
        """A claim failed its check: re-retrieve (a new plan for the slot behind it) or let Vakeel reword (plan §6.2 step 3).

        Re-retrieve when the factor's pack still has a required slot short, or when the failure is about the authority
        (not supported by the cited paragraph, overruled, not retrieved); the failing documents are not offered again.
        Reword when the evidence is in the pack and the claim overstates it (fact support, wording).

        Returns:
            ClaimDecision; `pack` holds the new evidence pack when a re-retrieval ran.
        """
        factor = Factor(factor)
        pack = next((p for p in state.evidence_packs if p.factor == factor), None)
        short = [s.slot for s in (pack.slots if pack else []) if s.status != SlotStatus.FILLED and s.slot in contract_for(factor).slots and contract_for(factor).slots[s.slot].need != "optional"]
        about_authority = bool(re.search(r"authorit|citation|cited|overrul|retriev|good[- ]law|paragraph", reason, re.IGNORECASE)) or bool(bad_docs)
        if pack is not None and (short or about_authority) and self._left(factor).tokens > 0 and self._left(factor).store_calls > 0:
            slots = short or [n for n in ("authority", "conditions") if n in contract_for(factor).slots][:1]
            new_pack = self._reretrieve(state, factor, slots, set(bad_docs or []))
            decision = ClaimDecision("re-retrieve", f"new retrieval plan for {', '.join(slots)}: {reason}", factor, slots, new_pack)
        else:
            decision = ClaimDecision("reword", f"the evidence is in the pack; Vakeel rewords the claim to what it supports: {reason}", factor)
        self._decision("failed_claim", decision.reason, factor=factor.value, claim=claim_id, decision=decision.decision, slots=decision.slots)
        return decision

    def _reretrieve(self, state: CaseGraphState, factor: Factor, slots: list[str], avoid: set[str]) -> EvidencePack | None:
        """A new plan for the slots behind a failed claim: reworded, never built on the failing documents again."""
        pctx = self._context_for(state)
        work = self._new_work(factor, pctx, adaptive=False)  # a failed claim gets the full loop
        work.only, work.avoid = set(slots), set(avoid)
        pack = next((p for p in state.evidence_packs if p.factor == factor), None)
        for r in pack.slots if pack else []:
            sw = work.slots.get(r.slot)
            if sw is not None and r.slot not in slots:
                sw.result, sw.items, sw.pending = r, list(r.items), False
        with self.factor_scope(factor):
            for name in slots:
                sw = work.slots.get(name)
                if sw is None or sw.source is None:
                    continue
                sw.items = [i for i in sw.items if str(i.get("doc_id")) not in avoid]
                self._reword(work, sw)
                sw.done.add("reword_claim")
        self._work[factor] = work
        plan = self._build_plan(work, 1)
        return self._drive({factor: plan}).get(factor)

    # ------------------------------------------------------------------ chat (plan §6.4)

    def answer_chat(self, state: CaseGraphState, question: str) -> ChatMessage:
        """Route a counsel question to the right store or tool and answer briefly with citations; refuse outcome predictions and lay advice (plan §6.4).

        The answer is a few cited sentences composed from the tool results (`[F:field]` a dossier fact, `[E:event]` a
        timeline event, `[A:doc#para]` an authority, `[D:doc p.N]` a case document, `[R:check]` a Rights Radar entry), with a
        chip for every store or tool used. An outcome prediction or a request for advice from the accused or their family
        is refused (`refused=True`); lay advice is pointed to NALSA, 15100.

        Args:
            state: see behaviour
            question: see behaviour

        Returns:
            ChatMessage.
        """
        key = classify_question(question)
        message_id = f"msg-{len(state.chat) + 1}"

        def reply(text: str, chips: list[ToolChip] | None = None, refused: bool = False) -> ChatMessage:
            if not refused and prediction_language(text):
                text, chips, refused = "I do not predict outcomes or quote past success figures, so I have left that out.", [], True
            return ChatMessage(message_id=message_id, case_id=self.case_id, role="agent", agent=AgentName.SUTRADHAR, text=text, chips=chips or [], refused=refused)

        if key in (REFUSE_PREDICTION, REFUSE_ADVICE):
            lay = key == REFUSE_ADVICE or is_lay_advice(question)
            self._decision("chat_refused", "Refused a question.", kind=key, tools=[])
            text = "I do not predict whether bail will be granted and I do not quote success figures. I can show where the case stands on each factor, the precedents and the State's usual objections."
            if lay:
                text = (
                    "I work for counsel and cannot advise an accused person or their family, or say what will happen to an application. "
                    f"Free legal aid is available: call NALSA on {NALSA_HELPLINE} or ask the District Legal Services Authority."
                )
            return reply(text, refused=True)
        route = key or "case_docs"
        tools = list(CHAT_ROUTES.get(key or "", ["search_case_docs"]))
        self._decision("chat_route", f"Routed to {', '.join(tools)}.", intent=route, tools=tools)
        self._last_state = state
        sig = self._signals(state)
        pctx = self._context_for(state)
        handler = {
            "custody_days": self._chat_custody, "section_equivalent": self._chat_section, "eligibility": self._chat_rights,
            "precedent_search": self._chat_precedent, "what_did_court_say": self._chat_docs, "how_state_opposes": self._chat_objections,
        }.get(key or "", self._chat_docs)  # fmt: skip
        with self.factor_scope(None):
            text, chips = handler(state, question, sig, pctx)
        return reply(text, chips)

    @staticmethod
    def _chip(tool: str) -> ToolChip:
        return ToolChip(tool=tool, store=TOOL_STORES.get(tool))

    @staticmethod
    def _problem(res: Any) -> str:
        kind = res.kind if isinstance(res, ToolError) else ""
        if kind == "disabled_by_switch":
            return "that tool is switched off in this run, so I cannot check it"
        if kind == "store_unavailable":
            return "the store it needs is unavailable in this run"
        return (res.message if isinstance(res, ToolError) else "nothing came back")[:160]

    def _chat_custody(self, state: CaseGraphState, question: str, sig: CaseSignals, pctx: PlanContext) -> tuple[str, list[ToolChip]]:
        chips = [self._chip("get_timeline")]
        events = self._tool("get_timeline", None, case_id=self.case_id)
        arrest, cite = sig.arrest_date, "[F:arrest_date]"
        if isinstance(events, list):
            hit = next((e for e in events if re.search(r"arrest", e.label, re.IGNORECASE)), None)
            if arrest is None and hit is not None:
                arrest, cite = str(hit.date), f"[E:{hit.event_id}]"
        if not arrest:
            return "The papers do not give a date of arrest, so I cannot count the days in custody. Please confirm the date.", chips
        chips.append(self._chip("date_calc"))
        res = self._tool("date_calc", None, start=str(arrest), end=pctx.as_of, rule="CALENDAR_DAYS_BETWEEN")
        if isinstance(res, ToolError):
            return f"Arrest was on {arrest} {cite}; I could not count the days: {self._problem(res)}.", chips
        return f"{res.value} days in custody: from the arrest on {arrest} {cite} to {pctx.as_of}, counted by date_calc.", chips

    @staticmethod
    def _section_in(question: str) -> tuple[str, str] | None:
        """The (code, section) a question names, however it is written: '420 IPC', 'IPC 420', 'section 420 of the IPC'."""
        code_re, sec_re = r"(IPC|BNSS|BNS|Cr\.?\s?P\.?\s?C\.?)", r"(\d+[A-Za-z]{0,2}(?:\([0-9A-Za-z]+\))*)"
        for pattern, order in (
            (rf"(?<![\w(]){sec_re}\s*{code_re}(?![A-Za-z])", ("sec", "code")),
            (rf"(?<![A-Za-z]){code_re}\s+(?:s(?:ection|ec)?\.?\s*)?{sec_re}", ("code", "sec")),
            (rf"s(?:ection|ec)?\.?\s*{sec_re}\D{{0,15}}?{code_re}", ("sec", "code")),
        ):
            m = re.search(pattern, question, re.IGNORECASE)
            if m:
                parts = dict(zip(order, m.groups(), strict=True))
                from vakeel_sahayak.pipelines.concordance.refs import normalise_code

                try:
                    return normalise_code(parts["code"]), parts["sec"].upper()
                except ValueError:
                    continue
        return None

    def _chat_section(self, state: CaseGraphState, question: str, sig: CaseSignals, pctx: PlanContext) -> tuple[str, list[ToolChip]]:
        from vakeel_sahayak.pipelines.concordance.refs import parse_ref

        chips = [self._chip("map_section")]
        code, section = self._section_in(question) or parse_ref(question)
        if section and not code:
            known = [s for s in sig.sections if str(s.get("ref", "")).split(" ")[-1].startswith(section)]
            code = str(known[0]["code"]) if known else None
        if not code or not section:
            return "Which section do you mean? Give it with its code, for example '420 IPC'.", chips
        dossier = state.dossier
        offence = (dossier.fields.offence_date.value if dossier else None) or sig.arrest_date or pctx.as_of
        res = self._tool("map_section", None, code=code, section=section, offence_date=str(offence))
        if isinstance(res, ToolError):
            return f"I could not map {code} {section}: {self._problem(res)}.", chips
        if res.ambiguous:
            return f"{code} {section} could map to more than one section: {', '.join(res.candidates)}. Counsel should choose.", chips
        edge = f" ({res.edge_type.value})" if res.edge_type else ""
        governing = f" The law governing an offence on {offence} is {res.governing}." if res.governing else ""
        return f"{code} {section} corresponds to {res.equivalent or 'no section'} in the new code{edge}.{governing}", chips

    def _chat_rights(self, state: CaseGraphState, question: str, sig: CaseSignals, pctx: PlanContext) -> tuple[str, list[ToolChip]]:
        chips = [self._chip("rights_check")]
        res = self._tool("rights_check", None, case_id=self.case_id, as_of=pctx.as_of)
        if isinstance(res, ToolError):
            return f"I could not run the Rights Radar: {self._problem(res)}.", chips
        pick = next((name for rx, name in (
            (r"479|436\s?a|undertrial", "undertrial_limit"), (r"default", "default_bail"), (r"antil", "antil_category"),
            (r"bar|37|43d|45", "statutory_bar"), (r"24|produc", "production_24h"), (r"ground", "grounds_of_arrest"),
        ) if re.search(rx, question, re.IGNORECASE)), None)  # fmt: skip
        checks = [c for c in res.checks if pick is None or c.check.value == pick] or list(res.checks)
        parts = []
        for c in checks[:3] if pick else [c for c in checks if c.status.value not in ("NOT_APPLICABLE",)][:4]:
            rule = f" Rule: {c.rule}." if c.rule else ""
            parts.append(f"{c.check.value.replace('_', ' ')}: {c.status.value}. {c.detail or ''}{rule} [R:{c.check.value}]".replace("  ", " "))
        return " ".join(parts) or "The Rights Radar has no entry for that.", chips

    def _chat_precedent(self, state: CaseGraphState, question: str, sig: CaseSignals, pctx: PlanContext) -> tuple[str, list[ToolChip]]:
        chips = [self._chip("search_reasoning")]
        args: dict[str, Any] = {"query": question, "before": pctx.before, "k": 5}
        if pctx.family:
            args["section_family"] = pctx.family
        res = self._tool("search_reasoning", None, **args)
        if isinstance(res, ToolError):
            return f"I could not search the precedents: {self._problem(res)}.", chips
        rows = [r for r in res if str(getattr(r.part, "value", r.part)) == "reasoning" and r.date < pctx.before][:3]
        widened = ""
        if not rows and "section_family" in args:
            widened = " (widened beyond the case's sections)"
            args.pop("section_family")
            res = self._tool("search_reasoning", None, **args)
            rows = [r for r in (res if isinstance(res, list) else []) if str(getattr(r.part, "value", r.part)) == "reasoning" and r.date < pctx.before][:3]
        if not rows:
            return "I found no court reasoning on that before the date of this case.", chips
        chips.append(self._chip("citations"))
        law = self._tool("citations", None, doc_ids=list(dict.fromkeys(r.doc_id for r in rows)), want=["good_law"])
        flags = {}
        if isinstance(law, dict):
            for d, rec in law.items():
                g = rec.get("good_law") if isinstance(rec, dict) else None
                flags[d] = getattr(getattr(g, "status", None), "value", None) or "UNKNOWN"
        lines = [f"[A:{r.doc_id}#{r.para}] {r.court}, {r.date}: {r.text.strip()[:140]}... (good law: {flags.get(r.doc_id, 'UNKNOWN')})" for r in rows]
        return f"Found{widened}: " + " ".join(lines), chips

    def _chat_docs(self, state: CaseGraphState, question: str, sig: CaseSignals, pctx: PlanContext) -> tuple[str, list[ToolChip]]:
        chips = [self._chip("search_case_docs")]
        res = self._tool("search_case_docs", None, case_id=self.case_id, query=question, k=3)
        if isinstance(res, ToolError):
            return f"I could not search the case file: {self._problem(res)}.", chips
        if not res:
            return "The case file has nothing on that.", chips
        lines = [f"[D:{c.doc_id} p.{c.page}] \"{(c.text_en or c.text).strip()[:160]}\"" for c in res[:2]]
        return "The file says: " + " ".join(lines), chips

    def _chat_objections(self, state: CaseGraphState, question: str, sig: CaseSignals, pctx: PlanContext) -> tuple[str, list[ToolChip]]:
        chips = [self._chip("search_objections")]
        args: dict[str, Any] = {"query": question, "before": pctx.before, "k": 3}
        if pctx.family:
            args["section_family"] = pctx.family
        res = self._tool("search_objections", None, **args)
        parts = []
        if isinstance(res, list) and res:
            parts.append("The State has argued: " + " ".join(f"[O:{r.doc_id}#{r.para}] {r.text.strip()[:140]}..." for r in res[:2]))
        elif isinstance(res, ToolError):
            parts.append(f"I could not search the objection bank: {self._problem(res)}.")
        else:
            parts.append("No recorded objection matches before the date of this case.")
        chips.append(self._chip("get_statute"))
        from vakeel_sahayak.pipelines.concordance.refs import split_ref

        for s in sig.sections[:1]:
            try:
                code, section = split_ref(s["ref"])
            except (ValueError, KeyError):
                continue
            st = self._tool("get_statute", None, code=code, section=section)
            if not isinstance(st, ToolError):
                parts.append(f"[S:{st.code} {st.section}] {st.text.strip()[:140]}...")
        return " ".join(parts), chips


def jsonable_pack(pack: EvidencePack) -> dict[str, Any]:
    """An evidence pack as plain JSON (for the trace and the UI)."""
    return jsonable(pack)
