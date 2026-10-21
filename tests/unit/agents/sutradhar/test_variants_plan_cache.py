"""S14 / A14 plan cache in Sutradhar (`Switches.plan_cache`): a RetrievalPlan template is reused across cases with the same signature (offline model, case-0007)."""

from __future__ import annotations

import json
from pathlib import Path

from tests.integration import _helpers as h
from tests.unit.agents.sutradhar._variants_helpers import build, canonical_run, digest
from vakeel_sahayak.batch.cache import RetrievalCache, plans_of
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import EventKind

GOLDEN = json.loads((Path(__file__).parent / "golden_default_run.json").read_text())
ON = Switches(plan_cache=True)


def planning_calls(env) -> int:
    return sum(1 for e in env.ctx.log.events if e.kind == EventKind.AGENT_MESSAGE and (e.inputs or {}).get("task") == "sutradhar.plan_factor")


def plan_events(env) -> list[dict]:
    return [e.outputs for e in env.ctx.log.events if (e.outputs or {}).get("type") == "plan_cache"]


def run_with(cache, switches=ON, **kw):
    env = build(switches=switches, **kw)
    env.ctx.cache = cache
    return env, canonical_run(env)


def test_switch_and_variant_ids():
    assert Switches.for_variant("S14").plan_cache is True and Switches.for_variant("A14") == Switches.for_variant("S14")
    assert Switches().plan_cache is False and "S14" in Switches.implemented_variants()


def test_default_run_matches_the_golden_digests_and_never_touches_the_cache():
    cache = RetrievalCache()
    env = build()
    env.ctx.cache = cache
    run = canonical_run(env)
    assert {k: digest(run[k]) for k in ("packs", "plans")} == {k: GOLDEN["case_0007"][k] for k in ("packs", "plans")}  # (events differ with a shared cache attached: cached results)
    plain = canonical_run(build())
    assert {k: digest(v) for k, v in plain.items()} == GOLDEN["case_0007"]
    assert not [k for k in cache._data if str(k).startswith("plan|")] and plan_events(env) == []


def test_the_second_case_with_the_same_signature_reuses_the_plans():
    cache = RetrievalCache()
    first_env, first = run_with(cache)
    second_env, second = run_with(cache)
    stats = plans_of(cache).stats()
    assert stats["hits"] == stats["misses"] > 0 and stats["hit_rate"] == 0.5 and stats["tokens_saved"] > 0
    assert planning_calls(second_env) == 0 < planning_calls(first_env)
    assert all(e["hit"] for e in plan_events(second_env)) and not any(e["hit"] for e in plan_events(first_env))


def test_the_evidence_is_the_same_with_and_without_the_cache():
    cache = RetrievalCache()
    _, first = run_with(cache)
    _, second = run_with(cache)
    plain = canonical_run(build())
    assert digest(first["packs"]) == digest(second["packs"]) == digest(plain["packs"])


def test_the_cache_saves_tokens_and_the_signal_counts_them():
    cache = RetrievalCache()
    first_env, _ = run_with(cache)
    second_env, _ = run_with(cache)
    spent = lambda env: env.budgets.spent(None)[0]  # noqa: E731
    assert spent(second_env) < spent(first_env)
    saved = plans_of(cache).stats()["tokens_saved"]
    assert saved > 0 and abs((spent(first_env) - spent(second_env)) - saved) <= 0.2 * saved  # the saving is what the planning calls cost


def test_a_different_month_or_section_family_or_store_version_is_a_miss():
    cache = RetrievalCache()
    run_with(cache)
    before = plans_of(cache).stats()["hits"]
    plans_of(cache, store_version="v2")  # a store was rebuilt: every template is stale
    run_with(cache)
    assert plans_of(cache).stats()["hits"] == before
    plans_of(cache, store_version="")
    world = h.case_0007_world()
    env = build(switches=ON, world=world)
    env.ctx.cache = cache
    env.state = env.state.model_copy(update={"before": "2023-01-15"})
    canonical_run(env)
    assert plans_of(cache).stats()["hits"] >= before  # the same factors hit again only where the signature (including the month) is the same


def test_without_a_shared_cache_the_switch_changes_nothing():
    on = build(switches=ON)
    assert on.ctx.cache is None
    assert digest(canonical_run(on)["packs"]) == digest(canonical_run(build())["packs"]) and plan_events(on) == []


def test_case_bound_arguments_are_refilled_and_before_is_the_new_cases():
    cache = RetrievalCache()
    run_with(cache)
    second_env, _ = run_with(cache)
    plans = [p for p in second_env.agent._plans_log]
    assert plans
    for plan in plans:
        for step in plan.steps:
            if "case_id" in step.args:
                assert step.args["case_id"] == second_env.agent.case_id
            if "before" in step.args:
                assert str(step.args["before"]) <= str(second_env.agent._pctx.before)


def test_plan_cache_run_is_deterministic():
    def once():
        cache = RetrievalCache()
        run_with(cache)
        _, second = run_with(cache)
        return digest(second["packs"]), plans_of(cache).stats()

    assert once() == once()


def test_budget_is_respected_with_the_cache_on():
    cache = RetrievalCache()
    run_with(cache)
    env, _ = run_with(cache, budgets=BudgetTracker())
    assert env.budgets.spent(None)[0] <= env.budgets.tokens_per_case
