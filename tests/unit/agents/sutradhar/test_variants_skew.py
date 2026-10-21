"""S4 score-skew weak-evidence signal: `Switches.weak_signal='skew'` (SkewRoute, Findings of EMNLP 2025; evaluation plan 3.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration import _helpers as h
from tests.unit.agents.sutradhar._variants_helpers import build, canonical_run, digest
from vakeel_sahayak.agents.sutradhar import skew
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.pipelines.citation_graph.expansion import ScoredParagraph
from vakeel_sahayak.schemas.enums import EventKind, Factor, SlotStatus
from vakeel_sahayak.schemas.retrieval_plan import SlotResult

GOLDEN = json.loads((Path(__file__).parent / "golden_default_run.json").read_text())
S4 = Switches.for_variant("S4")


class ScoreToolbox(h.ScenarioToolbox):
    """ScenarioToolbox whose `search_reasoning` understands `with_scores`; `shape` makes the score list 'flat' or 'skewed'."""

    shape = "flat"

    def t_search_reasoning(self, query, factor=None, section_family=None, before=None, outcome=None, court=None, k=10, with_scores=False):
        plain = super().t_search_reasoning(query, factor, section_family, before, outcome, court, k)
        if not with_scores:
            return plain
        n = len(plain)
        scores = [0.8] * n if self.shape == "flat" else [1.0 / (1 + 3 * i) for i in range(n)]
        return [ScoredParagraph(**r.model_dump(), score=s) for r, s in zip(plain, scores, strict=True)]


class SkewedToolbox(ScoreToolbox):
    shape = "skewed"


def decisions(env, tool):
    return [e.outputs for e in env.ctx.log.events if e.kind == EventKind.AGENT_MESSAGE and e.tool == tool]


def calls(env):
    return [c for c in env.toolbox.calls if c.name == "search_reasoning"]


# ---- the statistics on constructed lists -----------------------------------------------------------------------
def test_gini_on_known_lists():
    assert skew.gini([1, 1, 1, 1]) == 0.0 and skew.gini([0, 0, 0, 1]) == 0.75
    assert skew.gini([5, 1, 1, 1]) > skew.gini([2, 1.5, 1.2, 1]) > 0
    assert skew.gini([1]) is None and skew.gini([0, 0]) is None and skew.gini([]) is None


def test_top_gap_on_known_lists():
    assert skew.top_gap([1.0, 0.5, 0.2]) == 0.5 and skew.top_gap([0.5, 1.0]) == 0.5 and skew.top_gap([0.8, 0.8, 0.8]) == 0.0
    assert skew.top_gap([1.0]) is None and skew.top_gap([0, 0]) is None


def test_flag_needs_three_flat_scores():
    assert skew.skew_of([0.8, 0.8, 0.8, 0.8])["weak"] is True
    assert skew.skew_of([1.0, 0.4, 0.2, 0.1])["weak"] is False  # one paragraph stands out
    assert skew.skew_of([0.8, 0.8])["weak"] is False and skew.skew_of([])["weak"] is False
    assert skew.skew_of([0.9, 0.85, 0.8, 0.8], gini_flat=0.5, gap_flat=0.5)["weak"] is True and skew.skew_of([0.9, 0.85, 0.8, 0.8], gini_flat=0.0001, gap_flat=0.0001)["weak"] is False


def test_scores_are_read_from_results():
    assert skew.scores_of([{"score": 0.5}, {"text_score": 0.25}, {"text": "x"}, {"score": True}]) == [0.5, 0.25]


def test_threshold_defaults_and_config_override(monkeypatch):
    assert skew.thresholds() == (skew.GINI_FLAT, skew.GAP_FLAT) or all(v > 0 for v in skew.thresholds())
    import vakeel_sahayak.config as cfg

    class Cfg:
        thresholds = {"retrieval": {"skew_gini_flat": 0.3, "skew_gap_flat": 0.4}}

    monkeypatch.setattr(cfg, "load_config", lambda *a, **k: Cfg())
    assert skew.thresholds() == (0.3, 0.4)


# ---- switches --------------------------------------------------------------------------------------------------
def test_switch_default_and_names():
    assert Switches().weak_signal == "rules" and S4.weak_signal == "skew" and S4.variant() == "S4" and "S4" in Switches.implemented_variants()
    with pytest.raises(ValueError):
        Switches(weak_signal="skew", fixed_router=True)


# ---- default-off equivalence -----------------------------------------------------------------------------------
@pytest.mark.parametrize("world", ["case_0007", "case_0007_second_parity"])
def test_default_run_is_byte_identical_and_asks_for_no_scores(world):
    env = build(switches=Switches(weak_signal="rules"), toolbox_cls=ScoreToolbox, world=h.case_0007_world(second_parity=world.endswith("parity")))
    assert {k: digest(v) for k, v in canonical_run(env).items()} == GOLDEN[world]
    assert all("with_scores" not in c.kwargs for c in calls(env)) and env.agent.retrieval_signals == {}


# ---- behaviour -------------------------------------------------------------------------------------------------
def test_scored_searches_are_requested_and_recorded():
    env = build(switches=S4, toolbox_cls=ScoreToolbox)
    out = env.agent.run(env.state)
    assert calls(env) and all(c.kwargs.get("with_scores") for c in calls(env))
    sig = out.retrieval_signals
    assert sig and all("skew" in s for s in sig.values())
    for s in sig.values():
        t = s["skew"]
        assert t["scored_calls"] == len(t["calls"]) and t["weak_flags"] <= t["scored_calls"] and t["downgrades"] <= t["weak_flags"]
        assert all({"slot", "round", "n", "gini", "top_gap", "weak"} <= set(c) for c in t["calls"])


def test_flat_scores_downgrade_a_filled_slot_and_cue_a_relaxation():
    """Round 1 of the second-parity world fills every parity slot by the rules; a flat score list turns authority WEAK and the re-plan relaxes a filter."""
    parity = Factor.PARITY_WITH_CO_ACCUSED
    env = build(switches=S4, toolbox_cls=ScoreToolbox, world=h.case_0007_world(second_parity=True))
    env.agent.pick_factors(env.state)
    plan = env.agent.plan_factor(parity, env.state)
    results = env.agent.run_plan(plan)
    work = env.agent._work[parity]
    sw = work.slots["authority"]
    assert sw.skew_last is not None and sw.skew_last["n"] >= 1  # the scored call was recorded
    sw.skew_last = {"n": 5, "gini": 0.0, "top_gap": 0.0, "weak": True}
    assessed = env.agent.assess(parity, results)
    authority = next(r for r in assessed if r.slot == "authority")
    assert authority.status == SlotStatus.WEAK and "score skew flat" in (authority.note or "") and decisions(env, "skew_weak")
    assert work.skew["downgrades"] == 1
    nxt = env.agent.replan(plan, assessed)
    assert nxt is not None and "authority: relaxed" in (plan.next or "")


def test_flat_lists_are_flagged_across_a_whole_run():
    env = build(switches=S4, toolbox_cls=ScoreToolbox)
    out = env.agent.run(env.state)
    assert sum(s["skew"]["weak_flags"] for s in out.retrieval_signals.values()) > 0


def test_skewed_scores_leave_every_slot_status_as_the_rules_gave_it():
    plain, env = build(toolbox_cls=ScoreToolbox), build(switches=S4, toolbox_cls=SkewedToolbox)
    base = plain.agent.run(plain.state)
    out = env.agent.run(env.state)
    assert [[s.status for s in p.slots] for p in out.evidence_packs] == [[s.status for s in p.slots] for p in base.evidence_packs]
    assert sum(s["skew"]["downgrades"] for s in out.retrieval_signals.values()) == 0 and not decisions(env, "skew_weak")


def test_no_downgrade_once_the_last_relaxation_is_used():
    env = build(switches=S4, toolbox_cls=ScoreToolbox)
    env.agent.retrieve(env.state, [Factor.PARITY_WITH_CO_ACCUSED])
    work = next(iter(env.agent._work.values()))
    sw = work.slots["authority"]
    sw.skew_last = {"n": 5, "gini": 0.0, "top_gap": 0.0, "weak": True}
    filled = SlotResult(slot="authority", status=SlotStatus.FILLED, items=[])
    sw.level = 0
    assert env.agent._apply_skew(work, sw, filled).status == SlotStatus.WEAK
    sw.level = 2
    assert env.agent._apply_skew(work, sw, filled).status == SlotStatus.FILLED
    sw.level, sw.skew_last = 0, {"n": 5, "gini": 0.5, "top_gap": 0.5, "weak": False}
    assert env.agent._apply_skew(work, sw, filled).status == SlotStatus.FILLED


def test_a_weak_or_missing_slot_is_never_changed_by_the_signal():
    env = build(switches=S4, toolbox_cls=ScoreToolbox)
    env.agent.retrieve(env.state, [Factor.PARITY_WITH_CO_ACCUSED])
    work = next(iter(env.agent._work.values()))
    sw = work.slots["authority"]
    sw.skew_last, sw.level = {"n": 5, "gini": 0.0, "top_gap": 0.0, "weak": True}, 0
    for status in (SlotStatus.WEAK, SlotStatus.MISSING):
        res = SlotResult(slot="authority", status=status, items=[])
        assert env.agent._apply_skew(work, sw, res) is res


def test_run_is_deterministic():
    runs = [canonical_run(build(switches=S4, toolbox_cls=ScoreToolbox)) for _ in range(2)]
    assert digest(runs[0]["packs"]) == digest(runs[1]["packs"]) and digest(runs[0]["plans"]) == digest(runs[1]["plans"])


def test_signals_are_events_and_state_fields():
    env = build(switches=S4, toolbox_cls=ScoreToolbox)
    out = env.agent.run(env.state)
    emitted = {d["factor"]: d for d in decisions(env, "retrieval_signals")}
    assert set(emitted) == set(out.retrieval_signals) and all("skew" in d for d in emitted.values())


def test_budgets_are_respected_even_when_every_list_is_flat():
    env = build(switches=S4, toolbox_cls=ScoreToolbox, budgets=BudgetTracker(tokens_per_case=20000))
    env.agent.run(env.state)
    snap = env.budgets.snapshot()
    assert all(v <= 8 for v in snap.store_calls.values()) and snap.tokens_spent <= snap.tokens_cap + 500


def test_combines_with_the_other_retrieval_variants():
    env = build(switches=Switches(weak_signal="skew", retrieval_policy="adaptive", stopping="rules_llm"), toolbox_cls=ScoreToolbox)
    out = env.agent.run(env.state)
    assert {"skew", "depth", "stopping"} <= set(next(iter(out.retrieval_signals.values())))
