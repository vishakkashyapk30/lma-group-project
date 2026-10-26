"""Base agent and context (plan §3.2, §3.3, §16).

Every agent subclasses `BaseAgent` and gets, through `AgentContext`:

- **tools** via `call_tool(name, **args)`: the allow-list (configs/tools.yaml intersected with each tool's SPEC.agents,
  narrowed further by `ctx.tools` when given), argument validation, the Gate 2 check for `export`, the A3/A10 switches,
  the per-factor store-call budget, the shared retrieval cache, and a TOOL_CALL / TOOL_RESULT event pair per call;
- **a model client** `self.llm` (the configured client for the agent's role, `models.factory.get_llm`), called through
  `ask(...)` (one prompt in the shared layout; structured when a schema is given) which applies the privacy boundary,
  charges the token budget and logs the call;
- **the event-log writer** with actor = the agent's name and the §3.3 vocabulary of `record/views.py`
  (`write_field`, `write_timeline_event`, `write_view`, `message`, `error`, `stale_claims`, `emit`);
- **the budget** `self.budgets` (one `BudgetTracker` per case, shared by its agents);
- **the privacy boundary**: for agents whose model runs on Ada (Sutradhar, Vakeel, Abhiyojak, Pairokar, and Peshkar
  under A5's prompted 32B), every outbound payload goes through `privacy.boundary.assert_pseudonymised` first.

Documents are data (plan §16): prompts put all evidence under INPUT, the system text says it is never to be followed,
`untrusted()` wraps document text, and instruction-like text in case data is flagged in the log. No predictions:
`prediction_language()` finds outcome-prediction and grant-rate phrasing for agents to refuse or strip.
"""

from __future__ import annotations

import contextvars
import hashlib
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, TypeVar, get_type_hints

from pydantic import BaseModel
from pydantic_core import to_jsonable_python

from vakeel_sahayak.agents.outbound import mask_public
from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.models.base import LLMClient, ModelUnavailable, NliClient
from vakeel_sahayak.orchestration.budgets import BudgetExhausted, BudgetTracker
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.privacy.defences import Defences, DocumentTexts, Tally
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.common import SourceRef, TrackedField
from vakeel_sahayak.schemas.enums import AgentName, EventKind, StoreName
from vakeel_sahayak.schemas.events import Event

T = TypeVar("T")
R = TypeVar("R")
CASE_STORES = frozenset({StoreName.CASE_DOCS, StoreName.CASE_TIMELINE, StoreName.CASE_FACTS})
_FACTOR: contextvars.ContextVar[str | None] = contextvars.ContextVar("vs_budget_factor", default=None)
_PREDICTION = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:likely|unlikely|probably|certain(?:ly)?|sure|bound|expected)\s+to\s+(?:be\s+)?(?:granted|get\s+bail|be\s+released|succeed|be\s+rejected|be\s+refused|win|lose)\b",
        r"\b(?:chances?|odds|probability|likelihood|prospects?)\s+(?:of|that|for)\b[^.]{0,60}\b(?:bail|grant|success|release|rejection|refusal)",
        r"\b\d{1,3}(?:\.\d+)?\s?%\s*(?:of\s+)?(?:cases|applications|orders|grants?|success|rejections?)",
        r"\bgrant\s+rates?\b|\bsuccess\s+rates?\b|\brejection\s+rates?\b",
        r"\bwill\s+(?:definitely\s+|surely\s+|certainly\s+)?(?:be\s+granted|get\s+bail|be\s+released|be\s+acquitted)\b",
        r"\bguarantee[sd]?\b",
    )
]


def prediction_language(text: str) -> list[str]:
    """Outcome-prediction or grant-rate phrases in a text (plan §1.3, §16: the system never predicts outcomes).

    Args:
        text: generated text (an answer, a ground, a hearing-card line)

    Returns:
        The matching phrases, in order (empty when the text is clean).
    """
    return [m.group(0) for p in _PREDICTION for m in p.finditer(text or "")]


def jsonable(value: Any) -> Any:
    """A JSON-able copy of a tool result or payload (pydantic models dumped in JSON mode)."""
    return to_jsonable_python(value, fallback=str)


def _sources_of(result: Any, limit: int = 50) -> list[SourceRef]:
    """Sources to put on a TOOL_RESULT event: paragraph ids, case chunks' pages, timeline sources."""
    items = result if isinstance(result, list) else [result]
    out: list[SourceRef] = []
    for item in items[:limit]:
        doc_id, para = getattr(item, "doc_id", None), getattr(item, "para", None)
        if isinstance(item, BaseModel) and doc_id and isinstance(para, int):
            out.append(SourceRef(doc=f"{doc_id}#{para}"))
        elif isinstance(item, BaseModel) and doc_id and hasattr(item, "chunk_id"):
            out.append(SourceRef(doc=str(doc_id), page=getattr(item, "page", None), box=getattr(item, "box", None),
                                 lang=getattr(item, "lang", None), route=getattr(item, "route", None)))  # fmt: skip
        elif isinstance(getattr(item, "source", None), SourceRef):
            out.append(item.source)
    return out


def _walk_strings(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _walk_strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from _walk_strings(v, f"{path}[{i}]")


def _spent(budgets: Any, specific: str, factor: str | None, actor: Any = None) -> bool:
    """The tracker's narrow check (`store_calls_exhausted` / `tokens_exhausted`), else the general `exhausted(factor)` of a minimal budget.

    The actor is passed only to a check that takes one (the real tracker picks the retrieval or the drafting token pool by it).
    """
    import inspect

    check = getattr(budgets, specific, None) or budgets.exhausted
    if actor is not None and "actor" in inspect.signature(check).parameters:
        return bool(check(factor, actor=actor))
    return bool(check(factor))


def _charge(budgets: Any, factor: str | None, *, actor: Any, **spend: int) -> None:
    """Charge spend; the actor is passed only to trackers that take one (the real BudgetTracker logs it on a BUDGET_HIT)."""
    import inspect

    if "actor" in inspect.signature(budgets.charge).parameters:
        budgets.charge(factor, actor=actor, **spend)
    else:
        budgets.charge(factor, **spend)


@dataclass
class AgentContext:
    """Everything an agent needs, injected (plan §3.3).

    Only `case_id` is required; everything else defaults from the configuration. Agents of one case should share one
    context (one event log, one budget). Leave `llm` None so each agent gets the client of its own role.
    """

    case_id: str
    config: AppConfig | None = None
    log: EventLog | None = None
    budgets: BudgetTracker | None = None
    llm: LLMClient | None = None  # from models.factory.get_llm(role); None: each agent resolves its role
    switches: Switches = field(default_factory=Switches)
    tools: dict[str, Callable[..., Any]] = field(default_factory=dict)  # filtered by configs/tools.yaml; empty: the registry's tools
    nli: NliClient | None = None  # None: models.factory.get_nli()
    cache: Any = None  # shared retrieval cache (batch.cache) with key(factor, section_family, before, query), get, put
    cases_dir: str | None = None  # override of the cases folder (event log, alias map, case stores)
    before: str | None = None  # the case's order date: shared-store searches only see earlier documents (plan §2)

    def __post_init__(self) -> None:
        """Fill the defaults: config, the case's event log (shared with the tools), a budget bound to that log."""
        from vakeel_sahayak.schemas.ids import check_case_id

        check_case_id(self.case_id)
        if self.config is None:
            from vakeel_sahayak.config import load_config

            self.config = load_config()
        if self.log is None:
            if self.cases_dir:
                self.log = EventLog.for_case(self.case_id, self.cases_dir)
            else:
                from vakeel_sahayak.tools.runtime import get_runtime

                self.log = get_runtime().event_log(self.case_id)
        if self.budgets is None:
            self.budgets = BudgetTracker.from_config(self.config, log=self.log, case_id=self.case_id)
        elif getattr(self.budgets, "log", None) is None and hasattr(self.budgets, "bind"):  # duck-typed budgets (tests) need no binding
            self.budgets.bind(self.log, self.case_id)
        if self.switches is None:
            self.switches = Switches()
        if self.tools is None:
            self.tools = {}

    @classmethod
    def for_case(cls, case_id: str, **kwargs: Any) -> AgentContext:
        """A context for a case (keyword arguments are the fields)."""
        return cls(case_id=case_id, **kwargs)


class BaseAgent(ABC):
    """Abstract agent. Subclasses declare NAME and ROLE_MODEL, never import model libraries directly, and emit an Event for every tool call (plan §3.3)."""

    NAME: AgentName
    ROLE_MODEL: str  # key in configs/models.yaml; allowed tools come from configs/tools.yaml
    SYSTEM_PROMPT: str = ""  # the agent's system text (its prompts module); the data rule is appended by the prompt layout

    def __init__(self, ctx: AgentContext) -> None:
        """Bind the agent to its context.

        Args:
            ctx: see behaviour
        """
        self.ctx = ctx
        self.case_id = ctx.case_id
        self.config = ctx.config
        self.log = ctx.log
        self.budgets = ctx.budgets
        self.switches = ctx.switches
        self.tools = ctx.tools
        self.llm = ctx.llm if ctx.llm is not None else self._resolve_llm()
        self.nli = ctx.nli
        self._filer = None
        self._mapping = None
        self._sync_runtime()

    # ------------------------------------------------------------------ plumbing

    def _resolve_llm(self) -> LLMClient:
        from vakeel_sahayak.models.factory import get_llm

        return get_llm(self.model_role())

    def model_role(self) -> str:
        """The configs/models.yaml role this agent's model calls use (Peshkar follows A5's `extractor` switch)."""
        if getattr(self, "NAME", None) == AgentName.PESHKAR:
            return (getattr(self, "switches", None) or Switches()).extractor_role()
        return self.ROLE_MODEL

    @property
    def ada_side(self) -> bool:
        """True when this agent's model runs on Ada, so every outbound payload must be pseudonymised (plan §16)."""
        from vakeel_sahayak.models.factory import role_where

        try:
            where = role_where(self.model_role())
        except ValueError:
            where = "laptop"
        return where == "ada" or getattr(getattr(self, "llm", None), "where", "laptop") == "ada"

    def _sync_runtime(self) -> None:
        """Share this agent's log with the tools (they read gates and case state from the runtime's log)."""
        log, case_id = getattr(self, "log", None), getattr(self, "case_id", None)
        if log is None or not case_id:
            return
        from vakeel_sahayak.tools.runtime import get_runtime

        runtime = get_runtime()
        runtime.attach_log(case_id, log)
        runtime.current_case_id = case_id

    def get_nli(self) -> NliClient:
        """The NLI client (the context's, else the configured one)."""
        if getattr(self, "nli", None) is None:
            from vakeel_sahayak.models.factory import get_nli

            self.nli = get_nli()
        return self.nli  # type: ignore[return-value]

    @abstractmethod
    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run the agent's job for the current graph state.

        Args:
            state: see behaviour

        Returns:
            Updated state.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------ events

    def emit(self, kind: EventKind, payload: dict[str, Any]) -> Event:
        """Append an event to the log.

        Args:
            kind: see behaviour
            payload: keys `tool`, `inputs`, `outputs`, `sources` and `parent_id` fill those event fields; any other key
                goes into `outputs`. The log holds pseudonymised text only.

        Returns:
            The event.
        """
        known = {"tool", "inputs", "outputs", "sources", "parent_id"}
        outputs = dict(payload.get("outputs") or {})
        outputs.update({k: v for k, v in payload.items() if k not in known})
        sources = [s if isinstance(s, SourceRef) else SourceRef.model_validate(s) for s in payload.get("sources") or []]
        assert self.log is not None and self.case_id, "the agent has no event log bound"
        return self.log.append(
            Event(
                event_id="",
                case_id=self.case_id,
                ts="",
                kind=kind,
                actor=self.NAME,
                tool=payload.get("tool"),
                inputs=jsonable(payload.get("inputs") or {}),
                outputs=jsonable(outputs),
                sources=sources,
                parent_id=payload.get("parent_id"),
            )
        )

    def message(self, text: str, **outputs: Any) -> Event:
        """AGENT_MESSAGE for the live trace (plan §3.3 use 4)."""
        return self.emit(EventKind.AGENT_MESSAGE, {"outputs": {"text": text, **outputs}})

    def error(self, kind: str, message: str, *, tool: str | None = None, parent_id: str | None = None, **details: Any) -> Event:
        """ERROR event (never echoes document text: pass ids and kinds, not content)."""
        return self.emit(EventKind.ERROR, {"tool": tool, "parent_id": parent_id, "outputs": {"error": kind, "message": message, **details}})

    def write_view(self, view: str, value: Any, *, sources: list[SourceRef] | None = None, parent_id: str | None = None) -> Event:
        """STORE_WRITE of a whole-object view to case.views (record/views.py): 'ingestion_report', 'rights_report',
        'brief', 'sparring' are folded by the views; 'evidence_packs', 'retrieval_plan', 'list_of_dates',
        'hearing_card', 'change_set', 'triage_card', 'factor_decisions' are kept for the trace and the UI."""
        return self.emit(
            EventKind.STORE_WRITE,
            {"inputs": {"store": "case.views", "view": view}, "outputs": {"value": jsonable(value)}, "sources": sources or [], "parent_id": parent_id},
        )

    def _filer_for_writes(self):  # noqa: ANN202
        if getattr(self, "_filer", None) is None:
            from vakeel_sahayak.ingestion.filing import Filer

            assert self.log is not None and self.case_id
            self._filer = Filer(self.case_id, self.log, cases_dir=getattr(self.ctx, "cases_dir", None), actor=self.NAME)
        return self._filer

    def write_field(self, name: str, tracked: TrackedField[Any] | dict[str, Any]) -> None:
        """Write one dossier field to case.facts and log it (STORE_WRITE inputs {store: case.facts, field}, outputs {tracked}).

        Args:
            name: a DossierFields field name
            tracked: the {value, source, status} wrapper (a dict is validated as TrackedField)
        """
        value = tracked if isinstance(tracked, TrackedField) else TrackedField[Any].model_validate(tracked)
        self._filer_for_writes().put_field(name, value)

    def write_timeline_event(self, row: Any) -> None:
        """Upsert one TimelineEvent in case.timeline and log it (STORE_WRITE inputs {store: case.timeline}, outputs {event})."""
        from vakeel_sahayak.schemas.store_rows import TimelineEvent

        self._filer_for_writes().update_event(row if isinstance(row, TimelineEvent) else TimelineEvent.model_validate(row))

    def stale_claims(self, claim_ids: list[str], reason: str, *, change_set: Any = None, parent_id: str | None = None) -> Event:
        """CLAIM_STALED: these grounds are STALE until a newer brief replaces them (plan §10)."""
        outputs: dict[str, Any] = {"claim_ids": list(claim_ids), "reason": reason}
        if change_set is not None:
            outputs["change_set"] = jsonable(change_set)
        return self.emit(EventKind.CLAIM_STALED, {"outputs": outputs, "parent_id": parent_id})

    def close(self) -> None:
        """Close the case stores opened for writes."""
        if getattr(self, "_filer", None) is not None:
            self._filer.close()
            self._filer = None

    def case_state(self):  # noqa: ANN201
        """record.case_state.CaseState over this case's log (dossier, timeline, rights report, brief, sparring views)."""
        from vakeel_sahayak.record.case_state import CaseState

        return CaseState(self.case_id, self.log)

    # ------------------------------------------------------------------ privacy and documents-as-data

    def pseudonyms(self):  # noqa: ANN201
        """The case's alias map (laptop only; used to check outbound payloads, never sent)."""
        if getattr(self, "_mapping", None) is None:
            from vakeel_sahayak.privacy.pseudonymise import load_map

            self._mapping = load_map(self.case_id, getattr(self.ctx, "cases_dir", None))
        return self._mapping

    def guard_outbound(self, payload: dict[str, Any], public: Any = None) -> None:
        """Apply the privacy boundary to a payload bound for an Ada-side model (no-op for laptop agents).

        The case-derived part goes through `privacy.boundary.assert_pseudonymised` with the case's alias map. Public
        corpus text (court orders, statutes: plan §16 "public test data") is checked only for this case's real names,
        since published orders legitimately name judges and counsel.

        Args:
            payload: everything case-derived (instructions, case data, tool arguments)
            public: public corpus data in the same call

        Raises:
            PrivacyBoundaryError: something must not leave the laptop (the message names paths, never the text).
        """
        if not self.ada_side:
            return
        from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError, assert_pseudonymised

        mapping = self.pseudonyms()
        try:
            assert_pseudonymised(jsonable(payload), mapping=mapping)
            if public is not None:
                names = mapping.known_names()
                pats = [re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, n.split())) + r"(?!\w)", re.IGNORECASE) for n in names]
                bad = [p for p, s in _walk_strings(jsonable(public), "public") if any(r.search(s) for r in pats)]
                if bad:
                    raise PrivacyBoundaryError("payload is not safe to send to Ada: " + "; ".join(f"{b}: raw name from the alias map" for b in bad[:10]))
        except PrivacyBoundaryError as exc:
            self.error("privacy_boundary", str(exc))
            raise

    # ------------------------------------------------------------------ injection defences (S17 / A15; privacy/defences.py)

    def defences(self) -> Defences:
        """Which injection defences are on (all three unless an S17 arm switched one off)."""
        return Defences.from_switches(getattr(self, "switches", None))

    def _defence_state(self) -> tuple[DocumentTexts, Tally]:
        """The agent's tracked document texts and defence counters, created on first use (Munshi does not call `BaseAgent.__init__`)."""
        state = self.__dict__.get("_vs_defence")
        if state is None:
            state = (DocumentTexts(), Tally())
            self.__dict__["_vs_defence"] = state
        return state

    def untrusted(self, text: str, source: SourceRef | dict[str, Any] | None = None) -> str:
        """Wrap document text as data for a prompt (privacy.injection_guard.wrap_untrusted); S17b `no_spotlighting` passes it unmarked."""
        from vakeel_sahayak.privacy.injection_guard import wrap_untrusted

        texts, tally = self._defence_state()
        texts.add(text)
        if not self.defences().spotlighting:
            tally.unmarked += 1
            return text
        tally.wrapped += 1
        src = source if isinstance(source, SourceRef) else SourceRef.model_validate(source or {})
        wrapped = wrap_untrusted(text, src)
        for k in range(1, 9):  # the delimiter tag is a hash prefix: one with a long run of digits reads as a phone number to the privacy boundary and would block the call
            tag = re.search(r"UNTRUSTED_DOCUMENT_DATA (\w+)>>>", wrapped)
            if tag is None or not re.search(r"[6-9]\d{9}|\d{12}", tag.group(1)):
                break
            wrapped = wrap_untrusted(text, src.model_copy(update={"doc": f"{src.doc or 'unknown'}{'.' * k}"}))
        return wrapped

    def flag_instructions(self, data: Any, where: str = "case") -> list[str]:
        """Log (without the text) every path in `data` whose text looks like an instruction to the model (plan §16, T7). S17c `no_guard` only counts them."""
        from vakeel_sahayak.privacy.injection_guard import detect_instruction_like

        _, tally = self._defence_state()
        paths = [p for p, s in _walk_strings(data, where) if detect_instruction_like(s)]
        if not self.defences().guard:
            tally.missed += len(paths)
            return []
        tally.flagged_paths += len(paths)
        if paths:
            self.emit(EventKind.AGENT_MESSAGE, {"outputs": {"type": "injection_flag", "paths": paths[:50],
                      "text": "Instruction-like text found in document data; it is treated as data and not followed."}})  # fmt: skip
        return paths

    def _handoff(self, instructions: str, case: Any, extra: Any) -> str:
        """Typed hand-off (S17a): the instruction text never carries document text.

        On (default): a tracked document text found in the instructions is removed and logged (no effect on any current prompt).
        Off (`no_typed_handoff`): the document texts of this call are copied into the instruction channel as free text, as a naive pipeline would.
        """
        from vakeel_sahayak.privacy.defences import with_free_text, without_document_text

        texts, tally = self._defence_state()
        if len(texts) == 0:
            return instructions
        if self.defences().typed_handoff:
            cleaned, removed = without_document_text(instructions, texts.all())
            if removed:
                tally.purged += removed
                self.emit(EventKind.AGENT_MESSAGE, {"outputs": {"type": "typed_handoff", "action": "removed document text from the instructions", "texts": removed}})
            return cleaned
        used = texts.in_data({"c": jsonable(case), "x": jsonable(extra)})
        if used:
            tally.spliced += len(used)
            self.emit(EventKind.AGENT_MESSAGE, {"outputs": {"type": "typed_handoff_off", "action": "document text copied into the instructions", "texts": len(used)}})
        return with_free_text(instructions, used)

    def _prefix_meter(self) -> Any:
        """The prefix meter: shared by every agent of a batch through the retrieval cache, else by the agents of one context."""
        from vakeel_sahayak.models.prefix import PrefixMeter

        holder = getattr(getattr(self, "ctx", None), "cache", None)
        if holder is None:
            holder = getattr(self, "ctx", None) or self
        try:
            return holder.__dict__.setdefault("_prefix_meter", PrefixMeter())
        except AttributeError:  # a holder without a __dict__ (slots): this agent keeps its own
            return self.__dict__.setdefault("_prefix_meter", PrefixMeter())

    def prefix_signals(self) -> dict[str, float]:
        """Prompt tokens and the tokens shared with earlier prompts of the same task (S14d: `shared_prefix_tokens`); measured under either layout."""
        return self._prefix_meter().stats()

    def injection_signals(self) -> dict[str, Any]:
        """Defence counters of this agent and which defences are off (S17 signals; counts only)."""
        _, tally = self._defence_state()
        return {"off": self.defences().off, **tally.as_dict()}

    def _with_injection(self, state: CaseGraphState) -> CaseGraphState:
        """Add `variant_signals['injection']` to a state, only when an S17 arm is running (default states are unchanged)."""
        if self.defences().all_on:
            return state
        mine = {**state.variant_signals.get("injection", {}), self.NAME.value: self.injection_signals()}
        return state.model_copy(update={"variant_signals": {**state.variant_signals, "injection": mine}})

    @staticmethod
    def prediction_language(text: str) -> list[str]:
        """Outcome-prediction or grant-rate phrases in `text` (see the module function)."""
        return prediction_language(text)

    # ------------------------------------------------------------------ budget scope and parallel work

    @contextmanager
    def factor_scope(self, factor: Any) -> Iterator[None]:
        """Charge the tool and LLM calls made inside this block to `factor` (per-factor budgets, plan §6.2)."""
        token = _FACTOR.set(None if factor is None else str(getattr(factor, "value", factor)))
        try:
            yield
        finally:
            _FACTOR.reset(token)

    @staticmethod
    def current_factor() -> str | None:
        """The factor the current block is charged to, if any."""
        return _FACTOR.get()

    def parallel(self, items: Iterable[T], fn: Callable[[T], R], max_workers: int = 4) -> list[R]:
        """Run `fn` over items concurrently (independent factors or calls, plan §6.2 step 2); results in input order.

        Each task runs in a copy of the caller's context, so a `factor_scope` set inside `fn` stays with that task.
        """
        work = list(items)
        if len(work) <= 1 or max_workers <= 1:
            return [fn(x) for x in work]
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(contextvars.copy_context().run, fn, x) for x in work]
            return [f.result() for f in futures]

    # ------------------------------------------------------------------ tools

    def allowed_tools(self) -> list[str]:
        """Tool names this agent may call (configs/tools.yaml ∩ SPEC.agents, narrowed by ctx.tools when given)."""
        from vakeel_sahayak.tools.registry import tools_for_agent

        names = [s.name for s in tools_for_agent(self.NAME)]
        toolbox = getattr(self, "tools", None) or {}
        if toolbox:
            names = [n for n in names if n in toolbox] + [n for n in toolbox if n not in names and not self._is_registry_tool(n)]
        return [n for n in names if self.switches.tool_allowed(n)]

    @staticmethod
    def _is_registry_tool(name: str) -> bool:
        from vakeel_sahayak.tools.registry import discover_tools

        return name in discover_tools()

    def call_tool(self, name: str, *, budget_factor: Any = None, **kwargs: Any) -> Any:
        """Call a registered tool: check it is allowed, charge the budget, append TOOL_CALL and TOOL_RESULT events.

        Args:
            name: the tool's name (plan §4.3-§8)
            budget_factor: the factor this call is charged to (default: the enclosing `factor_scope`, else the case)
            kwargs: the tool's arguments

        Returns:
            The tool's typed result, or a ToolError (invalid arguments, a store failure, a refused call: A3 rule
            tools, an A10 knocked-out store, a spent factor budget, a privacy-boundary refusal).

        Raises:
            ToolPermissionError: the agent may not call this tool.
            GateNotApproved: `export` without counsel's Gate 2 approval for this case.
        """
        from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError
        from vakeel_sahayak.record.gates import GateNotApproved, assert_export_allowed
        from vakeel_sahayak.tools.base import ToolError
        from vakeel_sahayak.tools.registry import (
            ToolArgumentError,
            ToolPermissionError,
            check_permission,
            discover_tools,
            get_tool,
            validate_args,
        )

        factor = None if budget_factor is None else str(getattr(budget_factor, "value", budget_factor))
        factor = factor or _FACTOR.get()
        spec = discover_tools().get(name)
        toolbox = getattr(self, "tools", None) or {}
        try:
            if toolbox and name not in toolbox:
                raise ToolPermissionError(f"{self.NAME.value} may not call {name} (not in its toolbox)")
            if spec is not None:
                check_permission(self.NAME, name)
            elif name not in toolbox:
                raise ToolPermissionError(f"unknown tool {name!r}")
        except ToolPermissionError as exc:
            self.error("permission_denied", str(exc), tool=name)
            raise

        def refuse(kind: str, message: str, retryable: bool = False) -> ToolError:
            err = ToolError(tool=name, kind=kind, message=message, retryable=retryable)
            self.emit(EventKind.TOOL_RESULT, {"tool": name, "inputs": {"refused": True}, "outputs": {"error": err.model_dump()}})
            return err

        switches = getattr(self, "switches", None) or Switches()
        if not switches.tool_allowed(name):
            return refuse("disabled_by_switch", f"{name} is switched off in this run (A3: the model judges this itself)")
        if spec is not None and any(not switches.store_allowed(s) for s in spec.stores):
            return refuse("store_unavailable", f"{switches.knockout_store} is knocked out in this run (A10)")
        clean = dict(kwargs)
        if spec is not None:
            try:
                clean = validate_args(name, kwargs)
            except ToolArgumentError as exc:
                return refuse("invalid_args", exc.message, retryable=True)
        clean = {k: v for k, v in clean.items() if k in kwargs}  # the tool's own defaults apply to the rest
        args_log = jsonable(clean)
        try:
            self.guard_outbound({"tool": name, "args": args_log})
        except PrivacyBoundaryError as exc:  # already logged as an ERROR event
            return ToolError(tool=name, kind="privacy_boundary", message=str(exc), retryable=False)
        if spec is not None and spec.gated:
            case_id = clean.get("case_id")
            try:
                if not case_id:
                    raise ToolArgumentError(name, "a gated tool needs a case_id")
                assert_export_allowed(self.log if case_id == self.case_id else self._log_of(case_id), case_id)
            except GateNotApproved as exc:
                self.error("gate_not_approved", str(exc), tool=name)
                raise
        store_call = bool(spec and spec.stores)
        budgets = getattr(self, "budgets", None)
        if store_call and budgets is not None and _spent(budgets, 'store_calls_exhausted', factor):
            return refuse("budget_exhausted", f"the store-call budget of {factor or 'the case'} is spent")
        charge = {"factor": factor, "store_calls": 1, "tokens": 0} if store_call else None
        arg_source = clean.get("source")  # a tool that files or cites something names where it came from: the audit trail shows it on the call and the result
        arg_sources = [arg_source] if isinstance(arg_source, (SourceRef, dict)) and arg_source else []
        call_ev = self.emit(EventKind.TOOL_CALL, {"tool": name, "inputs": args_log, "outputs": {"budget_charge": charge} if charge else {}, "sources": arg_sources})
        if charge and budgets is not None:
            _charge(budgets, factor, actor=self.NAME, store_calls=1)
        self._sync_runtime()
        cache, cache_key = self._cache_lookup(name, spec, clean, factor)
        if cache_key is not None and (hit := cache.get(cache_key)) is not None:
            result = self._rehydrate(name, hit)
            self.emit(EventKind.TOOL_RESULT, {"tool": name, "outputs": {"result": jsonable(result), "cached": True},
                                             "sources": _sources_of(result), "parent_id": call_ev.event_id})  # fmt: skip
            return result
        func = toolbox.get(name) or get_tool(name)
        try:
            result = func(**clean)
        except (ToolPermissionError, GateNotApproved) as exc:
            self.error(type(exc).__name__, str(exc), tool=name, parent_id=call_ev.event_id)
            raise
        except ToolArgumentError as exc:
            result = ToolError(tool=name, kind="invalid_args", message=exc.message, retryable=True)
        except ModelUnavailable as exc:
            result = ToolError(tool=name, kind="model_unavailable", message=str(exc), retryable=False)
        except NotImplementedError as exc:  # a tool whose builder is still a stub (none in the default run: the Phase 5 DOCX builders are implemented)
            result = ToolError(tool=name, kind="not_implemented", message=str(exc) or f"{name} is not implemented yet", retryable=False)
        except Exception as exc:  # noqa: BLE001 - tool crashes come back as errors the agent can recover from (plan §15.8)
            result = ToolError(tool=name, kind="tool_failed", message=f"{type(exc).__name__}: {exc}", retryable=True)
        if isinstance(result, ToolError):
            self.emit(EventKind.TOOL_RESULT, {"tool": name, "outputs": {"error": result.model_dump()}, "parent_id": call_ev.event_id})
            return result
        if cache_key is not None:
            cache.put(cache_key, result)
        self.emit(EventKind.TOOL_RESULT, {"tool": name, "outputs": {"result": jsonable(result)}, "sources": _sources_of(result) or arg_sources, "parent_id": call_ev.event_id})
        return result

    def _log_of(self, case_id: str) -> EventLog:
        from vakeel_sahayak.tools.runtime import get_runtime

        return get_runtime().event_log(case_id)

    def _cache_lookup(self, name: str, spec: Any, args: dict[str, Any], factor: str | None) -> tuple[Any, str | None]:
        """The shared retrieval cache and this call's key (shared stores only; key: factor, section family, before-date month, query)."""
        cache = getattr(getattr(self, "ctx", None), "cache", None)
        if cache is None or spec is None or not spec.stores or any(StoreName(s) in CASE_STORES for s in spec.stores):
            return None, None
        before = str(args.get("before") or "")[:7]  # the month (plan §11)
        family = sorted(str(x) for x in (args.get("section_family") or []))
        query = name + ":" + hashlib.sha256(repr(sorted((k, repr(v)) for k, v in jsonable(args).items())).encode()).hexdigest()[:16]
        query = f"{args.get('query') or ''}|{query}"
        try:
            return cache, cache.key(args.get("factor") or factor or "", family, before, query)
        except Exception:  # noqa: BLE001 - a cache that cannot key this call is simply not used
            return None, None

    @staticmethod
    def _rehydrate(name: str, value: Any) -> Any:
        """A cached value as the tool's return type (a persistent cache may hand back plain JSON)."""
        if isinstance(value, (BaseModel, list)) and (not isinstance(value, list) or not value or isinstance(value[0], BaseModel)):
            return value
        from pydantic import TypeAdapter

        from vakeel_sahayak.tools.registry import get_tool

        try:
            hint = get_type_hints(get_tool(name)).get("return")
            return TypeAdapter(hint).validate_python(value) if hint is not None else value
        except Exception:  # noqa: BLE001
            return value

    # ------------------------------------------------------------------ model calls

    def system_prompt(self) -> str:
        """The agent's system text."""
        return self.SYSTEM_PROMPT or (
            f"You are {self.NAME.value.title()}, one of the agents of a bail-preparation system for legal-aid counsel in "
            "Indian High Courts. You never predict outcomes or give grant rates, and you never advise accused persons."
        )

    def build_prompt(self, task: str, instructions: str, *, case: Any = None, corpus: Any = None, schema: Any = None, extra: dict[str, Any] | None = None) -> str:
        """The prompt for one call in the shared layout (`models.prompting.render_prompt`).

        Args:
            task: dotted task id, e.g. 'vakeel.draft_ground' (offline handlers are registered under it)
            instructions: static instructions (no document text)
            case: private, pseudonymised case data (dossier fields, case chunks, grounds)
            corpus: public data (paragraphs, statutes, objection-bank rows)
            schema: pydantic model class or JSON schema of the reply (structured calls)
            extra: further top-level input keys

        Returns:
            The prompt.
        """
        from vakeel_sahayak.models.json_schema import schema_of
        from vakeel_sahayak.models.prompting import render_prompt

        data: dict[str, Any] = {"case": jsonable(case) if case is not None else {}, "corpus": jsonable(corpus) if corpus is not None else {}}
        if extra:
            data.update(jsonable(extra))
        return render_prompt(task, instructions, data, system=self.system_prompt(), schema=schema_of(schema) if schema is not None else None,
                             prefix_friendly=bool(getattr(self.switches, "prefix_layout", False)))

    def ask(
        self,
        task: str,
        instructions: str,
        *,
        case: Any = None,
        corpus: Any = None,
        schema: Any = None,
        extra: dict[str, Any] | None = None,
        factor: Any = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        retries: int = 2,
    ) -> Any:
        """One model call: privacy boundary, token budget, structured validation and repair, an AGENT_MESSAGE llm_call event.

        Args:
            task: dotted task id (see `build_prompt`)
            instructions: static instructions
            case: private case data (checked by the privacy boundary for Ada-side agents)
            corpus: public corpus data
            schema: pydantic model class or JSON schema; None for free text
            extra: further input keys (treated as case data for the boundary)
            factor: the factor to charge (default: the enclosing `factor_scope`)
            max_tokens: completion limit per attempt
            temperature: 0.0 for reproducible runs
            retries: repair attempts for structured calls

        Returns:
            A validated model instance or JSON value (schema given), else the text.

        Raises:
            BudgetExhausted: the factor's or the case's token budget is spent.
            PrivacyBoundaryError: the payload is not safe to send to Ada.
            StructuredOutputError: no valid reply after the repairs.
            ModelUnavailable: the model cannot run (VS_MODELS=real without the backend).
        """
        from vakeel_sahayak.orchestration.structured_output import StructuredOutputError, structured_call

        fkey = None if factor is None else str(getattr(factor, "value", factor))
        fkey = fkey or _FACTOR.get()
        if corpus is not None and self.ada_side:
            corpus = mask_public(jsonable(corpus))  # PII in public rows is masked, so the boundary does not refuse the call
        self.flag_instructions({"case": jsonable(case), "extra": jsonable(extra)} if extra else jsonable(case))
        instructions = self._handoff(instructions, case, extra)
        self.guard_outbound({"system": self.system_prompt(), "instructions": instructions, "case": case, "extra": extra}, public=corpus)
        budgets = getattr(self, "budgets", None)
        if budgets is not None and _spent(budgets, 'tokens_exhausted', fkey, self.NAME):
            raise BudgetExhausted(f"token budget of {fkey or 'the case'} is spent", "factor" if fkey else "case", fkey, "tokens")
        prompt = self.build_prompt(task, instructions, case=case, corpus=corpus, schema=schema, extra=extra)
        shared = self._prefix_meter().observe(task, prompt)  # S14d signal: tokens shared with an earlier prompt of this task (in memory; an event only under the variant)
        if getattr(self.switches, "prefix_layout", False):
            self.emit(EventKind.AGENT_MESSAGE, {"outputs": {"type": "prefix_signals", "task": task, "shared_prefix_tokens": shared}})
        attempts, value = 1, None
        try:
            if schema is not None:
                res = structured_call(self.llm, prompt, schema, max_tokens=max_tokens, temperature=temperature, retries=retries)
                value, p_tok, c_tok, attempts = res.value, res.prompt_tokens, res.completion_tokens, res.attempts
            else:
                done = self.llm.complete(prompt, max_tokens=max_tokens, temperature=temperature)
                value, p_tok, c_tok = done.text, done.prompt_tokens, done.completion_tokens
        except StructuredOutputError as exc:
            p_tok = self.llm._count(prompt) * exc.attempts if hasattr(self.llm, "_count") else 0
            self._log_llm(task, fkey, prompt, p_tok, 0, exc.attempts, ok=False)
            self.error("structured_output", str(exc)[:500], task=task)
            raise
        except ModelUnavailable as exc:
            tried = (getattr(self.llm, "fallbacks", None) or [])[-1:]  # a FallbackLLM: why the hosted client did not answer first
            self.error("model_unavailable", str(exc), task=task, **({"primary_failed": tried[0]} if tried else {}))
            raise
        self._log_llm(task, fkey, prompt, p_tok, c_tok, attempts, ok=True, value=value)
        return value

    def _log_llm(self, task: str, factor: str | None, prompt: str, p_tok: int, c_tok: int, attempts: int, *, ok: bool, value: Any = None) -> None:
        """Charge the budget and append the llm_call AGENT_MESSAGE (token counts and hashes, not the prompt itself)."""
        charge = {"factor": factor, "tokens": int(p_tok) + int(c_tok), "store_calls": 0}
        budgets = getattr(self, "budgets", None)
        if budgets is not None:
            _charge(budgets, factor, actor=self.NAME, tokens=charge["tokens"])
        out_text = value.model_dump_json() if isinstance(value, BaseModel) else str(jsonable(value))
        engine = getattr(self.llm, "last_engine", None)  # a FallbackLLM: which client answered (the hosted primary, or the local fallback and why)
        fell_back = engine is not None and engine is not getattr(self.llm, "primary", engine)
        self.emit(
            EventKind.AGENT_MESSAGE,
            {
                "inputs": {"type": "llm_call", "task": task, "role": self.model_role(), "factor": factor},
                "outputs": {
                    **({"fallback": (getattr(self.llm, "fallbacks", None) or [{}])[-1]} if fell_back else {}),
                    "model": (getattr(engine, "model_id", None) or getattr(engine, "name", None)) if fell_back else (getattr(self.llm, "model_id", None) or getattr(self.llm, "name", type(self.llm).__name__)),
                    "offline": bool(getattr(self.llm, "is_offline", False)),
                    "prompt_tokens": int(p_tok), "completion_tokens": int(c_tok), "attempts": attempts, "ok": ok,
                    "prompt_hash": "h:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
                    "output_hash": "h:" + hashlib.sha256(out_text.encode("utf-8")).hexdigest()[:12] if ok else None,
                    "budget_charge": charge,
                },
            },
        )  # fmt: skip

    def generate_text(self, prompt: str, *, task: str = "raw", factor: Any = None, max_tokens: int = 1024, temperature: float = 0.0) -> str:
        """A raw-prompt call (the whole prompt is checked by the privacy boundary as case data). Prefer `ask`."""
        fkey = None if factor is None else str(getattr(factor, "value", factor))
        fkey = fkey or _FACTOR.get()
        self.guard_outbound({"prompt": prompt})
        budgets = getattr(self, "budgets", None)
        if budgets is not None and _spent(budgets, 'tokens_exhausted', fkey, self.NAME):
            raise BudgetExhausted(f"token budget of {fkey or 'the case'} is spent", "factor" if fkey else "case", fkey, "tokens")
        done = self.llm.complete(prompt, max_tokens=max_tokens, temperature=temperature)
        self._log_llm(task, fkey, prompt, done.prompt_tokens, done.completion_tokens, 1, ok=True, value=done.text)
        return done.text
