"""Sparring reserve, second correction (15 Nov): each reply is judged right after it is drafted; objections the pool cannot cover are NOT_REPLIED_BUDGET.

Offline: a scripted judge and a fake replier that charges the reserve like a Vakeel call. Default (reserve 0) keeps the old order.
"""

from __future__ import annotations

from tests.unit.agents._helpers import build_agent
from tests.unit.agents.abhiyojak.test_agent import TABLE, objection_with_reply, state, verdict_llm  # noqa: F401  (state is a fixture)
from vakeel_sahayak.agents.abhiyojak import agent as abh
from vakeel_sahayak.agents.abhiyojak.agent import NOT_REPLIED_REASON, AbhiyojakAgent
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import ClaimCheck, SparringVerdict
from vakeel_sahayak.schemas.sparring import Reply

F = "parity_with_co_accused"
PLAIN = "no reply was drafted because the sparring budget was spent; counsel answers this one."


def _objections():
    return [objection_with_reply(f"O{i}", t, reply=False) for i, t in ((1, "The money went into his own account"), (2, "The accused role is disputed"), (3, "The complainant is yet to be examined"))]


def _replier(t: BudgetTracker, cost: int, seen: list[str]):
    def reply(state, objs):  # noqa: F811
        (o,) = objs
        seen.append(o.id)
        t.charge(F, cost, actor="VAKEEL", pool="sparring")
        return [Reply(text=f"Reply to {o.id}", check=ClaimCheck.SUPPORTED)]

    return reply


def _run(state, reserve, cost, monkeypatch, n=3):  # noqa: F811
    monkeypatch.setattr(abh, "JUDGE_HOLDBACK_TOKENS", 1000)
    t = BudgetTracker()
    agent, ctx, _ = build_agent(AbhiyojakAgent, llm=verdict_llm(TABLE), budgets=t, switches=Switches(sparring_reserve_tokens=reserve))
    seen: list[str] = []
    out = agent.reply_and_judge(state, _objections()[:n], _replier(t, cost, seen))
    return out, t, ctx, seen


def test_every_replied_objection_is_judged_and_the_rest_are_not_replied_budget(state, monkeypatch):  # noqa: F811
    out, t, ctx, seen = _run(state, 6000, 2500, monkeypatch)  # an objection costs about 2850: two fit, the third does not
    assert seen == ["O1", "O2"]
    assert [o.verdict for o in out] == [SparringVerdict.ANSWERED, SparringVerdict.PARTLY, SparringVerdict.UNANSWERED]
    assert out[0].reply is not None and out[1].reply is not None and out[2].reply is None
    assert out[2].reason == NOT_REPLIED_REASON == "NOT_REPLIED_BUDGET: " + PLAIN
    assert "could not be judged" not in " ".join(o.reason or "" for o in out)  # no judge call was refused
    assert t.sparring_spent() <= 6000


def _trace(state, monkeypatch):  # noqa: F811
    out, t, ctx, _ = _run(state, 6000, 2500, monkeypatch)
    keep = {"verdict", "not_replied_budget", "round_2", "round_2_done", "replies"}
    return [(e.tool or "", (e.outputs or {}).get("objection")) for e in ctx.log.events if (e.tool or "") in keep]


def test_event_order_is_deterministic_and_judge_follows_each_reply(state, monkeypatch):  # noqa: F811
    first = _trace(state, monkeypatch)
    assert first == _trace(state, monkeypatch)
    names = [n for n, _ in first]
    assert names == ["round_2", "verdict", "verdict", "not_replied_budget", "verdict", "replies", "round_2_done"]
    assert [o for n, o in first if n == "verdict"] == ["O1", "O2", "O3"]


def test_judge_is_never_starved_by_a_repair_that_spends_the_pool(state, monkeypatch):  # noqa: F811
    monkeypatch.setattr(abh, "JUDGE_HOLDBACK_TOKENS", 1000)
    t = BudgetTracker()
    agent, _, _ = build_agent(AbhiyojakAgent, llm=verdict_llm(TABLE), budgets=t, switches=Switches(sparring_reserve_tokens=4000))
    checks: list[bool] = []

    def greedy(st, objs):
        checks.append(t.tokens_exhausted(F, "VAKEEL", pool="sparring"))  # 0 spent: not refused
        t.charge(F, 3100, actor="VAKEEL", pool="sparring")
        checks.append(t.tokens_exhausted(F, "VAKEEL", pool="sparring"))  # repair now: 3100 + 1000 held back >= 4000, refused
        return [Reply(text="r", check=ClaimCheck.SUPPORTED)]

    out = agent.reply_and_judge(state, _objections()[:1], greedy)
    assert checks == [False, True]
    assert out[0].verdict == SparringVerdict.ANSWERED and "could not be judged" not in (out[0].reason or "")
    assert t.spar_holdback_tokens == 0  # released after the reply


def test_budget_meter_stays_one_total(state, monkeypatch):  # noqa: F811
    out, t, ctx, _ = _run(state, 6000, 2500, monkeypatch)
    snap = t.snapshot()
    assert snap.tokens_cap == 150000 + 6000 and snap.tokens_spent == t.sparring_spent()
    last = [e for e in ctx.log.events if e.outputs and e.outputs.get("reserve") == 6000][-1].outputs
    assert last["spent"] == t.sparring_spent() and last["left"] == 6000 - t.sparring_spent()


def test_events_replay_to_the_same_judge_spend_and_verdicts(state, monkeypatch):  # noqa: F811
    out, t, ctx, _ = _run(state, 6000, 2500, monkeypatch)
    back = BudgetTracker.from_events(ctx.log.events)
    judge_spend = sum(e.outputs["budget_charge"]["tokens"] for e in ctx.log.events if (e.outputs or {}).get("budget_charge"))
    assert back.sparring_spent() == judge_spend and judge_spend > 0
    verdicts = {e.outputs["objection"]: (e.outputs["verdict"], e.outputs["reason"]) for e in ctx.log.events if e.tool == "verdict"}
    assert verdicts == {o.id: (o.verdict.value, o.reason) for o in out}


def test_reserve_zero_keeps_the_old_order_and_events(state):  # noqa: F811
    agent, ctx, _ = build_agent(AbhiyojakAgent, llm=verdict_llm(TABLE), budgets=BudgetTracker())
    paired = [o.model_copy(update={"reply": Reply(text=f"Reply to {o.id}", check=ClaimCheck.SUPPORTED)}) for o in _objections()]
    out = agent.judge_replies(state, paired)
    tools = [e.tool for e in ctx.log.events if e.tool]
    assert "not_replied_budget" not in tools and "sparring_reserve" not in tools
    assert tools.index("round_2") < tools.index("verdict") < tools.index("round_2_done")
    assert all(o.reason and not o.reason.startswith("NOT_REPLIED_BUDGET") for o in out)
    assert BudgetTracker().spar_holdback_tokens == 0 and "sparring" not in BudgetTracker().to_dict()
