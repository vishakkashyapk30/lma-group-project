"""PlanCache (S14 / A14): templates under a signature, adaptation of case-bound arguments, invalidation, separate counters, persistence."""

from __future__ import annotations

from types import SimpleNamespace

from vakeel_sahayak.batch.cache import PlanCache, RetrievalCache, plans_of
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.retrieval_plan import PlanStep


def work(factor="parity_with_co_accused", family=("BNS 318(4)", "IPC 420"), before="2025-02-03", stance="FAVOURABLE", sources=("caselaw.reasoning",)):
    slots = {"authority": SimpleNamespace(need="at least 1", sources=list(sources))}
    return SimpleNamespace(factor=factor, stance=stance, pctx=SimpleNamespace(family=list(family), before=before), slots=slots)


STEPS = [
    {"slot": "authority", "tool": "search_reasoning", "args": {"query": "parity co-accused granted bail", "before": "2025-02-03", "case_id": "case-0001", "factor": "parity_with_co_accused"}},
    {"slot": "custody", "tool": "date_calc", "args": {"start": "2024-08-20", "end": "2025-02-03", "rule": "CALENDAR_DAYS_BETWEEN"}},
]


def test_signature_depends_on_factor_family_month_stance_layout_flags_and_version():
    plans = PlanCache(RetrievalCache())
    s = Switches()
    base = plans.signature(work(), s)
    assert base == plans.signature(work(before="2025-02-27"), s)  # the same month
    assert base == plans.signature(work(family=("IPC 420", "BNS 318(4)")), s)  # family order does not matter
    for other in (work(factor="custody_period"), work(family=("BNS 103",)), work(before="2025-03-01"), work(stance="ADVERSE"), work(sources=("caselaw.similar",))):
        assert plans.signature(other, s) != base
    assert plans.signature(work(), Switches(plain_retrieval=True)) != base and plans.signature(work(), Switches(no_dossier=True)) != base
    assert PlanCache(RetrievalCache(), store_version="v2").signature(work(), s) != base


def test_a_miss_then_a_hit_with_the_tokens_saved():
    plans = PlanCache(RetrievalCache())
    key = plans.signature(work(), Switches())
    assert plans.lookup(key) is None
    plans.store(key, STEPS, tokens=1200)
    hit = plans.lookup(key)
    assert hit is not None and hit["tokens_saved"] == 1200 and len(hit["steps"]) == 2
    stats = plans.stats()
    assert (stats["hits"], stats["misses"], stats["lookups"], stats["hit_rate"], stats["tokens_saved"], stats["tokens_spent"], stats["templates"]) == (1, 1, 2, 0.5, 1200, 1200, 1)


def test_the_template_drops_the_case_id_and_the_date_and_keeps_the_query():
    plans = PlanCache(RetrievalCache())
    key = plans.signature(work(), Switches())
    plans.store(key, STEPS, 10)
    first = plans.lookup(key)["steps"][0]["args"]
    assert "case_id" not in first and "before" not in first and first["query"] == "parity co-accused granted bail" and first["factor"] == "parity_with_co_accused"


def test_case_bound_arguments_come_from_the_new_case_and_the_query_from_the_template():
    plans = PlanCache(RetrievalCache())
    key = plans.signature(work(), Switches())
    plans.store(key, STEPS, 10)
    fresh = {
        ("authority", "search_reasoning"): PlanStep(slot="authority", tool="search_reasoning", args={"query": "a different wording", "section_family": ["BNS 103"], "k": 10}),
        ("custody", "date_calc"): PlanStep(slot="custody", tool="date_calc", args={"start": "2024-11-01", "end": "2025-02-03", "rule": "CALENDAR_DAYS_BETWEEN"}),
    }
    steps = plans.lookup(key, fresh)["steps"]
    assert steps[0]["args"]["query"] == "parity co-accused granted bail" and steps[0]["args"]["section_family"] == ["BNS 103"] and steps[0]["args"]["k"] == 10
    assert steps[1]["args"]["start"] == "2024-11-01"


def test_a_new_store_version_makes_every_template_a_miss():
    cache = RetrievalCache()
    plans = plans_of(cache)
    key = plans.signature(work(), Switches())
    plans.store(key, STEPS, 10)
    plans_of(cache, store_version="rebuilt")
    assert plans.lookup(plans.signature(work(), Switches())) is None


def test_plan_lookups_do_not_touch_the_retrieval_hit_rate():
    cache = RetrievalCache()
    plans = plans_of(cache)
    key = plans.signature(work(), Switches())
    plans.lookup(key)
    plans.store(key, STEPS, 10)
    plans.lookup(key)
    assert cache.stats()["lookups"] == 0 and cache.stats()["hit_rate"] == 0.0


def test_plans_of_gives_one_plan_cache_per_retrieval_cache():
    a, b = RetrievalCache(), RetrievalCache()
    assert plans_of(a) is plans_of(a) and plans_of(a) is not plans_of(b)


def test_templates_survive_in_a_persistent_cache(tmp_path):
    path = str(tmp_path / "cache.sqlite")
    first = RetrievalCache(path)
    key = plans_of(first).signature(work(), Switches())
    plans_of(first).store(key, STEPS, 500)
    first.close()
    second = RetrievalCache(path)
    hit = plans_of(second).lookup(key)
    assert hit is not None and hit["tokens_saved"] == 500
    second.close()


def test_peek_does_not_count_and_a_missing_key_is_none():
    cache = RetrievalCache()
    assert cache.peek("nothing") is None
    cache.put("k", {"a": 1})
    assert cache.peek("k") == {"a": 1} and cache.stats()["lookups"] == 0
