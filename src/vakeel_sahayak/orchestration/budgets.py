"""Per-case and per-factor budgets (plan §6.2).

Defaults come from configs/budgets.yaml (150K tokens per case; 8 store calls and 12K tokens per factor); a factor's
evidence contract may set its own limits (`set_factor_limits`). Spend is tracked per factor and for the case; every
time a budget is hit a BUDGET_HIT event is appended to the case's event log (once per budget and scope), and the UI
shows `snapshot()`.

A budget is *spent* when use reaches the cap: after the 8th store call of a factor, `exhausted(factor)` is True and
`BaseAgent.call_tool` refuses the 9th with a `budget_exhausted` ToolError. Token budgets are charged by
`BaseAgent`'s LLM calls; a call that would start with nothing left raises `BudgetExhausted`.

Two token pools per factor (bug fix of the first hosted pilot): the 12K cap is the *retrieval* pool (Sutradhar's planning and
query rewording, Peshkar, Munshi), and the drafting stage (Vakeel's draft, check-and-repair and replies, Abhiyojak's objections
and reply judging) has its own pool `drafting_tokens_per_factor` (16K, measured: the downstream steps of one factor used about
12K with the hosted model, `data/eval/token_measure.json` and `docs/handoff/pilot-hosted-model.md`). Before, both stages shared 12K,
so the repair and judge-reply steps were starved after retrieval and drafting had spent it. The case cap still bounds the total.
A charge without an actor counts as retrieval, as before.

The tracker is thread-safe (factors run in parallel, plan §6.2 step 2) and rebuildable from the event log after a
resume (`from_events`): every charge made through `BaseAgent` is recorded in its event's outputs under `budget_charge`.
"""

from __future__ import annotations

import threading
from typing import Any

from vakeel_sahayak.schemas.case import BudgetState
from vakeel_sahayak.schemas.enums import AgentName, EventKind
from vakeel_sahayak.schemas.retrieval_plan import BudgetLeft

DRAFTING_ACTORS = frozenset({"VAKEEL", "ABHIYOJAK"})  # their LLM calls are charged to the factor's drafting pool
CASE_SCOPE = "case"  # key of unscoped (case-level) store calls in BudgetState.store_calls


class BudgetExhausted(RuntimeError):
    """An LLM call or tool call was refused because its budget is spent.

    Attributes:
        scope: 'factor' or 'case'
        factor: the factor, when the factor budget is spent
        limit: 'tokens' or 'store_calls'
    """

    def __init__(self, message: str, scope: str, factor: str | None, limit: str) -> None:
        """Keep which budget was spent."""
        super().__init__(message)
        self.scope, self.factor, self.limit = scope, factor, limit


def _actor_name(actor: Any) -> str | None:
    """Agent enum or string to its name ('VAKEEL'); None stays None."""
    if actor is None:
        return None
    return str(getattr(actor, "value", actor)).upper()


def _key(factor: Any) -> str | None:
    """Factor enum or string to its value (None stays None)."""
    if factor is None:
        return None
    return str(getattr(factor, "value", factor))


class BudgetTracker:
    """Tracks tokens and store calls per case and per factor; logs every time a budget is hit (plan §6.2)."""

    def __init__(
        self,
        tokens_per_case: int = 150000,
        store_calls_per_factor: int = 8,
        tokens_per_factor: int = 12000,
        *,
        drafting_tokens_per_factor: int = 16000,
        log: Any = None,
        case_id: str | None = None,
        actor: AgentName | str = AgentName.SUTRADHAR,
    ) -> None:
        """Create a tracker.

        Args:
            tokens_per_case: token cap for the whole case
            store_calls_per_factor: store-call cap per factor
            tokens_per_factor: token cap per factor for the retrieval stage (Sutradhar, Peshkar, Munshi)
            drafting_tokens_per_factor: token cap per factor for the drafting stage (Vakeel, Abhiyojak)
            log: the case's EventLog for BUDGET_HIT events (None: hits are kept in `hits` only)
            case_id: the case (needed to log)
            actor: default actor of BUDGET_HIT events (the agent charging may override it)
        """
        self.tokens_per_case = int(tokens_per_case)
        self.store_calls_per_factor = int(store_calls_per_factor)
        self.tokens_per_factor = int(tokens_per_factor)
        self.drafting_tokens_per_factor = int(drafting_tokens_per_factor)
        self.log, self.case_id, self.actor = log, case_id, actor
        self._lock = threading.RLock()
        self._case_tokens = 0
        self._factor_tokens: dict[str, int] = {}  # retrieval pool
        self._draft_tokens: dict[str, int] = {}  # drafting pool
        self._store_calls: dict[str, int] = {}
        self._limits: dict[str, tuple[int, int]] = {}  # factor -> (store_calls, tokens)
        self._hit_keys: set[tuple[str, str | None, str]] = set()
        self.hits: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ construction

    @classmethod
    def from_config(cls, config: Any = None, *, log: Any = None, case_id: str | None = None, actor: AgentName | str = AgentName.SUTRADHAR) -> BudgetTracker:
        """A tracker with the limits of configs/budgets.yaml.

        Args:
            config: AppConfig or BudgetConfig (default: load_config())
            log: the case's event log
            case_id: the case
            actor: default actor of BUDGET_HIT events

        Returns:
            BudgetTracker.
        """
        if config is None:
            from vakeel_sahayak.config import load_config

            config = load_config()
        b = getattr(config, "budgets", config)
        return cls(b.tokens_per_case, b.store_calls_per_factor, b.tokens_per_factor, drafting_tokens_per_factor=getattr(b, "drafting_tokens_per_factor", 16000), log=log, case_id=case_id, actor=actor)

    @classmethod
    def from_events(cls, events: list[Any], config: Any = None, *, log: Any = None, case_id: str | None = None) -> BudgetTracker:
        """Rebuild spend after a resume from the `budget_charge` records in event outputs (plan §17).

        Args:
            events: the case's events, in order
            config: AppConfig or BudgetConfig (default: load_config())
            log: the event log to keep logging into
            case_id: the case

        Returns:
            BudgetTracker with the recorded spend (no new BUDGET_HIT events are written while replaying).
        """
        tracker = cls.from_config(config, log=None, case_id=case_id)
        for ev in events:
            charge = (getattr(ev, "outputs", None) or {}).get("budget_charge")
            if isinstance(charge, dict):
                tracker.charge(charge.get("factor"), int(charge.get("tokens", 0)), int(charge.get("store_calls", 0)), actor=getattr(ev, "actor", None))
            if getattr(ev, "kind", None) == EventKind.BUDGET_HIT:
                inputs = getattr(ev, "inputs", {}) or {}
                tracker._hit_keys.add((str(inputs.get("scope")), inputs.get("factor"), str(inputs.get("limit"))))
        tracker.log = log
        return tracker

    def bind(self, log: Any, case_id: str) -> None:
        """Attach the case's event log (for trackers created before the log)."""
        self.log, self.case_id = log, case_id

    def set_factor_limits(self, factor: Any, store_calls: int | None = None, tokens: int | None = None) -> None:
        """Use a factor's own limits (its evidence contract's `budget`) instead of the defaults."""
        key = _key(factor)
        assert key is not None
        with self._lock:
            sc, tk = self._limits.get(key, (self.store_calls_per_factor, self.tokens_per_factor))
            self._limits[key] = (int(store_calls) if store_calls is not None else sc, int(tokens) if tokens is not None else tk)

    def limits(self, factor: Any) -> tuple[int, int]:
        """(store-call cap, token cap) of a factor."""
        key = _key(factor)
        return self._limits.get(key or "", (self.store_calls_per_factor, self.tokens_per_factor))

    # ------------------------------------------------------------------ spend

    def charge(self, factor: str | None, tokens: int = 0, store_calls: int = 0, *, actor: AgentName | str | None = None) -> None:
        """Record spend.

        Args:
            factor: the factor the spend belongs to (None: case level only)
            tokens: tokens spent (count toward the factor and the case)
            store_calls: store calls made
            actor: who spent it (actor of a BUDGET_HIT event this charge triggers)
        """
        key = _key(factor)
        with self._lock:
            self._case_tokens += int(tokens)
            if key is not None:
                pool = self._draft_tokens if _actor_name(actor) in DRAFTING_ACTORS else self._factor_tokens
                pool[key] = pool.get(key, 0) + int(tokens)
            if store_calls:
                slot = key or CASE_SCOPE
                self._store_calls[slot] = self._store_calls.get(slot, 0) + int(store_calls)
        self._check_hits(key, actor)

    def spent(self, factor: str | None = None) -> tuple[int, int]:
        """(tokens, store calls) spent by a factor, or by the case when factor is None."""
        key = _key(factor)
        with self._lock:
            if key is None:
                return self._case_tokens, sum(self._store_calls.values())
            return self._factor_tokens.get(key, 0) + self._draft_tokens.get(key, 0), self._store_calls.get(key, 0)

    def left(self, factor: str | None = None) -> BudgetLeft:
        """Remaining budget (for RetrievalPlan.budget_left).

        Args:
            factor: the factor; None gives the case-level view (tokens left in the case; store calls a fresh factor gets)

        Returns:
            BudgetLeft (never negative). A factor's tokens are capped by what the case has left.
        """
        key = _key(factor)
        with self._lock:
            case_left = max(0, self.tokens_per_case - self._case_tokens)
            if key is None:
                return BudgetLeft(store_calls=self.store_calls_per_factor, tokens=case_left)
            sc_cap, tk_cap = self.limits(key)
            return BudgetLeft(
                store_calls=max(0, sc_cap - self._store_calls.get(key, 0)),
                tokens=min(case_left, max(0, tk_cap - self._factor_tokens.get(key, 0))),
            )

    def _spent_budgets(self, key: str | None) -> list[tuple[str, str | None, str, int, int]]:
        """(scope, factor, limit, spent, cap) for every budget that is spent."""
        out = []
        if self._case_tokens >= self.tokens_per_case:
            out.append(("case", None, "tokens", self._case_tokens, self.tokens_per_case))
        if key is not None:
            sc_cap, tk_cap = self.limits(key)
            if self._store_calls.get(key, 0) >= sc_cap:
                out.append(("factor", key, "store_calls", self._store_calls.get(key, 0), sc_cap))
            if self._factor_tokens.get(key, 0) >= tk_cap:
                out.append(("factor", key, "tokens", self._factor_tokens.get(key, 0), tk_cap))
            if self._draft_tokens.get(key, 0) >= self.drafting_tokens_per_factor:
                out.append(("factor", key, "drafting_tokens", self._draft_tokens.get(key, 0), self.drafting_tokens_per_factor))
        return out

    def exhausted(self, factor: str | None = None, *, actor: AgentName | str | None = None) -> bool:
        """True when the budget for the factor or case is spent; emits a BUDGET_HIT event.

        Args:
            factor: the factor (its store calls and tokens, and the case's tokens), or None for the case only
            actor: who asked (actor of the event)

        Returns:
            bool.
        """
        key = _key(factor)
        with self._lock:
            spent = self._spent_budgets(key)
        self._check_hits(key, actor)
        return bool(spent)

    def store_calls_exhausted(self, factor: str | None) -> bool:
        """True when the factor's store calls (or the case's tokens) are spent: the next store call must be refused."""
        key = _key(factor)
        with self._lock:
            spent = [s for s in self._spent_budgets(key) if s[2] == "store_calls" or s[0] == "case"]
        self._check_hits(key, None)
        return bool(spent)

    def tokens_exhausted(self, factor: str | None, actor: AgentName | str | None = None) -> bool:
        """True when the token budget the next LLM call draws on is spent, so the call must be refused.

        Args:
            factor: the factor (None: the case budget only)
            actor: who is about to call; Vakeel and Abhiyojak draw on the factor's drafting pool, everyone else on its retrieval pool
        """
        key = _key(factor)
        want = "drafting_tokens" if _actor_name(actor) in DRAFTING_ACTORS else "tokens"
        with self._lock:
            spent = [s for s in self._spent_budgets(key) if s[2] == want or (s[0] == "case" and s[2] == "tokens")]
        self._check_hits(key, None)
        return bool(spent)

    def _check_hits(self, key: str | None, actor: AgentName | str | None) -> None:
        """Log each newly spent budget once."""
        with self._lock:
            fresh = [s for s in self._spent_budgets(key) if (s[0], s[1], s[2]) not in self._hit_keys]
            for scope, factor, limit, spent, cap in fresh:
                self._hit_keys.add((scope, factor, limit))
                self.hits.append({"scope": scope, "factor": factor, "limit": limit, "spent": spent, "cap": cap})
        for scope, factor, limit, spent, cap in fresh:
            self._log_hit(scope, factor, limit, spent, cap, actor)

    def _log_hit(self, scope: str, factor: str | None, limit: str, spent: int, cap: int, actor: AgentName | str | None) -> None:
        if self.log is None or not self.case_id:
            return
        from vakeel_sahayak.schemas.events import Event

        self.log.append(
            Event(
                event_id="",
                case_id=self.case_id,
                ts="",
                kind=EventKind.BUDGET_HIT,
                actor=actor or self.actor,
                inputs={"scope": scope, "factor": factor, "limit": limit},
                outputs={"spent": spent, "cap": cap, "budget": self.snapshot().model_dump(mode="json")},
            )
        )

    def snapshot(self) -> BudgetState:
        """Spend shown in the UI.

        Returns:
            BudgetState (store calls per factor; unscoped calls under 'case').
        """
        with self._lock:
            return BudgetState(tokens_spent=self._case_tokens, tokens_cap=self.tokens_per_case, store_calls=dict(self._store_calls))

    def to_dict(self) -> dict[str, Any]:
        """JSON-able state for a graph checkpoint."""
        with self._lock:
            return {
                "limits": {"tokens_per_case": self.tokens_per_case, "store_calls_per_factor": self.store_calls_per_factor,
                           "tokens_per_factor": self.tokens_per_factor, "drafting_tokens_per_factor": self.drafting_tokens_per_factor, "factors": {k: list(v) for k, v in self._limits.items()}},
                "case_tokens": self._case_tokens, "factor_tokens": dict(self._factor_tokens), "draft_tokens": dict(self._draft_tokens),
                "store_calls": dict(self._store_calls), "hits": [list(k) for k in sorted(self._hit_keys, key=str)],
            }  # fmt: skip

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, log: Any = None, case_id: str | None = None) -> BudgetTracker:
        """Restore a tracker saved with `to_dict`."""
        lim = data.get("limits", {})
        tracker = cls(lim.get("tokens_per_case", 150000), lim.get("store_calls_per_factor", 8), lim.get("tokens_per_factor", 12000), drafting_tokens_per_factor=lim.get("drafting_tokens_per_factor", 16000), log=log, case_id=case_id)
        tracker._limits = {k: (int(v[0]), int(v[1])) for k, v in (lim.get("factors") or {}).items()}
        tracker._case_tokens = int(data.get("case_tokens", 0))
        tracker._factor_tokens = {k: int(v) for k, v in (data.get("factor_tokens") or {}).items()}
        tracker._draft_tokens = {k: int(v) for k, v in (data.get("draft_tokens") or {}).items()}
        tracker._store_calls = {k: int(v) for k, v in (data.get("store_calls") or {}).items()}
        tracker._hit_keys = {(str(h[0]), h[1], str(h[2])) for h in data.get("hits", [])}
        return tracker
