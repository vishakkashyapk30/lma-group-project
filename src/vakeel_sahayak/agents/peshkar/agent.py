"""Peshkar agent (plan §3.2). Dossier, List of Dates, Rights Radar, change detection (plan §7). Fine-tuned Qwen3-4B + rules, laptop.

Peshkar reads the case shelf Munshi filed and builds what counsel approves at Gate 1:

1. **The dossier** (§7.1). Each of the 12 fields the extractor reads is asked of the model (`extractor_4b`, or the
   offline handler) with the passages most likely to hold it. Every value comes back with a quote; the quote must be
   found in the file (that gives the source: document, page, box, language and route) and the NLI `span_check` must find
   the value supported by it. A field that fails is read again, more widely, once; what still fails is UNSUPPORTED.
   Two different values for one field are a conflict: AMBIGUOUS, put to counsel through `ask_user`, which shares the
   round's 3 questions with Munshi. `map_section` fills each section's equivalent, bail class and maximum punishment;
   `date_calc` computes the days in custody. Counsel's own values (USER_STATED, USER_EDITED) are never overwritten.
2. **The List of Dates** (§7.2) from `case.timeline`: sorted, with sources, conflicts side by side.
3. **The Rights Radar** (§7.3) through the `rights_check` tool.
4. **Change detection** (§7.4). When a new document is filed only the fields it touches are read again; the diff
   against counsel's last approval is a `ChangeSet`, with the Radar re-run and the clock-based threshold crossings
   (`RightsEngine.clock_crossings`) included.

Peshkar is callable on its own, without the case graph:

    peshkar = PeshkarAgent(case_id="case-0007", log=log)
    dossier = peshkar.build_dossier()
    report = peshkar.run_rights_radar()

Every decision is an event with actor PESHKAR (tool `extract_field`, `conflict`, `ask_user`, ...). The event log is the
source of truth: fields are written through the filer (STORE_WRITE `case.facts`), views through `write_view`.
"""

from __future__ import annotations

import os
import re
import weakref
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from typing import Any

from vakeel_sahayak.agents.base import AgentContext, BaseAgent, jsonable
from vakeel_sahayak.agents.peshkar import changes, offline  # noqa: F401  (importing `offline` registers the offline handler)
from vakeel_sahayak.agents.peshkar.dates import resolve_rows, side_by_side
from vakeel_sahayak.agents.peshkar.fields import (
    ALL_FIELDS,
    EXTRACTION_ORDER,
    FIELD_SPECS,
    QUESTION_PRIORITY,
    STATED_STATUSES,
    USER_STATUSES,
    ExtractedItem,
    FieldExtraction,
    FieldSpec,
    build_tracked,
    claim_text,
    coerce_value,
    describe_value,
    flat,
    merge_subsumed,
    norm_key,
    sentences,
    snippet,
    value_key,
)
from vakeel_sahayak.agents.peshkar.prompts import (
    QUESTION_TEMPLATES,
    RETRY_NOTE,
    SYSTEM_PROMPT,
    TASK_EXTRACT_FIELD,
    USER_PROMPT_TEMPLATES,
)
from vakeel_sahayak.ingestion.questions import _asker as _asker_slot  # noqa: PLC2701
from vakeel_sahayak.ingestion.questions import question_limit, questions_used_this_round, set_asker
from vakeel_sahayak.models.base import LLMClient, ModelUnavailable, NliClient
from vakeel_sahayak.orchestration.budgets import BudgetExhausted
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.orchestration.structured_output import StructuredOutputError
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.pipelines.concordance.refs import make_ref, split_ref
from vakeel_sahayak.pipelines.order_facts import extract_dates
from vakeel_sahayak.pipelines.section_extract import extract_sections
from vakeel_sahayak.record import gates as record_gates
from vakeel_sahayak.record import views
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.rights.engine import RightsEngine
from vakeel_sahayak.schemas.change_set import ChangeSet, FieldChange
from vakeel_sahayak.schemas.common import SourceRef, TrackedField
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import (
    AgentName,
    EventKind,
    FieldStatus,
    GateId,
    RightsCheckName,
    RightsStatus,
)
from vakeel_sahayak.schemas.rights_report import RightsCheckResult, RightsReport
from vakeel_sahayak.schemas.store_rows import TimelineEvent
from vakeel_sahayak.tools.base import ToolError
from vakeel_sahayak.tools.types import SpanCheckResult


def peshkar_workers() -> int:
    """Threads for the field readings: `VS_PESHKAR_WORKERS`; unset means 1 with the offline backend (event order stays exactly as before) and 4 with a hosted one."""
    raw = os.environ.get("VS_PESHKAR_WORKERS", "").strip()
    if raw.isdigit():
        return max(1, min(int(raw), 16))
    return 1 if os.environ.get("VS_LLM_BACKEND", "offline").strip().lower() in ("", "offline") else 4


MAX_ATTEMPTS = 2  # the first reading, and one re-extraction of a field that failed the check
FIRST_K, WIDE_K = 4, 12  # chunks shown per field on the first reading, and on the re-extraction
CLOCK_RULE = "CALENDAR_DAYS_BETWEEN"  # arrest to as-of (plan §7.1 example: 167 days)
MAX_TIMELINE_ROWS = 40
_HIGH_COURT = re.compile(r"\bHigh\s+Court\s+of\s+([A-Za-z]+(?:\s+(?!at\b|and\b|in\b)[A-Za-z]+)?)", re.IGNORECASE)
_NO = re.compile(r"^\W*(?:no|none|nil|nahi|nahin|नहीं)\b", re.IGNORECASE)
_YES = re.compile(r"^\W*(?:yes|y|haan|han|हाँ|हां)\b", re.IGNORECASE)
_NOT_FILED = re.compile(r"not\s+(?:yet\s+)?(?:been\s+)?filed|no\s+charge|yet\s+to\s+be\s+filed|pending", re.IGNORECASE)


_ACTIVE: dict[str, weakref.ReferenceType[PeshkarAgent]] = {}  # the Peshkar working on each case (the `extract_dossier` tool uses it)


def active_agent(case_id: str) -> PeshkarAgent | None:
    """The live PeshkarAgent of a case, if one exists (so the `extract_dossier` tool reads with that agent's model, NLI and budget)."""
    ref = _ACTIVE.get(case_id)
    return ref() if ref is not None else None


@dataclass
class _Checked:
    """A value that passed the check, with where it came from."""

    value: Any
    source: SourceRef
    score: float


@dataclass
class FieldOutcome:
    """What Peshkar decided for one field (written to the log as one `extract_field` event)."""

    name: str
    tracked: TrackedField[Any]
    decision: str  # verified | unsupported | ambiguous | kept_counsel | kept_filed | computed | stated | edited
    attempts: int = 0
    reasons: list[str] = field(default_factory=list)
    candidates: list[_Checked] = field(default_factory=list)  # the conflicting readings of an AMBIGUOUS scalar
    mapped_with: str | None = None  # the date `map_section` was given (sections only)
    unmapped: dict[str, list[str]] = field(default_factory=dict)  # sections whose mapping is unclear -> the candidate references
    changed: bool = False


@dataclass
class _Ask:
    """A question for counsel and what to do with the answer."""

    key: str
    text: str
    apply: Any  # callable(answer: str) -> None


class PeshkarAgent(BaseAgent):
    """Dossier, List of Dates, Rights Radar, change detection (plan §7). Fine-tuned Qwen3-4B + rules, laptop."""

    NAME = AgentName.PESHKAR
    ROLE_MODEL = "extractor_4b"
    SYSTEM_PROMPT = SYSTEM_PROMPT

    def __init__(
        self,
        ctx: AgentContext | None = None,
        *,
        case_id: str | None = None,
        log: EventLog | None = None,
        switches: Switches | None = None,
        llm: LLMClient | None = None,
        nli: NliClient | None = None,
        cases_dir: str | None = None,
    ) -> None:
        """Create Peshkar, from an AgentContext or from plain arguments (the graph is optional).

        Args:
            ctx: the injected context; its case id, log, switches, LLM, NLI client and toolbox are used
            case_id: the case (needed when there is no context)
            log: the case's event log (default: the configured per-case log)
            switches: ablation switches (A3 refuses the rule tools, A5 picks the extractor)
            llm: the extractor client (default: the configured client of the agent's role)
            nli: the NLI client for the span check (default: the configured one)
            cases_dir: cases folder for the event log, the alias map and the case stores
        """
        if ctx is None:
            if not case_id:
                raise ValueError("Peshkar needs a case_id or an AgentContext")
            ctx = AgentContext(case_id=case_id, log=log, switches=switches or Switches(), llm=llm, nli=nli, cases_dir=cases_dir)
        super().__init__(ctx)
        self._row_sources: dict[str, SourceRef] = {}
        _ACTIVE[self.case_id] = weakref.ref(self)

    # ------------------------------------------------------------------ small plumbing

    def _state(self, state: CaseGraphState | None) -> CaseGraphState:
        return state if state is not None else CaseGraphState(case_id=self.case_id, switches=self.switches)

    @staticmethod
    def _as_of(state: CaseGraphState) -> str:
        return state.as_of or date.today().isoformat()

    def _dossier(self) -> CaseDossier:
        """The dossier as the log folds it (the views are always rebuilt from the log)."""
        return self.case_state().dossier()

    def _decision(self, tool: str, **outputs: Any) -> None:
        """One event for a decision (actor PESHKAR)."""
        sources = [s for s in [outputs.pop("source", None)] if s]
        self.emit(EventKind.AGENT_MESSAGE, {"tool": tool, "outputs": outputs, "sources": sources})

    def _tool(self, name: str, **kwargs: Any) -> Any:
        """call_tool, with a refused or failed call coming back as a ToolError rather than an exception."""
        from vakeel_sahayak.tools.registry import ToolPermissionError

        try:
            return self.call_tool(name, **kwargs)
        except ToolPermissionError as exc:
            return ToolError(tool=name, kind="permission_denied", message=str(exc), retryable=False)

    # ------------------------------------------------------------------ the run

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Peshkar's full job for the current graph state.

        The first time on a case: build the dossier, the List of Dates and the Rights Radar, and prepare Gate 1. Once
        there is a baseline (a snapshot of an earlier run, or counsel's approval): detect what changed instead and
        leave a pending ChangeSet for counsel to re-approve. The stage is left for the graph to advance.

        Args:
            state: see behaviour

        Returns:
            Updated state: dossier, list_of_dates, rights, and pending_change_set when something changed.
        """
        events = self.log.read(self.case_id)
        if changes.baseline(events, self.case_id) is None:
            dossier = self.build_dossier(state)
            dates = self.build_list_of_dates(state)
            rights = self.run_rights_radar(state)
            self.snapshot(state)
            self.gate1_inputs(state)
            return self._with_injection(state.model_copy(update={"dossier": dossier, "list_of_dates": dates, "rights": rights}))
        change_set = self.detect_changes(state)
        update: dict[str, Any] = {
            "dossier": self._dossier(),
            "list_of_dates": self._list_of_dates(),
            "rights": self.case_state().rights_report(),
        }
        if not _is_empty(change_set):
            update["pending_change_set"] = change_set
        return self._with_injection(state.model_copy(update=update))

    # ------------------------------------------------------------------ dossier (plan §7.1)

    def build_dossier(self, state: CaseGraphState | None = None) -> CaseDossier:
        """Extract, span-check, re-extract failed fields, put conflicts to counsel; stop when ready for Gate 1 (plan §7.1).

        Args:
            state: see behaviour

        Returns:
            CaseDossier.
        """
        state = self._state(state)
        self._extract_and_commit(state, list(EXTRACTION_ORDER) + ["custody_days"], reason="build")
        return self._dossier()

    def extract_fields(self, state: CaseGraphState | None, fields: list[str] | None = None) -> CaseDossier:
        """Read only these fields again (all when None), check them, and write what changed (the `extract_dossier` tool)."""
        state = self._state(state)
        names = [n for n in ALL_FIELDS if fields is None or n in fields]
        unknown = set(fields or []) - set(ALL_FIELDS)
        if unknown:
            raise ValueError(f"not dossier fields: {sorted(unknown)}")
        self._extract_and_commit(state, names, reason="extract_fields")
        return self._dossier()

    def _extract_and_commit(self, state: CaseGraphState, names: list[str], reason: str) -> dict[str, FieldOutcome]:
        existing = self._dossier()
        as_of = self._as_of(state)
        outcomes: dict[str, FieldOutcome] = {}
        order = [n for n in EXTRACTION_ORDER if n in names]
        read = self.parallel(order, lambda n: self._read_field(n, getattr(existing.fields, n)), max_workers=peshkar_workers())  # results in extraction order
        outcomes.update(zip(order, read, strict=True))
        self._finish_sections(outcomes, existing)
        asks = self._conflict_asks(outcomes) + self._mapping_asks(outcomes) + self._missing_asks(outcomes)
        open_questions = self._put_to_counsel(asks)
        sections = outcomes.get("sections")
        if sections is not None and sections.mapped_with is None:  # an answer may have given the date the concordance needed
            self._finish_sections(outcomes, existing)
        if "custody_days" in names:
            outcomes["custody_days"] = self._custody(outcomes, existing, as_of)
        for name in [n for n in ALL_FIELDS if n in outcomes]:
            self._commit(outcomes[name], getattr(existing.fields, name))
        self._write_meta(state, existing, open_questions)
        self._decision(
            "build_dossier",
            reason=reason,
            fields={n: o.decision for n, o in outcomes.items()},
            open_questions=open_questions,
        )
        return outcomes

    # ---- reading one field

    def _read_field(self, name: str, existing: TrackedField[Any]) -> FieldOutcome:
        """The model reading of one field, checked, re-read once if it failed, and decided (VERIFIED, UNSUPPORTED, AMBIGUOUS)."""
        spec = FIELD_SPECS[name]
        if existing.status in USER_STATUSES:  # counsel's word stands; it keeps its chat source
            self._decision("extract_field", field=name, decision="kept_counsel", status=existing.status.value)
            return FieldOutcome(name, existing, "kept_counsel")
        verified: list[_Checked] = []
        none_ok: _Checked | None = None
        reasons: list[str] = []
        attempts = 0
        for attempt in range(MAX_ATTEMPTS):
            attempts += 1
            passages, timeline = self._evidence(spec, attempt)
            try:
                extraction = self._ask_extract(spec, passages, timeline, attempt, reasons)
            except (StructuredOutputError, ModelUnavailable, BudgetExhausted) as exc:
                reasons = [f"extraction failed: {type(exc).__name__}"]
                self.error("extract_failed", f"{name}: {type(exc).__name__}", field=name)
                break
            ok, bad = self._check_items(name, extraction, passages, timeline)
            for c in ok:
                if all(value_key(c.value) != value_key(v.value) for v in verified):
                    verified.append(c)
            if none_ok is None and extraction.none_stated:
                none_ok = self._check_none(name, extraction, passages, timeline)
                if none_ok is None:
                    bad.append("the quote for 'none' does not support it")
            reasons = bad
            if not bad and (verified or none_ok):
                break
            if not bad and not extraction.items and not extraction.none_stated:
                reasons = ["nothing found in the passages shown"]
        return self._decide(spec, verified, none_ok, existing, reasons, attempts)

    def _evidence(self, spec: FieldSpec, attempt: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Passages likely to hold the field (case.docs search), cut to the cue sentences, and the filed timeline rows."""
        k = FIRST_K if attempt == 0 else WIDE_K
        found: dict[str, Any] = {}
        for query in spec.queries[: 1 if attempt == 0 else len(spec.queries)]:
            res = self._tool("search_case_docs", case_id=self.case_id, query=query, k=k)
            if isinstance(res, ToolError):
                continue
            for chunk in res:
                found.setdefault(chunk.chunk_id, chunk)
        chunks = sorted(found.values(), key=lambda c: (c.doc_id, c.page, c.chunk_id))
        width = 1 + attempt
        passages = [
            {
                "chunk_id": c.chunk_id, "doc": c.doc_id, "doc_type": c.doc_type.value, "page": c.page, "box": c.box,
                "lang": c.lang, "route": c.route, "confidence": c.confidence,
                "text": self.untrusted(snippet(c.text, spec.cue, width), SourceRef(doc=c.doc_id, page=c.page)),
                **({"text_en": self.untrusted(snippet(c.text_en, spec.cue, width), SourceRef(doc=c.doc_id, page=c.page))} if c.text_en else {}),
            }
            for c in chunks
        ]  # fmt: skip
        return passages, self._timeline_rows()

    def _timeline_rows(self) -> list[dict[str, Any]]:
        res = self._tool("get_timeline", case_id=self.case_id)
        if isinstance(res, ToolError):
            return []
        self._row_sources = {r.event_id: r.source for r in res if r.source is not None}
        return [
            {"event_id": r.event_id, "date": r.date, "label": r.label, "status": r.status.value,
             "doc": r.source.doc if r.source else None, "page": r.source.page if r.source else None,
             "quote": r.source.quote if r.source else None}
            for r in res[:MAX_TIMELINE_ROWS]
        ]  # fmt: skip

    def _ask_extract(self, spec: FieldSpec, passages: list[dict], timeline: list[dict], attempt: int, reasons: list[str]) -> FieldExtraction:
        instructions = USER_PROMPT_TEMPLATES[TASK_EXTRACT_FIELD].format(field=spec.name, describe=spec.describe)
        if attempt and reasons:
            instructions += " " + RETRY_NOTE.format(reasons="; ".join(reasons)[:300])
        result = self.ask(
            TASK_EXTRACT_FIELD,
            instructions,
            case={"field": spec.name, "passages": passages, "timeline": timeline, "retry": attempt},
            schema=FieldExtraction,
            max_tokens=1500,
        )
        return result if isinstance(result, FieldExtraction) else FieldExtraction.model_validate(result)

    # ---- the check: quote located, value supported

    def _check_items(
        self, name: str, extraction: FieldExtraction, passages: list[dict], timeline: list[dict]
    ) -> tuple[list[_Checked], list[str]]:
        ok: list[_Checked] = []
        bad: list[str] = []
        for item in extraction.items:
            checked, why = self._check_item(name, item, passages, timeline)
            if checked is not None:
                ok.append(checked)
            else:
                bad.append(why)
        return ok, bad

    def _check_item(self, name: str, item: ExtractedItem, passages: list[dict], timeline: list[dict]) -> tuple[_Checked | None, str]:
        try:
            value = coerce_value(name, item.value)
        except ValueError as exc:
            return None, f"malformed value ({exc})"
        located = self._locate(item, passages, timeline)
        if located is None:
            return None, f"the quote for {name} is not in the file"
        source = located
        premise = source.quote_en or source.quote or ""
        result = self._span(claim_text(name, value, premise), premise)
        self._decision("span_check", field=name, supported=result.supported, score=round(result.score, 3), source=source)
        if not result.supported:
            return None, f"the quote does not support {describe_value(name, value)} (score {result.score:.2f})"
        return _Checked(value, source, result.score), ""

    def _check_none(self, name: str, extraction: FieldExtraction, passages: list[dict], timeline: list[dict]) -> _Checked | None:
        """'The papers say there is none' (no criminal antecedents): the quote must be in the file and support it."""
        located = self._locate(ExtractedItem(quote=extraction.none_quote), passages, timeline)
        if located is None:
            return None
        premise = located.quote_en or located.quote or ""
        result = self._span("The accused has no criminal antecedents", premise)
        return _Checked([], located, result.score) if result.supported else None

    def _locate(self, item: ExtractedItem, passages: list[dict], timeline: list[dict]) -> SourceRef | None:
        """Find the quote in the file and build its source (the model's own doc and page are only a hint)."""
        quote = (item.quote or "").strip()
        wanted = norm_key(quote)
        if len(wanted.split()) < 2:
            return None
        order = sorted(passages, key=lambda p: (p["doc"] != item.doc, p["page"] != item.page))
        for p in order:
            for key in ("text", "text_en"):
                if not p.get(key):
                    continue
                shown = _unwrap(p[key])
                if wanted in norm_key(shown):
                    return self._source_of(p, quote, key == "text_en")
                best = _best_sentence(wanted, shown)
                if best is not None:
                    return self._source_of(p, best, key == "text_en")
        for row in timeline:  # the quote is one Munshi already filed with its source
            if row.get("quote") and norm_key(row["quote"]) == wanted and row["event_id"] in self._row_sources:
                return self._row_sources[row["event_id"]]
        return None

    def _source_of(self, passage: dict, quote: str, english: bool) -> SourceRef:
        """The source of a quote found in a chunk: document, page, box, language, route, and the English line of a Hindi quote."""
        original_text = _unwrap(passage.get("text") or "")
        quote_orig, quote_en = quote, None
        if passage.get("text_en"):
            en_text = _unwrap(passage["text_en"])
            if english:
                quote_en = quote
                # the Hindi sentence at the same place, when the two texts split into the same sentences
                o, e = sentences(original_text), sentences(en_text)
                if len(o) == len(e):
                    idx = next((i for i, s in enumerate(e) if norm_key(quote)[:30] in norm_key(s)), None)
                    quote_orig = o[idx] if idx is not None else quote
            else:
                o, e = sentences(original_text), sentences(en_text)
                idx = next((i for i, s in enumerate(o) if norm_key(quote)[:30] in norm_key(s)), None)
                quote_en = e[idx] if idx is not None and len(o) == len(e) else None
        return SourceRef(
            doc=passage["doc"], page=passage["page"], box=passage.get("box"), lang=passage.get("lang"),
            route=passage.get("route"), quote=quote_orig[:600], quote_en=quote_en[:600] if quote_en else None,
            confidence=passage.get("confidence"),
        )  # fmt: skip

    def _span(self, claim: str, quote: str) -> SpanCheckResult:
        """The NLI span check of a claim against its quote: the `span_check` tool, or the context's own NLI client."""
        if self.ctx.nli is None:
            res = self._tool("span_check", value=claim, quote=quote)
            if isinstance(res, SpanCheckResult):
                return res
        from vakeel_sahayak.models.nli import nli_threshold

        nli = self.get_nli()
        call = self.emit(EventKind.TOOL_CALL, {"tool": "span_check", "inputs": {"value": claim, "quote": quote}})
        verdict = nli.judge(quote, claim, nli_threshold("span_check", nli))
        result = SpanCheckResult(supported=verdict.supported, score=verdict.score, quote=quote)
        self.emit(EventKind.TOOL_RESULT, {"tool": "span_check", "outputs": {"result": result.model_dump()}, "parent_id": call.event_id})
        return result

    # ---- deciding the field

    def _decide(
        self, spec: FieldSpec, verified: list[_Checked], none_ok: _Checked | None, existing: TrackedField[Any], reasons: list[str], attempts: int
    ) -> FieldOutcome:
        name = spec.name
        if spec.kind == "scalar":
            values = merge_subsumed([c.value for c in verified])
            chosen = [next(c for c in verified if c.value is v or c.value == v) for v in _unique(values)]
            if len(chosen) > 1:
                tracked = build_tracked(name, None, chosen[0].source, FieldStatus.AMBIGUOUS)
                out = FieldOutcome(name, tracked, "ambiguous", attempts, ["the documents give different values"], chosen)
            elif chosen:
                out = FieldOutcome(name, build_tracked(name, chosen[0].value, chosen[0].source, FieldStatus.VERIFIED), "verified", attempts)
            else:
                out = self._fallback(spec, existing, reasons, attempts)
        else:
            values: list[Any] = []
            for c in verified:
                if all(value_key(c.value) != value_key(v) for v in values):
                    values.append(c.value)
            if verified:
                quotes = list(dict.fromkeys(c.source.quote for c in verified if c.source.quote))[:3]
                first = verified[0].source.model_copy(update={"quote": " … ".join(quotes)[:600]})
                out = FieldOutcome(name, build_tracked(name, values, first, FieldStatus.VERIFIED), "verified", attempts)
            elif none_ok is not None:
                out = FieldOutcome(name, build_tracked(name, [], none_ok.source, FieldStatus.VERIFIED), "verified", attempts)
            else:
                out = self._fallback(spec, existing, reasons, attempts)
        out.reasons = out.reasons or reasons
        self._decision(
            "extract_field", field=name, decision=out.decision, status=out.tracked.status.value, attempts=attempts, reasons=out.reasons,
            candidates=[{"value": c.value, "doc": c.source.doc, "page": c.source.page} for c in out.candidates], source=out.tracked.source,
        )  # fmt: skip
        return out

    def _fallback(self, spec: FieldSpec, existing: TrackedField[Any], reasons: list[str], attempts: int) -> FieldOutcome:
        """Nothing checked this time: keep what Munshi filed if its own quote still passes the check, else UNSUPPORTED."""
        name = spec.name
        if existing.status == FieldStatus.VERIFIED and existing.value is not None and existing.source and existing.source.quote:
            premise = existing.source.quote_en or existing.source.quote
            value = jsonable(existing.value)
            items = value if spec.kind == "list" and isinstance(value, list) else [value]
            passed = [v for v in items if self._span(claim_text(name, v, premise), premise).supported]
            if passed:
                kept = passed if spec.kind == "list" else passed[0]
                return FieldOutcome(
                    name, build_tracked(name, kept, existing.source, FieldStatus.VERIFIED), "kept_filed", attempts,
                    ["kept what was filed at intake: its quote passes the check"],
                )  # fmt: skip
        return FieldOutcome(name, build_tracked(name, None, None, FieldStatus.UNSUPPORTED), "unsupported", attempts, reasons or ["not found in the file"])

    # ---- sections and custody

    def _finish_sections(self, outcomes: dict[str, FieldOutcome], existing: CaseDossier) -> None:
        """Map each charged section across the 2024 change and add its bail class and maximum punishment (plan §7.1)."""
        out = outcomes.get("sections")
        if out is None or out.decision in ("kept_counsel", "unsupported", "stated", "edited") or not isinstance(out.tracked.value, list):
            return
        when = self._offence_date(outcomes, existing)
        out.unmapped = {}
        values = [self._map_section(dict(raw), when, out.unmapped) for raw in out.tracked.value]
        status = FieldStatus.AMBIGUOUS if out.unmapped else FieldStatus.VERIFIED
        out.tracked = build_tracked("sections", values, out.tracked.source, status)
        out.decision, out.mapped_with = ("ambiguous" if out.unmapped else out.decision), when
        self._decision("map_sections", sections=[v["as_written"] for v in values], ambiguous=sorted(out.unmapped), offence_date=when)

    def _offence_date(self, outcomes: dict[str, FieldOutcome], existing: CaseDossier) -> str | None:
        """The date that decides which code governs: the offence date, else the FIR date, else the arrest date."""

        def stated(name: str) -> Any:
            t = outcomes[name].tracked if name in outcomes else getattr(existing.fields, name)
            return jsonable(t.value) if t.status in STATED_STATUSES else None

        fir = stated("fir")
        return stated("offence_date") or (fir or {}).get("date") or stated("arrest_date")

    def _map_section(self, value: dict[str, Any], when: str | None, unmapped: dict[str, list[str]]) -> dict[str, Any]:
        equivalent = None
        if when:
            res = self._tool("map_section", code=value["code"], section=value["section"], offence_date=when)
            if not isinstance(res, ToolError):
                value["equivalent"] = res.equivalent or value.get("equivalent")
                if res.ambiguous:
                    unmapped[value["as_written"]] = list(res.candidates)
                else:
                    equivalent = res.equivalent
        refs = [(value["code"], value["section"])]
        if equivalent:  # the statute table may hold only one of the two codes: the one-to-one equivalent has the same offence
            try:
                refs.append(split_ref(equivalent))
            except ValueError:
                pass
        for code, section in refs:
            statute = self._tool("get_statute", code=code, section=section)
            if isinstance(statute, ToolError):
                continue
            if statute.bailable is None and not statute.max_punishment:
                continue
            if statute.bailable is not None:
                value["bailable"] = statute.bailable
            if statute.max_punishment:
                value["max_punishment"] = statute.max_punishment
            break
        return value

    def _custody(self, outcomes: dict[str, FieldOutcome], existing: CaseDossier, as_of: str) -> FieldOutcome:
        arrest = outcomes["arrest_date"].tracked if "arrest_date" in outcomes else existing.fields.arrest_date
        old = existing.fields.custody_days
        if old.status in USER_STATUSES:
            return FieldOutcome("custody_days", old, "kept_counsel")
        if arrest.value is None or arrest.status not in STATED_STATUSES or as_of < str(arrest.value):
            tracked = build_tracked("custody_days", None, None, FieldStatus.UNSUPPORTED)
            why = "the arrest date is not settled" if arrest.value is None else "the arrest date is after the as-of date"
            return FieldOutcome("custody_days", tracked, "unsupported", 0, [why])
        res = self._tool("date_calc", start=str(arrest.value), end=as_of, rule=CLOCK_RULE)
        if isinstance(res, ToolError):
            return FieldOutcome("custody_days", build_tracked("custody_days", None, None, FieldStatus.UNSUPPORTED), "unsupported", 0, [res.message])
        source = SourceRef(tool="date_calc", quote=f"{arrest.value} to {as_of} ({CLOCK_RULE})")
        self._decision("date_calc", field="custody_days", days=res.value, start=str(arrest.value), end=as_of)
        return FieldOutcome("custody_days", build_tracked("custody_days", int(res.value), source, FieldStatus.COMPUTED), "computed", 0)

    # ---- writing

    def _commit(self, out: FieldOutcome, before: TrackedField[Any]) -> None:
        """Write a field unless it is what the log already holds (the same value and status)."""
        if out.decision == "kept_counsel":
            return
        new = out.tracked
        same = (
            before.status == new.status
            and value_key(before.value) == value_key(new.value)
            and (before.source is None) == (new.source is None)
            and (before.source is None or (before.source.doc, before.source.page) == (new.source.doc, new.source.page))  # type: ignore[union-attr]
        )
        if same:
            return
        self.write_field(out.name, new)
        out.changed = True

    def _write_meta(self, state: CaseGraphState, existing: CaseDossier, open_questions: list[str]) -> None:
        """Dossier-level court, as-of date and open questions (the `dossier` shorthand of the record views)."""
        meta: dict[str, Any] = {"as_of": self._as_of(state), "open_questions": open_questions}
        court = existing.court or self._court()
        if court:
            meta["court"] = court
        self.emit(EventKind.STORE_WRITE, {"inputs": {"store": "case.views", "view": "dossier"}, "outputs": {"dossier": meta}})

    def _court(self) -> str | None:
        res = self._tool("search_case_docs", case_id=self.case_id, query="High Court of", k=4)
        if isinstance(res, ToolError):
            return None
        for chunk in res:
            m = _HIGH_COURT.search(flat(chunk.text_en or chunk.text))
            if m:
                return f"{m.group(1).title()} High Court"
        return None

    # ---- questions to counsel (plan §4.3: 3 per round, shared with Munshi)

    def _conflict_asks(self, outcomes: dict[str, FieldOutcome]) -> list[_Ask]:
        asks = []
        for name, out in outcomes.items():
            if out.decision != "ambiguous" or not out.candidates:
                continue
            options = "; ".join(f"{describe_value(name, c.value)} ({c.source.doc}, p.{c.source.page})" for c in out.candidates)
            what = name.replace("_", " ")
            self._decision("conflict", field=name, values=[c.value for c in out.candidates], sources=[c.source.model_dump(mode="json") for c in out.candidates])
            asks.append(_Ask(f"conflict:{name}", QUESTION_TEMPLATES["conflict"].format(what=what, options=options), lambda a, n=name, o=out: self._resolve_conflict(n, o, a)))
        return asks

    def _resolve_conflict(self, name: str, out: FieldOutcome, answer: str) -> None:
        """Counsel picked one of the readings (by its date): their choice is a USER_EDITED value."""
        isos = {d.iso for d in extract_dates(answer)}
        picked = [c for c in out.candidates if (c.value if isinstance(c.value, str) else (c.value or {}).get("date")) in isos]
        if len(picked) != 1:
            self._decision("answer_unclear", field=name, note="the answer does not pick exactly one of the readings; the field stays AMBIGUOUS")
            return
        out.tracked = build_tracked(name, picked[0].value, picked[0].source, FieldStatus.USER_EDITED)
        out.decision, out.candidates = "edited", []
        self._decision("conflict_resolved", field=name, value=picked[0].value)

    def _mapping_asks(self, outcomes: dict[str, FieldOutcome]) -> list[_Ask]:
        """Sections whose mapping across the 2024 change is unclear (`map_section` says ambiguous) go to counsel too."""
        out = outcomes.get("sections")
        if out is None or not out.unmapped:
            return []
        asks = []
        for as_written, candidates in out.unmapped.items():
            options = ", ".join(candidates) or "no single equivalent"
            self._decision("mapping_unclear", section=as_written, candidates=candidates)
            asks.append(
                _Ask(
                    f"mapping:{as_written}", QUESTION_TEMPLATES["mapping"].format(as_written=as_written, options=options),
                    lambda a, w=as_written, c=list(candidates), o=out: self._resolve_mapping(o, w, c, a),
                )
            )  # fmt: skip
        return asks

    def _resolve_mapping(self, out: FieldOutcome, as_written: str, candidates: list[str], answer: str) -> None:
        picked = [c for c in candidates if _ref_in(c, answer)]
        if len(picked) != 1 or not isinstance(out.tracked.value, list):
            return
        values = [{**v, "equivalent": picked[0]} if v.get("as_written") == as_written else v for v in out.tracked.value]
        out.unmapped.pop(as_written, None)
        status = FieldStatus.AMBIGUOUS if out.unmapped else FieldStatus.USER_EDITED
        out.tracked = build_tracked("sections", values, out.tracked.source, status)
        out.decision = "ambiguous" if out.unmapped else "edited"
        self._decision("mapping_resolved", section=as_written, equivalent=picked[0])

    def _missing_asks(self, outcomes: dict[str, FieldOutcome]) -> list[_Ask]:
        """Fields the papers do not state, in the order the Rights Radar needs them (antecedents, arrest, first remand, ...)."""
        asks = []
        for name in QUESTION_PRIORITY:
            out = outcomes.get(name)
            if out is not None and out.decision == "unsupported":
                asks.append(_Ask(f"missing:{name}", QUESTION_TEMPLATES[name], lambda a, n=name, o=out: self._take_answer(n, o, a)))
        return asks

    def _take_answer(self, name: str, out: FieldOutcome, answer: str) -> None:
        """A typed answer to a missing-field question becomes a USER_STATED value (counsel's word, no court record behind it)."""
        source = SourceRef(chat=f"answer to the {name.replace('_', ' ')} question")
        text = answer.strip()
        value: Any = None
        if name == "antecedents":
            value = [] if _NO.search(text) else ([text[:240]] if len(text) > 3 else None)
        elif name in ("arrest_date", "offence_date", "first_remand"):
            dates = extract_dates(text)
            value = dates[0].iso if dates else None
        elif name == "charge_sheet":
            dates = extract_dates(text)
            if dates:
                value = {"filed": True, "date": dates[0].iso}
            elif _NOT_FILED.search(text) or _NO.search(text):
                value = {"filed": False, "date": None}
            elif _YES.search(text):
                value = {"filed": True, "date": None}
        elif name == "sections":
            from vakeel_sahayak.pipelines.section_extract import charged_sections

            refs = charged_sections(extract_sections(text))
            value = [{"as_written": r, "code": split_ref(r)[0], "section": split_ref(r)[1]} for r in refs] or None
        if value is None:
            return
        try:
            value = coerce_list(name, value)
        except ValueError:
            return
        out.tracked = build_tracked(name, value, source, FieldStatus.USER_STATED)
        out.decision = "stated"
        self._decision("answer_taken", field=name, status=FieldStatus.USER_STATED.value)

    def _put_to_counsel(self, asks: list[_Ask]) -> list[str]:
        """Ask what fits in the round's room through `ask_user`; return every question still open afterwards.

        The questions that do not fit are deferred, not dropped: they stay in the dossier's open questions. A question
        already put to counsel and not yet answered is not asked twice.
        """
        events = self.log.read(self.case_id)
        asked_before = {q for e in events if e.inputs.get("action") == "ask_user" for q in e.outputs.get("questions", [])}
        answered = {e.inputs.get("question") for e in events if e.kind == EventKind.USER_ACTION and e.inputs.get("action") == "answer_question"}
        fresh = [a for a in asks if a.text not in asked_before or a.text in answered]
        stale_open = [a.text for a in asks if a.text in asked_before and a.text not in answered]
        room = max(0, question_limit() - questions_used_this_round(self.log, self.case_id))
        to_ask, deferred = fresh[:room], fresh[room:]
        answers: list[str] = []
        if to_ask:
            previous = getattr(_asker_slot, "agent", None)
            try:
                set_asker(AgentName.PESHKAR)
                res = self._tool("ask_user", questions=[a.text for a in to_ask], case_id=self.case_id)
            finally:
                set_asker(previous)
            if isinstance(res, ToolError):
                self._decision("ask_user", deferred=[a.text for a in to_ask], reason=res.kind)
                deferred = to_ask + deferred
                to_ask = []
            else:
                answers = [str(a) for a in res]
                self._decision("ask_user", asked=[a.text for a in to_ask], answered=len(answers), deferred=[a.text for a in deferred])
        elif deferred:
            self._decision("ask_user", asked=[], deferred=[a.text for a in deferred], reason="the round's questions are used up")
        blank: list[str] = []
        for ask, answer in zip(to_ask, answers, strict=False):
            if answer.strip():
                ask.apply(answer)
            else:  # an empty reply is no answer: the question stays open for counsel
                blank.append(ask.text)
        unanswered = [a.text for a in to_ask[len(answers) :]]
        return list(dict.fromkeys(stale_open + unanswered + blank + [a.text for a in deferred]))

    # ------------------------------------------------------------------ List of Dates (plan §7.2)

    def _list_of_dates(self) -> list[TimelineEvent]:
        res = self._tool("get_timeline", case_id=self.case_id)
        rows = [] if isinstance(res, ToolError) else list(res)
        rows, _ = resolve_rows(rows)
        return side_by_side(rows)

    def build_list_of_dates(self, state: CaseGraphState | None = None) -> list[TimelineEvent]:
        """Build the List of Dates from case.timeline (plan §7.2).

        One row per dated event, sorted by date, each with its source (document and page). Events that give different
        dates for the same single-valued event are marked AMBIGUOUS and listed side by side. Counsel's edits stand.

        Args:
            state: see behaviour

        Returns:
            Events.
        """
        res = self._tool("get_timeline", case_id=self.case_id)
        rows = [] if isinstance(res, ToolError) else list(res)
        updated, conflicts = resolve_rows(rows)
        before = {r.event_id: r for r in rows}
        for row in updated:
            if (row.status, row.conflicts_with) != (before[row.event_id].status, before[row.event_id].conflicts_with):
                self.write_timeline_event(row)
        listed = side_by_side(updated)
        self.write_view("list_of_dates", [r.model_dump(mode="json") for r in listed], sources=[r.source for r in listed if r.source][:50])
        self._decision("list_of_dates", rows=len(listed), conflicts=[{"field": f, "event_ids": ids} for f, ids in conflicts])
        return listed

    # ------------------------------------------------------------------ Rights Radar (plan §7.3)

    def run_rights_radar(self, state: CaseGraphState | None = None) -> RightsReport:
        """Call the Rights Radar tool (plan §7.3).

        The report is written to the log as the `rights_report` view. When the rule tools are switched off (A3) or the
        call fails, the report says CHECK for every right, with the reason, rather than guessing.

        Args:
            state: see behaviour

        Returns:
            RightsReport.
        """
        state = self._state(state)
        as_of = self._as_of(state)
        res = self._tool("rights_check", case_id=self.case_id, as_of=as_of)
        if isinstance(res, ToolError):
            self.error("rights_check_failed", res.message, tool="rights_check", tool_error=res.kind)
            res = RightsReport(
                case_id=self.case_id,
                as_of=as_of,
                checks=[RightsCheckResult(check=c, status=RightsStatus.CHECK, detail=f"Not judged: {res.message}") for c in RightsCheckName],
            )
        self.write_view("rights_report", res)
        self._decision("rights_radar", as_of=as_of, statuses={c.check.value: c.status.value for c in res.checks})
        return res

    # ------------------------------------------------------------------ change detection (plan §7.4)

    def detect_changes(self, state: CaseGraphState | None = None) -> ChangeSet:
        """On a new document or clock tick: re-extract touched fields, diff, re-run the radar, highlight for re-approval (plan §7.4).

        `diff_case_state` says which fields changed or were touched since counsel's last Gate 1 approval (or, before
        any approval, Peshkar's last snapshot). Only those fields are read again, through `extract_dossier`. The
        ChangeSet keeps the fields whose value or status really differs after that, the new timeline events, and the
        Rights Radar checks whose status moved: the radar is re-run, so a threshold crossed only because the days went
        by (the s.479 date) is in `rights_changed` too. With nothing new the trigger is the clock.

        Args:
            state: see behaviour

        Returns:
            ChangeSet.
        """
        state = self._state(state)
        base = changes.baseline(self.log.read(self.case_id), self.case_id)
        previous = base.rights if base is not None and base.rights is not None else (self.case_state().rights_report() or state.rights)
        diff = self._tool("diff_case_state", case_id=self.case_id, since_hash=base.dossier_hash if base else None)
        if isinstance(diff, ToolError):
            self.error("diff_failed", diff.message, tool="diff_case_state", tool_error=diff.kind)
            diff = ChangeSet(case_id=self.case_id, trigger="new_document")
        touched = [f.field for f in diff.fields]
        trigger = "new_document" if (touched or diff.new_event_ids) else "clock"
        self._decision("detect_changes", trigger=trigger, touched=touched, new_events=len(diff.new_event_ids))
        fields: list[FieldChange] = []
        if touched:
            after = self._tool("extract_dossier", case_id=self.case_id, fields=touched)
            now = changes.field_hashes(after if isinstance(after, CaseDossier) else self._dossier())
            fields = [f.model_copy(update={"new_hash": now[f.field]}) for f in diff.fields if f.field in now and now[f.field] != f.old_hash]
        self._refresh_custody(state)
        self.build_list_of_dates(state)
        report = self.run_rights_radar(state)
        crossings = RightsEngine(rules=[]).clock_crossings(previous, report) if previous is not None else []
        change_set = ChangeSet(
            case_id=self.case_id, trigger=trigger, fields=fields, new_event_ids=list(diff.new_event_ids), rights_changed=crossings
        )
        self.write_view("change_set", change_set)
        self._decision(
            "change_set", trigger=trigger, fields=[f.field for f in fields], new_events=len(change_set.new_event_ids),
            rights_changed=crossings, empty=_is_empty(change_set),
        )  # fmt: skip
        return change_set

    def _refresh_custody(self, state: CaseGraphState) -> None:
        """The days in custody grow with the clock: recompute the COMPUTED field to the as-of date (a counsel's value stands)."""
        existing = self._dossier()
        out = self._custody({}, existing, self._as_of(state))
        self._commit(out, existing.fields.custody_days)

    # ------------------------------------------------------------------ Gate 1 (plan §7.1, §13.5)

    def snapshot(self, state: CaseGraphState | None = None) -> str:
        """Mark the dossier as built (a `dossier_snapshot` view): the change-detection baseline until counsel approves."""
        dossier = self._dossier()
        digest = views.dossier_hash(dossier)
        self.write_view(changes.SNAPSHOT_VIEW, {"dossier_hash": digest, "fields": changes.field_hashes(dossier)})
        return digest

    def gate1_inputs(self, state: CaseGraphState | None = None) -> dict[str, Any]:
        """What the Gate 1 checklist needs (plan §13.5): what is unsupported, ambiguous or only stated, the open questions, the flags.

        Nothing is approved here: Peshkar only prepares the checklist. Counsel approves (record/gates.py), and the gate
        node of the graph opens the gate with `GateGuard.open` or `await_gate`.

        Args:
            state: see behaviour

        Returns:
            A dict: gate, unresolved_unsupported (the fields that block approval until acknowledged), ambiguous,
            user_stated, user_edited, conflicts (side by side), open_questions, rights_flags and dossier_hash.
        """
        status = record_gates.gate_status(self.log, self.case_id, GateId.GATE_1_DOSSIER)
        dossier = self._dossier()
        by_status: dict[FieldStatus, list[str]] = {s: [] for s in FieldStatus}
        for name in ALL_FIELDS:
            by_status[getattr(dossier.fields, name).status].append(name)
        report = self.case_state().rights_report()
        flags = [
            {"check": c.check.value, "status": c.status.value, "rule": c.rule}
            for c in (report.checks if report else [])
            if c.status in (RightsStatus.ELIGIBLE, RightsStatus.FLAG, RightsStatus.WINDOW_CLOSED, RightsStatus.BAR_APPLIES)
        ]
        _, conflicts = resolve_rows(self._timeline_models())
        inputs = {
            "gate": GateId.GATE_1_DOSSIER.value,
            "unresolved_unsupported": list(status.unresolved_unsupported),
            "ambiguous": by_status[FieldStatus.AMBIGUOUS],
            "user_stated": by_status[FieldStatus.USER_STATED],
            "user_edited": by_status[FieldStatus.USER_EDITED],
            "conflicts": [{"field": f, "event_ids": ids} for f, ids in conflicts],
            "open_questions": list(dossier.open_questions),
            "rights_flags": flags,
            "dossier_hash": views.dossier_hash(dossier),
        }
        self.write_view("gate1_checklist", inputs)
        self._decision("gate1_inputs", **{k: v for k, v in inputs.items() if k != "gate"})
        return inputs

    def _timeline_models(self) -> list[TimelineEvent]:
        res = self._tool("get_timeline", case_id=self.case_id)
        return [] if isinstance(res, ToolError) else list(res)

    def record_approval(self, state: CaseGraphState | None = None) -> str:
        """After counsel approves Gate 1: check the approval is on record and note the approved dossier hash (plan §7.4).

        The approval itself is only ever written by counsel (`record.gates.approve_gate`, which stores the hash of the
        dossier as approved). Peshkar reads it back, writes the per-field hashes of that dossier as the baseline view the
        next diff starts from, and returns the hash.

        Args:
            state: see behaviour

        Returns:
            The approved dossier hash.

        Raises:
            GateNotApproved: counsel has not approved Gate 1 for this case.
        """
        from vakeel_sahayak.record.gates import GateNotApproved

        approved = self.case_state().approved_dossier_hash()
        if approved is None or not views.gate_is_approved(self.log.read(self.case_id), GateId.GATE_1_DOSSIER):
            raise GateNotApproved(f"Gate 1 is not approved by counsel for case {self.case_id!r}")
        base = changes.baseline(self.log.read(self.case_id), self.case_id)
        fields = base.hashes if base is not None else {}
        self.write_view("approved_baseline", {"dossier_hash": approved, "fields": fields})
        self._decision("approval_recorded", dossier_hash=approved)
        return approved

    def clock_tick(self, state: CaseGraphState | None = None, as_of: str | None = None) -> ChangeSet:
        """The radar on a clock (plan §7.4): re-run it as of a later date; a threshold crossed gives a ChangeSet (trigger 'clock').

        Args:
            state: see behaviour
            as_of: the date to count to (default: the state's as_of, else today)

        Returns:
            ChangeSet (empty when no right changed status).
        """
        state = self._state(state)
        if as_of:
            state = state.model_copy(update={"as_of": as_of})
        return self.detect_changes(state)


# ---------------------------------------------------------------------------------------------- helpers

def _is_empty(change_set: ChangeSet) -> bool:
    return not (change_set.fields or change_set.new_event_ids or change_set.rights_changed)


def _unique(values: list[Any]) -> list[Any]:
    out: list[Any] = []
    for v in values:
        if all(value_key(v) != value_key(w) for w in out):
            out.append(v)
    return out


def _unwrap(text: str) -> str:
    from vakeel_sahayak.agents.peshkar.fields import unwrap

    return unwrap(text)


def _best_sentence(wanted: str, text: str) -> str | None:
    """A sentence of the text that is nearly the wanted quote (the model changed a character or two)."""
    for s in sentences(text):
        key = norm_key(s)
        if key and SequenceMatcher(None, wanted, key).ratio() >= 0.92:
            return s
    return None


def _ref_in(ref: str, answer: str) -> bool:
    """True when the answer names this statute reference ('BNS 318(4)' or '318(4) BNS')."""
    try:
        code, section = split_ref(ref)
    except ValueError:
        return False
    return any(r == make_ref(code, section) for r in extract_sections(answer))


def coerce_list(name: str, value: Any) -> Any:
    """A counsel-stated value as the field's type (list fields take a list of validated elements)."""
    from vakeel_sahayak.agents.peshkar.fields import FIELD_SPECS as specs

    if specs[name].kind == "list":
        return [coerce_value(name, v) for v in value]
    return coerce_value(name, value)
