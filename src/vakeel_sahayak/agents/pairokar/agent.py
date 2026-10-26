"""Pairokar agent (plan §3.2). Batch triage desk (plan §11). Rules + Qwen3-14B; laptop and Ada.

Pairokar is the clerk of the cause list. Legal-aid offices upload hundreds of undertrial files; Pairokar finds the
urgent ones:

1. **Stage 1, every file (cheap)**: Munshi, Peshkar and the Rights Radar run on each file; each gets a TriageCard.
2. **Decide**: per case, queue a full brief, flag it for counsel (an open default-bail window), or ask for documents
   first. The order is the fixed rule of `batch.urgency`; the decision is a rule too (the model is consulted only with
   `use_model=True`, and the rule has the last word on anything time-critical).
3. **Stage 2**: full runs (Sutradhar, then Vakeel) in urgency order within the session's GPU budget, the retrieval
   cache shared across cases, each case's output saved the moment it finishes, so an interrupted shard resumes.

No bulk export, ever: `export` is refused here (`BulkExportError`), a batch toolbox carries a refusing `export`, and a
full run that reports exported files is rejected. Each case's export needs its own Gate 2 approval from counsel.

Every decision is an event with actor PAIROKAR, on the case's own log (and a summary on the desk's log).

Pairokar is callable on its own, without the case graph:

    pairokar = PairokarAgent(case_id="desk-1", queue=TriageQueue("batch.sqlite"))
    cards = pairokar.stage1(["a.pdf", "b.pdf"])
    done = pairokar.stage2(cards, gpu_budget_hours=4.5)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from vakeel_sahayak.agents.base import AgentContext, BaseAgent, jsonable
from vakeel_sahayak.agents.pairokar import offline  # noqa: F401  (importing `offline` registers the offline handler)
from vakeel_sahayak.agents.pairokar.prompts import SYSTEM_PROMPT, TASK_DECIDE, USER_PROMPT_TEMPLATES
from vakeel_sahayak.agents.pairokar.triage import make_card
from vakeel_sahayak.batch.cache import RetrievalCache
from vakeel_sahayak.batch.queue import DEFAULT_CASE_HOURS, TriageQueue
from vakeel_sahayak.batch.scheduler import (
    DECISIONS,
    BulkExportError,
    FullRunner,
    Scheduler,
    Stage1Runner,
    guard_tools,
    next_step_text,
    refuse_export,
)
from vakeel_sahayak.models.base import LLMClient
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import AgentName, EventKind
from vakeel_sahayak.schemas.events import Event
from vakeel_sahayak.schemas.triage import TriageCard

DESK_CASE_ID = "batch-desk"


class NextStepChoice(BaseModel):
    """The model's reply to the decision task."""

    decision: str
    why: str = ""


class PairokarAgent(BaseAgent):
    """Batch triage desk (plan §11). Rules + Qwen3-14B; laptop and Ada."""

    NAME = AgentName.PAIROKAR
    ROLE_MODEL = "agents_14b"
    SYSTEM_PROMPT = SYSTEM_PROMPT

    def __init__(
        self,
        ctx: AgentContext | None = None,
        *,
        case_id: str | None = None,
        log: EventLog | None = None,
        switches: Switches | None = None,
        llm: LLMClient | None = None,
        cases_dir: str | None = None,
        cache: RetrievalCache | None = None,
        queue: TriageQueue | None = None,
        stage1_runner: Stage1Runner | None = None,
        full_runner: FullRunner | None = None,
        case_logs: Callable[[str], EventLog] | None = None,
        session_hours: float | None = None,
        hours_per_case: float = DEFAULT_CASE_HOURS,
        as_of: str | None = None,
        use_model: bool = False,
    ) -> None:
        """Create Pairokar, from an AgentContext or from plain arguments (the graph is optional).

        Args:
            ctx: the injected context; its log, budget, switches, LLM and retrieval cache are used
            case_id: the desk's own id (default 'batch-desk'); the desk log is this id's log
            log: the desk's event log (default: the configured one)
            switches: ablation switches
            llm: the 14B client, used only with `use_model=True`
            cases_dir: cases folder for the per-case logs and stores
            cache: the retrieval cache shared by every case of the batch (default: a new in-memory one)
            queue: the batch queue (default: the desk's durable queue file under the data directory)
            stage1_runner: (case_id, path) -> TriageCard (default: Munshi, Peshkar and the Radar on the file)
            full_runner: (case_id, path) -> the case's output (default: Sutradhar then Vakeel on the case)
            case_logs: case id -> that case's EventLog (default: its file under `cases_dir`; with no `cases_dir`, the desk's log)
            session_hours: GPU-hours of this session (the default budget of stage 2)
            hours_per_case: GPU-hours one full run is planned at
            as_of: the date the Rights Radar counts to (default: today)
            use_model: ask the model for each decision (the rule still decides anything time-critical)
        """
        if ctx is None:
            ctx = AgentContext(case_id=case_id or DESK_CASE_ID, log=log, switches=switches or Switches(), llm=llm, cases_dir=cases_dir)
        if cache is not None:
            ctx.cache = cache
        elif ctx.cache is None:
            ctx.cache = RetrievalCache()
        super().__init__(ctx)
        self.cache: RetrievalCache = ctx.cache
        self.queue = queue if queue is not None else TriageQueue()
        self.as_of = as_of
        self.use_model = use_model
        self._case_logs = case_logs
        self._logs: dict[str, EventLog] = {}
        self._stage1_runner = stage1_runner
        self._full_runner = full_runner
        self.scheduler = Scheduler(
            stage1_runner or self.run_stage1_case,
            full_runner or self.run_full_case,
            session_hours=session_hours,
            hours_per_case=hours_per_case,
            owner=f"pairokar:{self.case_id}",
            on_event=self._record,
            policy=self.switches.urgency_policy,
        )

    # ------------------------------------------------------------------ events

    def _log_for(self, case_id: str) -> EventLog:
        """The case's own event log: from `case_logs`, else its file under `cases_dir`, else the desk's log."""
        if case_id == self.case_id:
            return self.log  # type: ignore[return-value]
        if case_id not in self._logs:
            if self._case_logs is not None:
                self._logs[case_id] = self._case_logs(case_id)
            elif self.ctx.cases_dir:
                self._logs[case_id] = EventLog.for_case(case_id, self.ctx.cases_dir)
            else:  # no cases folder given: the desk's log holds every case's events (each carries its case id)
                self._logs[case_id] = self.log  # type: ignore[assignment]
        return self._logs[case_id]

    def _record(self, case_id: str, tool: str, text: str, outputs: dict[str, Any]) -> None:
        """One decision as an event (actor PAIROKAR) on the case's log, and a summary on the desk's log."""
        body = {"text": text, **outputs}
        log = self._log_for(case_id)
        log.append(Event(event_id="", case_id=case_id, ts="", kind=EventKind.AGENT_MESSAGE, actor=self.NAME, tool=tool, inputs={}, outputs=jsonable(body), sources=[]))
        if log is not self.log:
            self.emit(EventKind.AGENT_MESSAGE, {"tool": tool, "outputs": {**body, "case": case_id}})

    def _ctx_for(self, case_id: str) -> AgentContext:
        """A context for one case's agents: its own log and budget, the shared cache, a toolbox that refuses export."""
        return AgentContext(
            case_id=case_id,
            log=self._log_for(case_id),
            switches=self.switches,
            nli=self.ctx.nli,
            cache=self.cache,
            cases_dir=self.ctx.cases_dir,
            before=self.ctx.before,
        )

    # ------------------------------------------------------------------ export is never done here

    def call_tool(self, name: str, *, budget_factor: Any = None, **kwargs: Any) -> Any:
        """Call a tool, except `export`, which the batch desk never calls.

        Raises:
            BulkExportError: for `export`: every case needs its own approval.
        """
        if name == "export":
            self.error("bulk_export_refused", "Pairokar never exports: each case's export needs counsel's own Gate 2 approval.", tool=name)
            refuse_export()
        return super().call_tool(name, budget_factor=budget_factor, **kwargs)

    def export(self, *args: Any, **kwargs: Any) -> Any:
        """Refused: no bulk export."""
        self.error("bulk_export_refused", "Pairokar never exports: each case's export needs counsel's own Gate 2 approval.", tool="export")
        return refuse_export(*args, **kwargs)

    export_all = export_batch = bulk_export = export

    # ------------------------------------------------------------------ the run (one case's state)

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Pairokar's full job for the current graph state.

        For the case in the state: the card from its Rights Radar report, dossier and Munshi's gaps (stage 1 is run on
        the first file only when there is no dossier yet), the decision, and the card in `state.triage` and the log.

        Args:
            state: see behaviour

        Returns:
            Updated state: triage.
        """
        card: TriageCard | None = None
        if state.rights is None or state.dossier is None:
            if state.files:
                card = self.run_stage1_case(state.case_id, state.files[0])
            else:
                state = state.refresh_from_log()
        if card is None:
            if state.rights is None or state.dossier is None:
                self.error("nothing_to_triage", "No rights report or dossier for this case, and no file to read.")
                return state.model_copy(update={"errors": [*state.errors, "pairokar: nothing to triage"]})
            gaps = [g.item for g in state.ingestion.gaps] if state.ingestion is not None else []
            card = make_card(state.case_id, state.rights, state.dossier, gaps)
        card = self.decide_next_steps([card])[0]
        self.write_view("triage_card", card)
        return state.model_copy(update={"triage": card})

    # ------------------------------------------------------------------ stage 1

    def run_stage1_case(self, case_id: str, path: str) -> TriageCard:
        """Munshi, Peshkar and the Rights Radar on one file; its TriageCard (unranked, no next step yet).

        Args:
            case_id: the case id the queue gave the file
            path: the file, zip or case folder

        Returns:
            TriageCard.
        """
        from vakeel_sahayak.agents.munshi.agent import MunshiAgent
        from vakeel_sahayak.agents.peshkar.agent import PeshkarAgent

        ctx = self._ctx_for(case_id)
        state = CaseGraphState(case_id=case_id, switches=self.switches, as_of=self.as_of, files=[path])
        munshi = MunshiAgent(ctx)
        peshkar = PeshkarAgent(ctx)
        try:
            report = munshi.ingest([path], state)
            sensitive = next((g for g in report.gaps if g.item == "sensitive matter"), None)  # Munshi declined it and filed nothing (plan §16)
            if sensitive is not None:
                from vakeel_sahayak.batch.scheduler import MatterDeclined

                raise MatterDeclined(sensitive.action)
            state = state.model_copy(update={"ingestion": report})
            dossier = peshkar.build_dossier(state)
            peshkar.build_list_of_dates(state)
            rights = peshkar.run_rights_radar(state)
        finally:
            munshi.close()
            peshkar.close()
        gaps = [g.item for g in report.gaps if not g.item.startswith("file ")]
        return make_card(case_id, rights, dossier, gaps)

    def stage1(self, files: list[str]) -> list[TriageCard]:
        """Run Munshi, Peshkar and Rights Radar on every file; one TriageCard each.

        Files are put in the queue (a file seen before keeps its case id and its saved card, so a resumed shard does
        not read it again). The cards come back in urgency order with their next steps decided.

        Args:
            files: the uploaded files, zips or case folders

        Returns:
            Cards.
        """
        ids = self.queue.enqueue_files(files)
        self.message(f"Stage 1 on {len(ids)} file(s).", case_ids=ids)
        cards = self.scheduler.triage_all(self.queue)
        wanted = set(ids)
        cards = [c for c in cards if c.case_id in wanted]
        for card in cards:  # the board reads each case's card from that case's record
            self._write_card(card)
        return cards

    def _write_card(self, card: TriageCard) -> None:
        """Append the card to its own case's record as the `triage_card` view (what `/api/desk/board` reads)."""
        from vakeel_sahayak.schemas.events import Event

        log = self._ctx_for(card.case_id).log
        log.append(Event(event_id="", case_id=card.case_id, ts="", kind=EventKind.STORE_WRITE, actor=self.NAME,
                         inputs={"store": "case.views", "view": "triage_card"}, outputs={"value": card.model_dump(mode="json")}))

    # ------------------------------------------------------------------ decisions

    def _decide_one(self, card: TriageCard) -> str:
        """The decision for a card: the rule, or the model's choice where the rule leaves it open."""
        rule = self.scheduler.decide(card)
        if not self.use_model:
            return rule
        try:
            choice = self.ask(
                TASK_DECIDE,
                USER_PROMPT_TEMPLATES[TASK_DECIDE],
                case={"card": card.model_dump(mode="json", exclude={"case_id"}) | {"case_id": card.case_id}},
                schema=NextStepChoice,
                max_tokens=200,
            )
        except Exception as exc:  # noqa: BLE001 - a model that cannot answer leaves the rule's decision
            self.error("decision_model_failed", type(exc).__name__, case=card.case_id)
            return rule
        picked = getattr(choice, "decision", None)
        if picked not in DECISIONS:
            return rule
        if rule == "flag_counsel" and picked != "flag_counsel":
            self._record(card.case_id, "decision_overruled", "The model's choice was set aside: counsel must see this case now.", {"model": picked, "rule": rule})
            return rule
        return picked

    def decide_next_steps(self, cards: list[TriageCard]) -> list[TriageCard]:
        """Per case: queue a full brief, flag for counsel, or ask for documents first.

        Args:
            cards: cards of one batch

        Returns:
            Cards in the order given (a case facing a statutory bar last), urgency_rank renumbered and next_step set.
        """
        if not self.use_model:
            return self.scheduler.decide_cards(cards)
        out = []
        for card in self.scheduler.reprioritise(cards):
            decision = self._decide_one(card)
            step = next_step_text(decision, card)
            self._record(card.case_id, "decide_next_step", f"Next step decided: {step}.", {"decision": decision, "urgency_rank": card.urgency_rank, "next_step": step})
            out.append(card.model_copy(update={"next_step": step}))
        return out

    # ------------------------------------------------------------------ stage 2

    def run_full_case(self, case_id: str, path: str) -> dict[str, Any]:
        """The full brief for one case: Sutradhar retrieves evidence, Vakeel drafts the brief (Gate 2 stays closed).

        Returns:
            A summary saved with the case: grounds, open issues, whether a statutory bar applies, and the cache counts.
        """
        from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent
        from vakeel_sahayak.agents.vakeel.agent import VakeelAgent

        ctx = self._ctx_for(case_id)
        ctx.tools = guard_tools(ctx.tools)
        state = CaseGraphState(case_id=case_id, switches=self.switches, as_of=self.as_of, before=self.ctx.before).refresh_from_log()
        sutradhar, vakeel = SutradharAgent(ctx), VakeelAgent(ctx)
        try:
            state = sutradhar.run(state)
            state = vakeel.run(state)
        finally:
            sutradhar.close()
            vakeel.close()
        check = state.rights.get("statutory_bar") if state.rights is not None else None
        return {
            "case_id": case_id,
            "grounds": len(state.brief.grounds) if state.brief is not None else 0,
            "open_issues": len(state.brief.open_issues) if state.brief is not None else 0,
            "statutory_bar": bool(check is not None and check.status.value == "BAR_APPLIES"),
            "exported": list(state.exported),
            "cache": self.cache.stats(),
        }

    def stage2(self, cards: list[TriageCard], gpu_budget_hours: float) -> list[str]:
        """Full runs in urgency order within the session budget; save each output as it finishes; no bulk export.

        Args:
            cards: the batch's cards (decided ones; cards without a next step are decided here)
            gpu_budget_hours: GPU-hours this session may spend

        Returns:
            Case ids completed in this call.
        """
        self.queue.add_cases([c.case_id for c in cards])  # a card for a case the queue has not seen (its files are filed already)
        ranked = self.scheduler.reprioritise(cards)
        self.scheduler.cards.update({c.case_id: c for c in ranked})
        for card in ranked:
            decision = self.scheduler.decide(card)
            self.queue.set_plan(card.case_id, decision=decision, urgency_rank=card.urgency_rank, est_hours=self.scheduler.hours_per_case)
            if self.scheduler.needs_full_run(decision, card):
                self.queue.enqueue_stage2(card.case_id)
            else:
                self.queue.skip_stage2(card.case_id)
        done = self.scheduler.run_stage2(self.queue, gpu_budget_hours)
        extra = {"batch_signals": self.batch_signals()} if self._serving_variant() else {}  # S14 arms only: the default message is unchanged
        self.message(f"Stage 2 finished {len(done)} case(s).", case_ids=done, cache=self.cache.stats(), **extra)
        return done

    def _serving_variant(self) -> bool:
        """True when a serving variant (S14 plan cache, S14b / S14c scheduling policy, S14d prefix layout) is on."""
        sw = self.switches
        return bool(sw.plan_cache or sw.urgency_policy != "urgency" or sw.prefix_layout)

    def batch_signals(self) -> dict[str, Any]:
        """Serving signals of this batch (S14): the retrieval cache, the plan cache (hit rate, tokens saved), the scheduling policy (missed deadlines, inversions)
        and the prefix meter (shared prefix tokens), whichever were used."""
        from vakeel_sahayak.batch.cache import plans_of

        out: dict[str, Any] = {"retrieval_cache": self.cache.stats(), "scheduling": self.scheduler.signals(self.queue)}
        plans = plans_of(self.cache).stats()
        if plans["lookups"]:
            out["plan_cache"] = plans
        meter = getattr(self.cache, "__dict__", {}).get("_prefix_meter")
        if meter is not None:
            out["prefix"] = meter.stats()
        return out


__all__ = ["BulkExportError", "PairokarAgent"]
