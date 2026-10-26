"""Batch scheduler (plan §11).

Stage 1 runs on every file: `stage1(case_id, path)` (Munshi + Peshkar + Rights Radar, supplied by the caller, by
default Pairokar's) returns one TriageCard, saved to the queue the moment it is done. Pairokar then decides per case:

- **flag_counsel**: counsel must see this now (a default-bail window open or opening soon, or a rights FLAG). A full
  brief is queued as well when no document is missing.
- **request_documents**: a document is missing and nothing is time-critical, so ask for it before spending GPU time.
- **full_brief**: queue the full run.

Full runs go in urgency order within the session's GPU budget. After each case finishes the order is recomputed: a
case found to face a statutory bar moves behind the others of its group. The queue is the only state, so an
interrupted shard resumes where it stopped and never repeats a finished case.

There is no bulk export, ever. Exporting needs counsel's Gate 2 approval of one case in its own workspace; nothing in
this module exports, and every export entry point here raises `BulkExportError`. A full-run function that reports
exported files is refused too.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from pydantic_core import to_jsonable_python

from vakeel_sahayak.batch.queue import DEFAULT_CASE_HOURS, STAGE1, STAGE2, TriageQueue
from vakeel_sahayak.batch.urgency import (
    CODE_DEFAULT_BAIL_OPEN,
    CODE_DEFAULT_BAIL_SOON,
    card_key,
    has_deadline,
    order_cards,
    parse_reasons,
    rank,
)
from vakeel_sahayak.schemas.triage import TriageCard

FULL_BRIEF, FLAG_COUNSEL, REQUEST_DOCUMENTS = "full_brief", "flag_counsel", "request_documents"
DECISIONS = (FULL_BRIEF, FLAG_COUNSEL, REQUEST_DOCUMENTS)
BAR_TEXT = "statutory bar"  # a card whose flags or reasons say this faces a bar (the Radar's BAR_APPLIES, shown by make_card)
ERROR_PREFIX = "ERROR:"

Stage1Runner = Callable[[str, str], TriageCard]  # (case_id, path) -> the case's card
FullRunner = Callable[[str, str], Any]  # (case_id, path) -> the case's saved output (JSON-able)
EventSink = Callable[[str, str, str, dict[str, Any]], None]  # (case_id, tool, text, outputs)

_BATCH: contextvars.ContextVar[bool] = contextvars.ContextVar("vs_batch_mode", default=False)


class MatterDeclined(Exception):  # noqa: N818 - not an error of the run: the matter is left out on purpose
    """Raised by a stage-1 runner when the file is a sensitive matter (sexual offence, POCSO, juvenile; plan §16): no card, no full run."""


class BulkExportError(PermissionError):
    """Raised on any attempt to export from the batch path: every case needs its own approval (plan §11)."""


def batch_mode_active() -> bool:
    """True while the batch desk is running a case."""
    return _BATCH.get()


@contextmanager
def batch_mode() -> Iterator[None]:
    """Mark the code inside as the batch path (export is refused here)."""
    token = _BATCH.set(True)
    try:
        yield
    finally:
        _BATCH.reset(token)


def refuse_export(*_args: Any, **_kwargs: Any) -> Any:
    """Always raises: the batch path never exports."""
    raise BulkExportError("no bulk export: each case's export needs counsel's own Gate 2 approval, given in that case's workspace")


def guard_tools(tools: dict[str, Callable[..., Any]] | None = None) -> dict[str, Callable[..., Any]]:
    """A toolbox for batch runs: `export` replaced by one that refuses (pass it as `AgentContext.tools`)."""
    guarded = dict(tools or {})
    guarded["export"] = refuse_export
    return guarded


def _exported(result: Any) -> list[str]:
    """Exported files a full-run result reports (a dict with 'exported', or a state with `.exported`)."""
    value = result.get("exported") if isinstance(result, dict) else getattr(result, "exported", None)
    return [str(x) for x in value] if isinstance(value, (list, tuple)) and value else []


def _found_bar(result: Any) -> bool:
    """True when a full-run result says the case faces a statutory bar."""
    if isinstance(result, dict):
        return bool(result.get("statutory_bar")) or any(BAR_TEXT in str(f).lower() for f in result.get("flags") or [])
    rights = getattr(result, "rights", None)
    check = rights.get("statutory_bar") if rights is not None and hasattr(rights, "get") else None
    return bool(check is not None and getattr(check.status, "value", check.status) == "BAR_APPLIES")


def _default_bail_deadline(card: TriageCard) -> bool:
    """True when a reason says a default-bail window is open or opens soon (not one that has closed)."""
    found = parse_reasons(card.reasons)
    if CODE_DEFAULT_BAIL_OPEN in found or CODE_DEFAULT_BAIL_SOON in found:
        return True
    return any("default-bail" in r.lower() and "closed" not in r.lower() for r in card.reasons)


def next_step_text(decision: str, card: TriageCard) -> str:
    """The next step as the TriageCard says it (plan §11 example: 'full brief queued; flag default-bail window to counsel')."""
    why = "default-bail window" if _default_bail_deadline(card) else None
    docs = ", ".join(card.missing_docs)
    if decision == REQUEST_DOCUMENTS:
        return f"request documents first: {docs}"
    if decision == FLAG_COUNSEL:
        flag = f"flag {why} to counsel" if why else "flag to counsel: " + "; ".join(f for f in card.flags if f.startswith("FLAG:"))
        return f"{flag}; request documents: {docs}" if card.missing_docs else f"full brief queued; {flag}"
    return "full brief queued"


class Scheduler:
    """Decides per case: queue a full brief, flag for counsel, or ask for documents first; re-prioritises as results arrive (plan §11)."""

    def __init__(
        self,
        stage1: Stage1Runner | None = None,
        full_run: FullRunner | None = None,
        *,
        session_hours: float | None = None,
        hours_per_case: float = DEFAULT_CASE_HOURS,
        owner: str = "pairokar",
        on_event: EventSink | None = None,
        policy: str = "urgency",
        sizes: dict[str, float] | None = None,
    ) -> None:
        """Create the scheduler.

        Args:
            stage1: (case_id, path) -> TriageCard; cheap, runs on every file
            full_run: (case_id, path) -> the case's saved output; runs only for cases decided for a full brief
            session_hours: GPU-hours of this session (the default budget of `run_stage2`; None: no limit)
            hours_per_case: GPU-hours one full run is planned at
            owner: the worker name written on claims
            on_event: called with (case_id, tool, text, outputs) for every decision, so the caller can log it
            policy: `Switches.urgency_policy` (S14b / S14c): 'urgency' (default, the fixed rule), 'fifo', 'urgency_least_work' or 'shortest_first'
            sizes: planned size of each case's full run for 'shortest_first' (case id -> hours; missing = equal)
        """
        self.stage1 = stage1
        self.full_run = full_run
        self.session_hours = session_hours
        self.hours_per_case = hours_per_case
        self.owner = owner
        self.on_event = on_event
        self.cards: dict[str, TriageCard] = {}
        self._barred: set[str] = set()  # cases found, by their full run, to face a statutory bar
        self.policy = policy
        self.sizes = dict(sizes or {})
        self.completed: list[str] = []  # case ids in the order their full runs finished (for the S14 signals; in memory only)

    # ------------------------------------------------------------------ events and refusals

    def _emit(self, case_id: str, tool: str, text: str, **outputs: Any) -> None:
        if self.on_event is not None:
            self.on_event(case_id, tool, text, outputs)

    def export(self, *args: Any, **kwargs: Any) -> Any:
        """Refused: no bulk export."""
        return refuse_export(*args, **kwargs)

    export_all = export_batch = bulk_export = export

    # ------------------------------------------------------------------ stage 1

    def triage_all(self, queue: TriageQueue) -> list[TriageCard]:
        """Stage 1: Munshi, Peshkar and Rights Radar on every file (cheap); then decide and queue.

        Files already done keep their saved cards (a resumed shard does not read them again); files whose job failed
        for good get a placeholder card ranked after the rest.

        Args:
            queue: the batch queue

        Returns:
            Cards in urgency order (urgency_rank 1 first), each with its next step.
        """
        if self.stage1 is None:
            raise RuntimeError("the scheduler has no stage-1 runner")
        queue.reclaim_expired()
        while True:
            waiting = queue.pending_ids(STAGE1)
            if not waiting:
                break
            claimed = queue.claim(STAGE1, owner=self.owner, limit=1, case_ids=waiting)
            if not claimed:
                break
            cid = claimed[0]
            try:
                with batch_mode():
                    card = self.stage1(cid, queue.path_of(cid))
                card = card.model_copy(update={"case_id": cid})
            except (KeyboardInterrupt, SystemExit):
                queue.release(cid, STAGE1)
                raise
            except MatterDeclined as exc:
                queue.decline(cid, str(exc))
                self._emit(cid, "stage1_declined", "Declined at intake: a sensitive matter is left out of the batch.", reason=str(exc))
                continue
            except Exception as exc:  # noqa: BLE001 - one unreadable file must not stop the shard
                status = queue.fail(cid, f"{type(exc).__name__}: {exc}", STAGE1)
                self._emit(cid, "stage1_failed", f"Stage 1 failed ({status}).", error=type(exc).__name__, status=status)
                continue
            queue.mark_done(cid, card, STAGE1)
            self._emit(cid, "stage1_done", "Stage 1 finished.", reasons=card.reasons, flags=card.flags, missing_docs=card.missing_docs)
        return self.plan(queue)

    def _stage1_cards(self, queue: TriageQueue) -> list[TriageCard]:
        cards = [TriageCard.model_validate(queue.result(c, STAGE1)) for c in queue.done_ids(STAGE1)]
        for cid in queue.failed_ids(STAGE1):
            err = queue.error_of(cid, STAGE1) or "unreadable"
            cards.append(TriageCard(case_id=cid, urgency_rank=0, flags=[f"{ERROR_PREFIX} stage 1 failed: {err[:120]}"], missing_docs=["a readable copy of the file"]))
        return cards

    # ------------------------------------------------------------------ decide, rank, plan

    def decide(self, card: TriageCard) -> str:
        """full_brief | flag_counsel | request_documents.

        flag_counsel when a reason says a default-bail window is open or opening soon, or a rights FLAG stands (counsel must see it
        now, whatever is missing). Otherwise request_documents when a document is missing, else full_brief.

        Args:
            card: the case's card

        Returns:
            Decision.
        """
        if _default_bail_deadline(card) or any(f.startswith("FLAG:") for f in card.flags):
            return FLAG_COUNSEL
        if card.missing_docs or any(f.startswith(ERROR_PREFIX) for f in card.flags):
            return REQUEST_DOCUMENTS
        return FULL_BRIEF

    @staticmethod
    def needs_full_run(decision: str, card: TriageCard) -> bool:
        """True when the decision queues a full brief (a flagged case too, unless a document is missing)."""
        return decision == FULL_BRIEF or (decision == FLAG_COUNSEL and not card.missing_docs)

    def decide_cards(self, cards: list[TriageCard]) -> list[TriageCard]:
        """Set each card's next_step from its decision and log every decision.

        The cards keep the order they come in (rank them first with `urgency.rank`), except that a case facing a
        statutory bar goes to the end (`reprioritise`).

        Args:
            cards: the batch's cards

        Returns:
            Cards with urgency_rank renumbered and next_step set.
        """
        out: list[TriageCard] = []
        for card in self.reprioritise(cards):
            decision = self.decide(card)
            step = next_step_text(decision, card)
            self._emit(card.case_id, "decide_next_step", f"Next step decided: {step}.", decision=decision, urgency_rank=card.urgency_rank, next_step=step)
            out.append(card.model_copy(update={"next_step": step}))
        return out

    def plan(self, queue: TriageQueue) -> list[TriageCard]:
        """Decide for every case with a finished stage 1, save the plan and queue the full runs.

        Returns:
            Cards in urgency order with next_step set.
        """
        cards = self._order(self._stage1_cards(queue), queue)
        for cid in queue.done_ids(STAGE2):
            res = queue.result(cid, STAGE2)
            if res is not None and _found_bar(res):
                self._barred.add(cid)
        decided = self.decide_cards(cards)
        for card in decided:
            decision = self.decide(card)
            queue.set_plan(card.case_id, decision=decision, urgency_rank=card.urgency_rank, est_hours=self.hours_per_case)
            if self.needs_full_run(decision, card):
                if queue.enqueue_stage2(card.case_id):
                    self._emit(card.case_id, "queue_full_run", "Full brief queued.", urgency_rank=card.urgency_rank)
            else:
                queue.skip_stage2(card.case_id)
        self.cards = {c.case_id: c for c in decided}
        return decided

    def _order(self, cards: list[TriageCard], queue: TriageQueue | None = None) -> list[TriageCard]:
        """Cards in the order of the scheduling policy (the default is `urgency.rank`, as before)."""
        if self.policy == "urgency":
            return rank(cards)
        arrival = {cid: i for i, cid in enumerate(queue.case_ids())} if queue is not None else {}
        work: dict[str, float] = {}
        if self.policy == "urgency_least_work" and queue is not None:  # attained service: planned hours of a full run times the attempts it has had
            for c in cards:
                work[c.case_id] = float(queue.plan_of(c.case_id)["est_hours"] or self.hours_per_case) * queue.attempts(c.case_id, STAGE2)
        return order_cards(cards, self.policy, arrival=arrival, work=work, sizes=self.sizes)

    def reprioritise(self, cards: list[TriageCard]) -> list[TriageCard]:
        """e.g. a case found to face a statutory bar moves down.

        Cards are taken in their current urgency order (cards with no rank keep the order they came in, after the
        ranked ones); a case that faces a statutory bar (a flag or reason says so, or its full run found one) moves to
        the end; the others keep their relative order. Ranks are renumbered 1..n.

        Args:
            cards: the batch's cards

        Returns:
            Reordered cards.
        """
        ordered = sorted(cards, key=lambda c: c.urgency_rank if c.urgency_rank > 0 else 10**9)
        if self.policy in ("fifo", "shortest_first"):  # baselines that do not use the urgency rule keep their own order (no statutory-bar demotion)
            return [c.model_copy(update={"urgency_rank": i}) for i, c in enumerate(ordered, start=1)]
        barred = [c for c in ordered if self._faces_bar(c)]
        rest = [c for c in ordered if not self._faces_bar(c)]
        return [c.model_copy(update={"urgency_rank": i}) for i, c in enumerate([*rest, *barred], start=1)]

    def _faces_bar(self, card: TriageCard) -> bool:
        return card.case_id in self._barred or any(BAR_TEXT in t.lower() for t in [*card.flags, *card.reasons])

    # ------------------------------------------------------------------ stage 2

    def run_stage2(self, queue: TriageQueue, gpu_budget_hours: float | None = None, *, stop_after: int | None = None) -> list[str]:
        """Run full runs in urgency order; vLLM prefix caching covers shared prompts.

        Each finished case is saved at once (`queue.mark_done` with its output). A run that fails is retried until
        the queue's attempt limit; an interrupt (Ctrl-C, shard ending) hands the case back without costing an attempt.
        After every case the order is recomputed, so a bar found by a run moves that case down.

        Args:
            queue: the batch queue
            gpu_budget_hours: GPU-hours this session may spend (default: the scheduler's `session_hours`; None: no limit)
            stop_after: finish at most this many cases in this call (ends a shard early)

        Returns:
            Case ids completed in this call, in the order they finished.

        Raises:
            BulkExportError: a full run reported exported files.
        """
        if self.full_run is None:
            raise RuntimeError("the scheduler has no full-run function")
        budget = gpu_budget_hours if gpu_budget_hours is not None else self.session_hours
        left = float("inf") if budget is None else float(budget)
        done: list[str] = []
        queue.reclaim_expired()
        while stop_after is None or len(done) < stop_after:
            cid = next((c for c in queue.next_stage2(left)), None)
            if cid is None:
                break
            if not queue.claim(STAGE2, owner=self.owner, case_ids=[cid]):
                break
            hours = float(queue.plan_of(cid)["est_hours"] or self.hours_per_case)
            try:
                with batch_mode():
                    result = self.full_run(cid, queue.path_of(cid))
                if _exported(result):
                    raise BulkExportError(f"full run of {cid} exported files; batch runs never export")
            except (KeyboardInterrupt, SystemExit):
                queue.release(cid, STAGE2)
                raise
            except BulkExportError:
                queue.fail(cid, "attempted export in batch mode")
                self._emit(cid, "export_refused", "Export refused: no bulk export; counsel approves each case's export on its own.")
                raise
            except Exception as exc:  # noqa: BLE001 - one failing case must not end the shard
                status = queue.fail(cid, f"{type(exc).__name__}: {exc}")
                left -= hours
                self._emit(cid, "stage2_failed", f"Full run failed ({status}).", error=type(exc).__name__, status=status)
                continue
            payload = to_jsonable_python(result, fallback=str)
            queue.mark_done(cid, payload)
            left -= hours
            done.append(cid)
            self.completed.append(cid)
            self._emit(cid, "stage2_done", "Full run finished and saved.", hours=hours)
            if _found_bar(result) and cid not in self._barred:
                self._barred.add(cid)
                self._emit(cid, "reprioritise", "A statutory bar was found; this case moves down.", statutory_bar=True)
            self._reorder(queue)
        return done

    def _reorder(self, queue: TriageQueue) -> None:
        """Recompute ranks from the cards and write them to the queue, so the next claim follows the new order."""
        if not self.cards:
            self.cards = {c.case_id: c for c in self._stage1_cards(queue)}
        cards = list(self.cards.values())
        if self.policy == "urgency_least_work":  # the work done changes after every case: order again
            cards = self._order(cards, queue)
        ranked = self.reprioritise(cards)
        self.cards = {c.case_id: c for c in ranked}
        queue.set_ranks({c.case_id: c.urgency_rank for c in ranked})

    def signals(self, queue: TriageQueue | None = None) -> dict[str, Any]:
        """S14b / S14c signals over the cards of this scheduler: the policy, cases with a legal deadline, those not finished (missed), inversions and completion order.

        A deadline case counts as missed when it needs a full run and that run has not finished (the session budget ended first); an inversion is a case
        without a legal deadline whose full run finished before one with a deadline.

        Args:
            queue: the batch queue, to read which full runs are done (default: the scheduler's own `completed` list)

        Returns:
            dict: `policy`, `deadline_cases`, `missed_deadlines`, `inversions`, `completed` (case ids in finish order), `needing_full_run`.
        """
        done = set(queue.done_ids(STAGE2)) if queue is not None else set(self.completed)
        wanted = [c for c in self.cards.values() if self.needs_full_run(self.decide(c), c)]
        deadline = [c.case_id for c in wanted if has_deadline(c)]
        order = [c for c in self.completed if c in {w.case_id for w in wanted}]
        inversions = sum(1 for i, a in enumerate(order) for b in order[i + 1:] if a not in deadline and b in deadline)
        return {"policy": self.policy, "deadline_cases": len(deadline), "missed_deadlines": sum(1 for c in deadline if c not in done),
                "inversions": inversions, "completed": list(self.completed), "needing_full_run": len(wanted)}

    def resume(self, queue: TriageQueue) -> list[tuple[str, str]]:
        """Start of a new session after a shard died: give back every job the old session still held.

        Only call when no other worker is running on this queue file.

        Returns:
            (case_id, phase) of the jobs given back.
        """
        freed = queue.release_all_claims()
        for cid, phase in freed:
            self._emit(cid, "resume", f"Interrupted {phase} job returned to the queue.", phase=phase)
        return freed


__all__ = ["DECISIONS", "BulkExportError", "Scheduler", "batch_mode", "batch_mode_active", "card_key", "guard_tools", "next_step_text", "refuse_export"]
