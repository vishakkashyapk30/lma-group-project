"""Switches.sparring_reserve_tokens: a separate token pool for the sparring step (post-freeze, 2026-11-15).

Engineering fix for a measured budget misallocation (docs/handoff/objections-unanswered-2026-11-15.md). Default 0 changes nothing.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from tests.unit.agents._helpers import build_agent
from tests.unit.agents.abhiyojak.test_agent import TABLE, state, three_objections, verdict_llm  # noqa: F401  (state is a fixture)
from vakeel_sahayak.agents.abhiyojak.agent import AbhiyojakAgent
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches, production_switches
from vakeel_sahayak.schemas.enums import EventKind, SparringVerdict

F = "parity_with_co_accused"
UNJUDGED = "The reply could not be judged; counsel to read it."


def _starved() -> BudgetTracker:
    """A tracker whose drafting pool for the factor is already spent (the measured situation)."""
    t = BudgetTracker(drafting_tokens_per_factor=100)
    t.charge(F, 500, actor="VAKEEL")
    assert t.tokens_exhausted(F, "ABHIYOJAK")
    return t


def test_default_is_zero_and_only_the_product_preset_turns_it_on():
    assert Switches().sparring_reserve_tokens == 0
    assert Switches().variant() == "full"
    assert production_switches().sparring_reserve_tokens == 60000
    for name in ("A8", "S3", "X1", "H1"):
        assert Switches.for_variant(name).sparring_reserve_tokens == 0


def test_tracker_without_reserve_is_unchanged():
    t = BudgetTracker()
    t.charge(F, 100, actor="ABHIYOJAK")
    assert t.spent(None)[0] == 100 and t.snapshot().tokens_cap == 150000
    assert "sparring" not in t.to_dict()
    assert t.tokens_exhausted(F, "ABHIYOJAK", pool="sparring") is False  # no reserve: the pool argument is ignored


def test_default_still_refuses_after_drafting_pool_is_spent(state):  # noqa: F811
    agent, _, _ = build_agent(AbhiyojakAgent, llm=verdict_llm(TABLE), budgets=_starved())
    out = agent.judge_replies(state, three_objections())
    assert all(o.verdict == SparringVerdict.UNANSWERED and o.reason == UNJUDGED for o in out)


def test_reserve_lets_judge_succeed_and_is_not_charged_to_the_drafting_pool(state):  # noqa: F811
    t = _starved()
    drafting_before = t.spent(F)[0]
    agent, ctx, _ = build_agent(AbhiyojakAgent, llm=verdict_llm(TABLE), budgets=t, switches=Switches(sparring_reserve_tokens=5000))
    out = agent.judge_replies(state, three_objections())
    assert [o.verdict for o in out] == [SparringVerdict.ANSWERED, SparringVerdict.PARTLY, SparringVerdict.UNANSWERED]
    assert not any(o.reason == UNJUDGED for o in out)
    assert t.spent(F)[0] == drafting_before  # the factor pools did not move
    snap = t.to_dict()["sparring"]
    assert snap["reserve"] == 5000 and snap["spent"] > 0
    assert t.snapshot().tokens_cap == 150000 + 5000 and t.snapshot().tokens_spent == 500 + snap["spent"]
    charged = [e.outputs["budget_charge"] for e in ctx.log.events if (e.outputs or {}).get("budget_charge")]
    assert charged and all(c.get("pool") == "sparring" for c in charged)
    ev = [e for e in ctx.log.events if e.outputs and e.outputs.get("reserve") == 5000]
    assert ev and ev[-1].outputs["spent"] == snap["spent"] and ev[-1].outputs["left"] == 5000 - snap["spent"]


def test_reserve_runs_out_then_the_old_refusal_and_fail_safe_hold(state):  # noqa: F811
    t = _starved()
    agent, ctx, _ = build_agent(AbhiyojakAgent, llm=verdict_llm(TABLE), budgets=t, switches=Switches(sparring_reserve_tokens=1))
    out = agent.judge_replies(state, three_objections())
    # the first call spends the whole 1-token reserve; the others are refused as before
    assert out[0].reason != UNJUDGED
    assert [o.reason for o in out[1:]] == [UNJUDGED, UNJUDGED]
    assert all(o.verdict == SparringVerdict.UNANSWERED for o in out[1:])
    hits = [e for e in ctx.log.events if e.kind == EventKind.BUDGET_HIT and (e.inputs or {}).get("scope") == "sparring"]
    assert len(hits) == 1


def test_reserve_is_not_spent_by_drafting_calls():
    t = BudgetTracker()
    t.set_sparring_reserve(1000)
    t.charge(F, 700, actor="VAKEEL")  # drafting: no pool
    assert t.to_dict()["sparring"]["spent"] == 0
    t.charge(F, 1000, actor="ABHIYOJAK", pool="sparring")
    assert t.tokens_exhausted(F, "ABHIYOJAK", pool="sparring")
    assert not t.tokens_exhausted("flight_risk", "SUTRADHAR")  # retrieval of other factors is unaffected
    assert not t.exhausted(None)


def test_reserve_survives_checkpoint_and_event_replay():
    t = BudgetTracker()
    t.set_sparring_reserve(1000)
    t.charge(F, 400, actor="ABHIYOJAK", pool="sparring")
    back = BudgetTracker.from_dict(json.loads(json.dumps(t.to_dict())))
    assert back.sparring_reserve_tokens == 1000 and back.spent(None)[0] == 400
    charge = {"factor": F, "tokens": 400, "store_calls": 0, "pool": "sparring"}
    ev = SimpleNamespace(outputs={"budget_charge": charge}, actor="ABHIYOJAK", kind=EventKind.AGENT_MESSAGE, inputs={})
    assert BudgetTracker.from_events([ev]).to_dict()["sparring"]["spent"] == 400


def test_vakeel_replies_and_abhiyojak_objections_run_in_the_sparring_scope(state, monkeypatch):  # noqa: F811
    """Vakeel's reply path (and so its reply-repair) and Abhiyojak's objections are inside the scope; drafting is not."""
    from tests.unit.agents.abhiyojak.test_agent import abhiyojak_llm
    from vakeel_sahayak.agents.base import _SPARRING
    from vakeel_sahayak.agents.vakeel.agent import VakeelAgent

    seen: dict[str, bool] = {}
    vakeel, _, _ = build_agent(VakeelAgent, llm=abhiyojak_llm(), budgets=BudgetTracker())
    monkeypatch.setattr(VakeelAgent, "_reply_one", lambda self, o, g: seen.setdefault("reply", _SPARRING.get()) or None)
    monkeypatch.setattr(VakeelAgent, "_emit_repair_signals", lambda self: None)
    monkeypatch.setattr(VakeelAgent, "_prime", lambda self, st: setattr(self, "_state", st))
    try:
        vakeel.reply_to_objections(state, three_objections())
    except Exception:  # noqa: BLE001 - only the scope at the moment of the call matters here
        pass
    assert seen.get("reply") is True and _SPARRING.get() is False
