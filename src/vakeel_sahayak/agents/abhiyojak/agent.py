"""Abhiyojak agent (plan §3.2, §9). Prosecution sparring with its own prompt and context; sees only drafted grounds, dossier and its own stores. Qwen3-14B on Ada.

What it does, in order (every decision is an event with actor ABHIYOJAK):

1. **context**: the input is built by `isolation.build_context` from an allow-list (drafted grounds with their cited
   authorities, the dossier facts, the charged sections). Vakeel's plan and notes and Sutradhar's plan never reach it:
   no method reads the state any other way, and `assert_allowed` rejects such keys at runtime;
2. **round 1** (`raise_objections`): per ground it searches its own stores (`search_objections`, refusal reasoning in
   `search_reasoning`, `get_statute` for the charged sections) and asks for at most two objections, then the general
   ones (gravity, flight risk, witness tampering, antecedents, statutory bars). An objection is kept only when it cites an
   objection-bank paragraph, a refusal-reasoning paragraph, a statute or a dossier fact that was actually offered;
   the rest are discarded and logged (and counted in `SparringRecord.discarded`);
3. **replies**: Vakeel answers each objection (`VakeelAgent.reply_to_objections`) under its own citation and checking
   rules;
4. **round 2** (`judge_replies`): each reply is judged ANSWERED, PARTLY or UNANSWERED with a reason; an UNANSWERED one is
   flagged NEEDS_REVIEW for counsel (an open issue of the brief). Two rounds, no more.

Switches: A8 and A9 (no sparring) return an empty record with a log line. `list_objections_one_call(state)` is the
B-style baseline of eval F1: one ungrounded model call listing the prosecution's likely objections.

Abhiyojak is callable on its own, with fakes:

    agent = AbhiyojakAgent(case_id="case-0007", log=log, before="2024-03-01", tools=fakes)
    state = agent.run(CaseGraphState(case_id="case-0007", brief=brief, dossier=dossier))
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from vakeel_sahayak.agents.abhiyojak import offline  # noqa: F401  (importing `offline` registers the offline handlers)
from vakeel_sahayak.agents.abhiyojak.isolation import ContextIsolationError, assert_allowed, build_context
from vakeel_sahayak.agents.abhiyojak.prompts import (
    SYSTEM_PROMPT,
    TASK_JUDGE,
    TASK_LIST,
    TASK_RAISE,
    JudgedReply,
    RaisedObjection,
    RaisedObjections,
    instructions,
)
from vakeel_sahayak.agents.base import AgentContext, BaseAgent, prediction_language
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.orchestration.budgets import BudgetExhausted
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.orchestration.structured_output import StructuredOutputError
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.bail_brief import OpenIssue
from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.enums import AgentName, ClaimCheck, EventKind, Factor, OpenIssueType, SparringVerdict
from vakeel_sahayak.schemas.sparring import Objection, ObjectionGround, Reply, SparringRecord
from vakeel_sahayak.tools.base import ToolError

MAX_ROUNDS = 2  # plan §9: two rounds, no more
MAX_PER_GROUND = 2  # plan §9: up to two objections per ground
MAX_PER_GENERAL = 1  # one objection on each general factor
GENERAL_FACTORS: tuple[str, ...] = ("gravity_and_punishment", "flight_risk", "witness_tampering", "antecedents", "statutory_bar")
BANK, REFUSALS, STATUTES = "advocacy.objections", "caselaw.reasoning", "law.statutes"
BANK_K, REFUSAL_K, MAX_STATUTES = 4, 3, 3
PARAGRAPH_LIMIT = 1500  # characters of a paragraph shown to the model
REFUSAL_OUTCOME = "rejected"  # the `outcome` value of refusal orders in caselaw.reasoning
_MARKER = re.compile(r"\[(?:F|A):[^\]]+\]")
_FACT_STORES = (None, "", "case.facts", "dossier", "case", "fact")


@dataclass
class Material:
    """What Abhiyojak's own stores returned for one factor: the only things an objection may rest on."""

    bank: list[dict[str, Any]] = field(default_factory=list)
    refusals: list[dict[str, Any]] = field(default_factory=list)
    statutes: list[dict[str, Any]] = field(default_factory=list)

    def offered(self) -> dict[str, set[Any]]:
        """Ids of what was offered, by store."""
        return {
            BANK: {(r["doc_id"], r["para"]) for r in self.bank},
            REFUSALS: {(r["doc_id"], r["para"]) for r in self.refusals},
            STATUTES: {f"{r['code']} {r['section']}".strip() for r in self.statutes},
        }


class AbhiyojakAgent(BaseAgent):
    """Prosecution sparring with its own prompt and context; sees only drafted grounds, dossier and its own stores (plan §9). Qwen3-14B on Ada."""

    NAME = AgentName.ABHIYOJAK
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
        tools: dict[str, Any] | None = None,
        cases_dir: str | None = None,
        before: str | None = None,
        replier: Callable[[CaseGraphState, list[Objection]], list[Reply]] | None = None,
        max_rounds: int | None = None,
    ) -> None:
        """Create Abhiyojak, from an AgentContext or from plain arguments (the graph is optional).

        Args:
            ctx: the injected context (case id, log, budget, switches, LLM, toolbox)
            case_id: the case (needed when there is no context)
            log: the case's event log (default: the configured per-case log)
            switches: ablation switches (A8 and A9 are read here)
            llm: the `agents_14b` client
            tools: a toolbox that replaces the registry's tools (fakes in tests)
            cases_dir: cases folder for the event log
            before: the case's order date when the graph state carries none (the stores only show earlier documents)
            replier: `fn(state, objections) -> list[Reply]`, how the objections are answered (default: Vakeel's
                `reply_to_objections`, through a peer agent sharing this context)
            max_rounds: rounds of sparring, at most 2 (plan §9)
        """
        if ctx is None:
            if not case_id:
                raise ValueError("Abhiyojak needs a case_id or an AgentContext")
            ctx = AgentContext(case_id=case_id, log=log, switches=switches or Switches(), llm=llm, tools=dict(tools or {}), cases_dir=cases_dir, before=before)
        super().__init__(ctx)
        self.replier = replier
        self._max_rounds = MAX_ROUNDS if max_rounds is None else max(1, min(int(max_rounds), MAX_ROUNDS))
        self._vakeel: BaseAgent | None = None
        self._reset()

    @property
    def max_rounds(self) -> int:
        """Rounds of sparring (never more than 2: plan §9)."""
        return self._max_rounds

    def _reset(self) -> None:
        self._discarded: list[str] = []
        self._statute_cache: dict[tuple[str, str], dict[str, Any] | None] = {}
        self._count = 0

    @property
    def discarded(self) -> list[str]:
        """The ungrounded objections discarded by the last round 1."""
        return list(self._discarded)

    # ------------------------------------------------------------------ small plumbing

    def _decision(self, tool: str, text: str = "", **outputs: Any) -> None:
        """One event for a decision (actor ABHIYOJAK; tool `retrieve`, `objection`, `discard`, `reply`, `verdict`, `flag`, ...)."""
        self.emit(EventKind.AGENT_MESSAGE, {"tool": tool, "outputs": {"type": tool, "text": text, **outputs}})

    def _tool(self, name: str, **kwargs: Any) -> Any:
        """call_tool, with a refused or failed call coming back as a ToolError rather than an exception."""
        from vakeel_sahayak.tools.registry import ToolPermissionError

        try:
            return self.call_tool(name, **kwargs)
        except ToolPermissionError as exc:
            return ToolError(tool=name, kind="permission_denied", message=str(exc), retryable=False)
        except BudgetExhausted as exc:
            return ToolError(tool=name, kind="budget", message=str(exc), retryable=False)

    def _safe_ask(self, task: str, instruction: str, *, factor: Any = None, **kw: Any) -> Any:
        """`ask`, with a spent budget, a model that cannot answer or a refused payload coming back as None (logged, never silent)."""
        try:
            return self.ask(task, instruction, factor=factor, **kw)
        except (BudgetExhausted, StructuredOutputError, ModelUnavailable, PrivacyBoundaryError) as exc:
            self._decision("model_failed", f"{task} could not be answered: {type(exc).__name__}", task=task, error=type(exc).__name__)
            return None

    def _before(self, state: CaseGraphState, as_of: str | None = None) -> str:
        """The order date the stores are searched before: the state's, else the context's, else the dossier's as-of date, else today."""
        from datetime import date

        return state.before or getattr(self.ctx, "before", None) or as_of or state.as_of or date.today().isoformat()

    def guard(self, payload: Any) -> None:
        """The runtime guard: refuse a payload that carries Vakeel's or Sutradhar's private keys (logged, then raised)."""
        try:
            assert_allowed(payload)
        except ContextIsolationError as exc:
            self._decision("isolation_refused", str(exc))
            raise

    # ------------------------------------------------------------------ own stores

    @staticmethod
    def _rows(res: Any) -> list[dict[str, Any]]:
        """Paragraph rows of a search result (a ToolError or anything else is no rows)."""
        if isinstance(res, ToolError) or not isinstance(res, (list, tuple)):
            return []
        out = []
        for r in res:
            d = r if isinstance(r, dict) else getattr(r, "model_dump", lambda **_: {})(mode="json")
            if d.get("doc_id") and isinstance(d.get("para"), int) and not isinstance(d.get("para"), bool):
                out.append({"doc_id": str(d["doc_id"]), "para": int(d["para"]), "text": str(d.get("text") or "")[:PARAGRAPH_LIMIT], "outcome": d.get("outcome")})
        return out

    def _statute(self, code: str, section: str) -> dict[str, Any] | None:
        key = (code, section)
        if key not in self._statute_cache:
            res = self._tool("get_statute", code=code, section=section)
            if isinstance(res, ToolError) or res is None:
                self._statute_cache[key] = None
            else:
                d = res if isinstance(res, dict) else res.model_dump(mode="json")
                self._statute_cache[key] = {k: d.get(k) for k in ("code", "section", "text", "max_punishment", "bailable")} | {"text": str(d.get("text") or "")[:600]}
        return self._statute_cache[key]

    def _material(self, factor: str, query: str, before: str | None, sections: list[dict[str, Any]]) -> Material:
        """The objection bank, refusal reasoning and statutes of the case for one factor (what an objection may rest on)."""
        mat = Material()
        fac = Factor(factor)
        with self.factor_scope(fac):
            self._search(mat, fac, query, before)
            for sec in sections[:MAX_STATUTES]:
                if row := self._statute(str(sec["code"]), str(sec["section"])):
                    mat.statutes.append(row)
        for rows in (mat.bank, mat.refusals):
            for r in rows:
                r["factors"] = [factor]
        self._log_material(mat, factor)
        return mat

    def _search(self, mat: Material, fac: Factor, query: str, before: str | None) -> None:
        factor = fac.value
        if before:
            mat.bank = self._rows(self._tool("search_objections", query=query, factor=fac, before=before, k=BANK_K))
            mat.refusals = self._rows(self._tool("search_reasoning", query=query, factor=fac, before=before, outcome=REFUSAL_OUTCOME, k=REFUSAL_K))
        else:
            self._decision("retrieve_skipped", "The case has no order date to search before: the bank and refusal reasoning are not searched.", factor=factor)

    def _log_material(self, mat: Material, factor: str) -> None:
        self._decision(
            "retrieve", f"{factor}: {len(mat.bank)} bank paragraph(s), {len(mat.refusals)} refusal paragraph(s), {len(mat.statutes)} statute(s).",
            factor=factor, bank=[f"{r['doc_id']}#{r['para']}" for r in mat.bank], refusals=[f"{r['doc_id']}#{r['para']}" for r in mat.refusals],
            statutes=[f"{r['code']} {r['section']}" for r in mat.statutes],
        )  # fmt: skip

    @staticmethod
    def _merged(parts: list[Material]) -> Material:
        """One Material from several (a paragraph found for two factors keeps both factors; statutes are listed once)."""
        out = Material()
        for part in parts:
            for rows, into in ((part.bank, out.bank), (part.refusals, out.refusals)):
                for r in rows:
                    same = next((x for x in into if (x["doc_id"], x["para"]) == (r["doc_id"], r["para"])), None)
                    if same is None:
                        into.append(dict(r))
                    else:
                        same["factors"] = [*same["factors"], *[f for f in r["factors"] if f not in same["factors"]]]
            out.statutes += [r for r in part.statutes if (r["code"], r["section"]) not in {(x["code"], x["section"]) for x in out.statutes}]
        return out

    def _corpus(self, mat: Material) -> dict[str, Any]:
        def wrap(r: dict[str, Any]) -> dict[str, Any]:
            return {**r, "text": self.untrusted(r["text"], SourceRef(doc=f"{r['doc_id']}#{r['para']}"))}

        return {"objection_bank": [wrap(r) for r in mat.bank], "refusals": [wrap(r) for r in mat.refusals], "statutes": mat.statutes}

    # ------------------------------------------------------------------ round 1

    @staticmethod
    def _query(ground: dict[str, Any] | None, factor: str) -> str:
        label = factor.replace("_", " ")
        if not ground:
            return f"prosecution objection to bail: {label}"
        text = re.sub(r"\s+", " ", _MARKER.sub("", str(ground.get("argument") or ""))).strip()
        return f"{label}: {text[:300]}"

    def _grounded(
        self, raw: RaisedObjection, mat: Material, facts: dict[str, Any], where: str
    ) -> tuple[list[ObjectionGround], list[str]]:
        """The grounds of a raised objection that were actually offered (store paragraph, statute, dossier fact), and the refs dropped."""
        offered = mat.offered()
        kept: list[ObjectionGround] = []
        dropped: list[str] = []
        for g in raw.grounds:
            label = f"{g.store or '-'}:{g.doc_id or g.fact}#{g.para}"
            if g.fact:
                if g.store in _FACT_STORES and g.fact in facts:
                    kept.append(ObjectionGround(fact=g.fact))
                else:
                    dropped.append(label)
                continue
            store = g.store
            if store in (None, "") and g.doc_id:  # a model that leaves the store out: the one store that holds it
                hits = [s for s, ids in offered.items() if ((g.doc_id, g.para) in ids if g.para is not None else g.doc_id in ids)]
                store = hits[0] if len(hits) == 1 else None
            if store in (BANK, REFUSALS) and g.doc_id and g.para is not None and (g.doc_id, g.para) in offered[store]:
                kept.append(ObjectionGround(store=store, doc_id=g.doc_id, para=g.para))
            elif store == STATUTES and g.doc_id and g.doc_id in offered[STATUTES]:
                kept.append(ObjectionGround(store=STATUTES, doc_id=g.doc_id))
            else:
                dropped.append(label)
        if dropped:
            self._decision("ground_dropped", f"{where}: reference(s) to material that was not offered were dropped.", refs=dropped)
        return kept, dropped

    def _raise_for(
        self, against: str, factor: str | None, ground: dict[str, Any] | None, mat: Material, facts: dict[str, Any], limit: int, seen: set[Any]
    ) -> list[Objection]:
        """One model call for a ground (factor given) or for the general objections (factor None): validated, grounded objections, ids not yet assigned."""
        scope = Factor(factor) if factor else None
        case = {"ground": ground, "factor": factor or "general", "factors": [] if factor else list(GENERAL_FACTORS), "against": against, "limit": limit, "facts": list(facts.values())}
        self.guard(case)
        with self.factor_scope(scope):
            out = self._safe_ask(
                TASK_RAISE, instructions(TASK_RAISE, limit=limit, factor=factor or "general"), factor=scope, case=case,
                corpus=self._corpus(mat), schema=RaisedObjections, max_tokens=900 if factor is None else 700,
            )  # fmt: skip
        # An answer for several grounds at once is read for this call's part only (an objection that names no ground is this one's).
        raised = [r for r in getattr(out, "objections", None) or [] if r.against in (None, "", against)]
        if factor is None:
            raised = [r for r in raised if r.factor in GENERAL_FACTORS]
        if len(raised) > limit:
            self._decision("truncated", f"{against}: {len(raised)} objections raised, only {limit} kept (plan §9).", against=against)
            raised = raised[:limit]
        kept: list[Objection] = []
        per_factor: dict[str, int] = {}
        for raw in raised:
            text = re.sub(r"\s+", " ", unwrapped(raw.objection)).strip()
            fac = factor or str(raw.factor)
            where = f"{against}/{fac}"
            if not text:
                continue
            if factor is None and per_factor.get(fac, 0) >= MAX_PER_GENERAL:
                self._decision("truncated", f"{where}: one objection per general factor.", against=against, factor=fac)
                continue
            grounds, _ = self._grounded(raw, mat, facts, where)
            if not grounds:
                self._discarded.append(f"{where}: {text}")
                self._decision("discard", f"{where}: objection discarded, it cites no objection-bank paragraph, refusal reasoning, statute or dossier fact that was offered.", against=against, factor=fac, objection=text[:300])
                continue
            if prediction_language(text):
                self._discarded.append(f"{where}: {text}")
                self._decision("discard", f"{where}: objection discarded, it predicts an outcome.", against=against, factor=fac, objection=text[:300])
                continue
            sig = (fac, tuple(sorted((g.store or "", g.doc_id or "", g.para or 0, g.fact or "") for g in grounds)))
            if sig in seen:
                self._decision("duplicate", f"{where}: an objection on the same grounds was already raised.", against=against, factor=fac)
                continue
            seen.add(sig)
            per_factor[fac] = per_factor.get(fac, 0) + 1
            kept.append(Objection(id="", against=against, factor=fac, objection=text, grounds=grounds))
        return kept

    def raise_objections(self, state: CaseGraphState) -> list[Objection]:
        """Round 1: up to two objections per ground plus general ones (gravity, flight risk, witness tampering, antecedents, statutory bars); discard and log ungrounded ones.

        Args:
            state: see behaviour

        Returns:
            Objections (ids O1, O2, ...). The ungrounded ones discarded on the way are in `self.discarded`.
        """
        ctx = build_context(state)  # the only way this agent reads the state (plan §9 isolation)
        facts: dict[str, Any] = ctx["dossier"]
        sections: list[dict[str, Any]] = ctx["sections"]
        before = self._before(state, ctx["as_of"])
        self._discarded = []
        out: list[Objection] = []
        seen: set[Any] = set()
        self._decision("round_1", f"Round 1: {len(ctx['grounds'])} ground(s) and the general objections.", grounds=[g["id"] for g in ctx["grounds"]], context_keys=sorted(ctx), stores=ctx["stores"])
        valid = {f.value for f in Factor}
        for g in ctx["grounds"]:
            factor = str(g.get("factor") or "")
            if not g.get("id") or factor not in valid or not str(g.get("argument") or "").strip():
                self._decision("ground_skipped", f"Ground {g.get('id')} has no argument to object to.", ground=g.get("id"))
                continue
            mat = self._material(factor, self._query(g, factor), before, sections)
            view = {k: g[k] for k in ("id", "factor", "stance", "argument", "authorities")}
            out += self._raise_for(str(g["id"]), factor, view, mat, facts, MAX_PER_GROUND, seen)
        parts = [self._material(f, self._query(None, f), before, sections) for f in GENERAL_FACTORS]
        out += self._raise_for("general", None, None, self._merged(parts), facts, len(GENERAL_FACTORS) * MAX_PER_GENERAL, seen)
        objections = []
        for o in out:
            self._count += 1
            o = o.model_copy(update={"id": f"O{self._count}"})
            objections.append(o)
            self._decision("objection", f"{o.id} against {o.against} ({o.factor}) raised.", objection=o.id, against=o.against, factor=o.factor, grounds=[g.model_dump(mode="json", exclude_none=True) for g in o.grounds])
        self._decision("round_1_done", f"Round 1: {len(objections)} objection(s) kept, {len(self._discarded)} discarded as ungrounded.", kept=len(objections), discarded=len(self._discarded))
        return objections

    # ------------------------------------------------------------------ replies and round 2

    def _replies(self, state: CaseGraphState, objections: list[Objection]) -> list[Reply]:
        """Vakeel's replies, in order (the replier given, else a VakeelAgent sharing this context)."""
        replier = self.replier
        if replier is None:
            if self._vakeel is None:
                import dataclasses

                from vakeel_sahayak.agents.registry import create_agent

                # Vakeel shares the case's log, budget, tools and switches but resolves its own model (its own prompt, its own client).
                self._vakeel = create_agent(AgentName.VAKEEL, dataclasses.replace(self.ctx, llm=None))
            replier = self._vakeel.reply_to_objections  # type: ignore[attr-defined]
        replies = list(replier(state, objections))
        self._decision("replies", f"Vakeel answered {len(replies)} of {len(objections)} objection(s).", answered=len(replies), objections=len(objections))
        return replies

    def judge_replies(self, state: CaseGraphState, objections: list[Objection]) -> list[Objection]:
        """Round 2: mark each reply ANSWERED, PARTLY or UNANSWERED with a reason; UNANSWERED goes to counsel as NEEDS_REVIEW.

        Args:
            state: see behaviour
            objections: see behaviour

        Returns:
            Objections with verdicts.
        """
        self._decision("round_2", f"Round 2: judging {len(objections)} repl(ies).", objections=[o.id for o in objections])
        judged: list[Objection] = []
        for o in objections:
            judged.append(self._judge_one(o))
        counts = {v.value: sum(1 for o in judged if o.verdict == v) for v in SparringVerdict}
        self._decision("round_2_done", "Round 2 done: " + ", ".join(f"{n} {k}" for k, n in counts.items()) + ".", **counts)
        return judged

    def _judge_one(self, o: Objection) -> Objection:
        reply = o.reply
        if reply is None or not reply.text.strip():
            return self._verdict(o, SparringVerdict.UNANSWERED, "There is no reply to this objection.")
        facts = [g.fact for g in o.grounds if g.fact]
        case = {
            "objection": self.untrusted(o.objection, SourceRef(doc=f"objection {o.id}")), "against": o.against, "factor": o.factor,
            "objection_facts": facts,
            "reply": {"text": self.untrusted(reply.text, SourceRef(doc=f"reply {o.id}")), "check": reply.check.value, "authorities": [f"{a.doc_id}#{a.para}" for a in reply.authorities]},
        }  # fmt: skip
        self.guard(case)
        factor = Factor(o.factor) if o.factor in {f.value for f in Factor} else None
        with self.factor_scope(factor):
            out = self._safe_ask(TASK_JUDGE, instructions(TASK_JUDGE), factor=factor, case=case, schema=JudgedReply, max_tokens=200)
        if out is None:
            return self._verdict(o, SparringVerdict.UNANSWERED, "The reply could not be judged; counsel to read it.")
        try:
            verdict = SparringVerdict(str(getattr(out, "verdict", "")).strip().upper())
        except ValueError:
            return self._verdict(o, SparringVerdict.UNANSWERED, "The judgement was not one of ANSWERED, PARTLY or UNANSWERED; counsel to read the reply.")
        return self._verdict(o, verdict, str(getattr(out, "reason", "") or "").strip() or None)

    def _verdict(self, o: Objection, verdict: SparringVerdict, reason: str | None) -> Objection:
        update: dict[str, Any] = {"verdict": verdict, "reason": reason}
        if verdict == SparringVerdict.UNANSWERED and o.reply is not None:
            update["reply"] = o.reply.model_copy(update={"check": ClaimCheck.NEEDS_REVIEW})  # goes to counsel
        self._decision("verdict", f"{o.id}: {verdict.value}.", objection=o.id, against=o.against, verdict=verdict.value, reason=reason)
        if verdict == SparringVerdict.UNANSWERED:
            self._decision("needs_review", f"{o.id} ({o.factor}) is unanswered: NEEDS_REVIEW for counsel.", objection=o.id, against=o.against)
        return o.model_copy(update=update)

    # ------------------------------------------------------------------ the whole exchange

    def spar(self, state: CaseGraphState) -> SparringRecord:
        """Run two rounds within budget.

        Args:
            state: see behaviour

        Returns:
            SparringRecord.
        """
        if not self.switches.sparring:
            self._decision("sparring_skipped", "No sparring in this run (A8/A9): an empty record.")
            return SparringRecord(case_id=state.case_id)
        objections = self.raise_objections(state)  # round 1
        discarded = list(self._discarded)
        if not objections:
            self._decision("no_objections", "No grounded objection could be raised: nothing to answer or judge.")
            return SparringRecord(case_id=state.case_id, rounds=1, objections=[], discarded=discarded)
        replies = self._replies(state, objections)
        objections = [o.model_copy(update={"reply": replies[i] if i < len(replies) else None}) for i, o in enumerate(objections)]
        rounds = 1
        if self.max_rounds >= 2:
            objections = self.judge_replies(state, objections)  # round 2
            rounds = 2
        record = SparringRecord(case_id=state.case_id, rounds=rounds, objections=objections, discarded=discarded)
        self._decision("record", f"Sparring record: {len(objections)} objection(s) over {rounds} round(s), {len(discarded)} discarded.", objections=len(objections), rounds=rounds, discarded=len(discarded))
        return record

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Abhiyojak's full job for the current graph state.

        Spars on the drafted brief (two rounds), writes the SparringRecord as a view, and adds each UNANSWERED objection
        to the brief's open issues as NEEDS_REVIEW. Under A8 and A9 the record is empty and nothing is written.

        Args:
            state: see behaviour

        Returns:
            Updated state: `sparring` (and `brief` with the new open issues).
        """
        self._reset()
        record = self.spar(state)
        update: dict[str, Any] = {"sparring": record}
        if record.objections:
            self.write_view("sparring", record)
            brief = self._flag_unanswered(state, record)
            if brief is not None:
                update["brief"] = brief
        snap = getattr(self.budgets, "snapshot", None)
        if snap is not None:
            update["budget"] = snap()
        to_dict = getattr(self.budgets, "to_dict", None)
        if to_dict is not None:
            update["budget_tracker"] = to_dict()
        return state.model_copy(update=update)

    def _flag_unanswered(self, state: CaseGraphState, record: SparringRecord) -> Any:
        """The brief with an open issue (NEEDS_REVIEW) for each unanswered objection; None when nothing changes."""
        brief = state.brief
        if brief is None:
            return None
        have = {i.item for i in brief.open_issues}
        issues = []
        for o in record.objections:
            if o.verdict != SparringVerdict.UNANSWERED:
                continue
            item = f"Objection {o.id} ({o.factor.replace('_', ' ')}) is unanswered: {o.objection}"
            if item not in have:
                issues.append(OpenIssue(type=OpenIssueType.NEEDS_REVIEW, item=item))
        if not issues:
            return None
        brief = brief.model_copy(update={"open_issues": [*brief.open_issues, *issues]})
        self.write_view("brief", brief)
        self._decision("flag", f"{len(issues)} unanswered objection(s) added to the brief's open issues for counsel.", objections=[o.id for o in record.objections if o.verdict == SparringVerdict.UNANSWERED])
        return brief

    # ------------------------------------------------------------------ eval F1 baseline

    def list_objections_one_call(self, state: CaseGraphState) -> list[Objection]:
        """B-style baseline of eval F1: one model call, "list the prosecution's likely objections", with no store, no grounding and no reply.

        Works under every switch (it is a baseline, not part of the pipeline). The objections come back with no grounds,
        `against` 'general' and ids B1, B2, ...

        Args:
            state: the graph state (only the dossier facts, or the raw facts text when there is no dossier, are read)

        Returns:
            Objections, ungrounded; empty when the model cannot answer.
        """
        ctx = build_context(state)
        facts = [ctx["dossier"][k] for k in ctx["dossier"]]
        case = {"facts": facts}
        self.guard(case)
        out = self._safe_ask(TASK_LIST, instructions(TASK_LIST), case=case, schema=RaisedObjections, max_tokens=700)
        valid = {f.value for f in Factor}
        result: list[Objection] = []
        for raw in list(getattr(out, "objections", None) or []):
            text = re.sub(r"\s+", " ", unwrapped(raw.objection)).strip()
            if text:
                factor = raw.factor if raw.factor in valid else "general"
                result.append(Objection(id=f"B{len(result) + 1}", against="general", factor=factor, objection=text))
        self._decision("one_call_list", f"One-call baseline: {len(result)} ungrounded objection(s) listed.", objections=len(result))
        return result


def unwrapped(text: str) -> str:
    """Text out of a `wrap_untrusted` block (a model may echo the markers)."""
    from vakeel_sahayak.agents.peshkar.fields import unwrap

    return unwrap(text)
