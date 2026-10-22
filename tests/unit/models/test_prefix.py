"""S14d prefix-friendly prompts: the layout, the shared-prefix meter and the agent hook (`Switches.prefix_layout`)."""

from __future__ import annotations

import json

from tests.unit.agents.peshkar._variants_helpers import RecordingLLM
from tests.unit.agents._helpers import build_agent
from vakeel_sahayak.agents.peshkar.agent import PeshkarAgent
from vakeel_sahayak.models.prefix import PrefixMeter, prefix_ordered, sorted_keys
from vakeel_sahayak.models.prompting import INPUT_HEADER, parse_prompt, render_prompt
from vakeel_sahayak.orchestration.switches import Switches

CORPUS = {"paragraphs": [{"doc_id": "SC-2014-0463", "text": "x" * 800}]}


def test_default_layout_is_unchanged_and_the_variant_only_reorders_the_input():
    data = {"case": {"b": 1, "a": 2}, "corpus": CORPUS, "extra": {"z": 1}}
    default = render_prompt("t.task", "Do it.", data, system="sys")
    friendly = render_prompt("t.task", "Do it.", data, system="sys", prefix_friendly=True)
    assert default == render_prompt("t.task", "Do it.", data, system="sys", prefix_friendly=False)
    assert default.index('"case"') < default.index('"corpus"') and friendly.index('"corpus"') < friendly.index('"extra"') < friendly.index('"case"')
    assert default.split(INPUT_HEADER)[0] == friendly.split(INPUT_HEADER)[0]  # system, task, instructions and schema come first in both
    assert parse_prompt(friendly).data == parse_prompt(default).data == data


def test_keys_are_sorted_at_every_level_and_lists_keep_their_order():
    assert json.dumps(sorted_keys({"b": [{"y": 1, "x": 2}, 3], "a": {"d": 1, "c": 2}})) == '{"a": {"c": 2, "d": 1}, "b": [{"x": 2, "y": 1}, 3]}'
    assert list(prefix_ordered({"case": 1, "zeta": 2, "corpus": 3, "alpha": 4})) == ["corpus", "alpha", "zeta", "case"]
    assert list(prefix_ordered({"case": 1})) == ["case"]


def test_the_friendly_layout_is_stable_across_key_order():
    a = render_prompt("t.task", "Do it.", {"case": {"p": 1, "q": 2}, "corpus": CORPUS}, prefix_friendly=True)
    b = render_prompt("t.task", "Do it.", {"corpus": CORPUS, "case": {"q": 2, "p": 1}}, prefix_friendly=True)
    assert a == b


def test_meter_counts_the_shared_prefix_with_the_best_earlier_prompt_of_the_task():
    meter = PrefixMeter()
    shared_text = "the court considered the period of custody " * 20
    assert meter.observe("t", shared_text + "one") == 0
    shared = meter.observe("t", shared_text + "two")
    assert shared >= 100  # 20 repeats of a seven-word sentence
    assert meter.observe("other", shared_text + "three") == 0  # another task has its own history
    stats = meter.stats()
    assert stats["calls"] == 3 and stats["shared_prefix_tokens"] == shared and 0 < stats["shared_share"] < 1
    assert PrefixMeter().stats()["shared_share"] == 0.0


def test_meter_keeps_a_bounded_history():
    meter = PrefixMeter()
    for i in range(30):
        meter.observe("t", f"{i:03d}" + "x" * 50)
    assert len(meter._recent["t"]) == 8


def ask_twice(layout: bool):
    agent, ctx, _ = build_agent(PeshkarAgent, llm=RecordingLLM(), switches=Switches(prefix_layout=layout))
    for case_text in ("first case text", "second case text, different"):
        try:
            agent.ask("peshkar.demo", "Read the data.", case={"text": case_text}, corpus=CORPUS)
        except Exception:  # noqa: BLE001 - the stand-in has no handler for this task; the prompt and the meter are what is checked
            pass
    return agent, ctx


def test_the_friendly_layout_shares_more_prefix_across_cases_than_the_default():
    default_agent, _ = ask_twice(False)
    friendly_agent, _ = ask_twice(True)
    d, f = default_agent.prefix_signals(), friendly_agent.prefix_signals()
    assert f["shared_prefix_tokens"] > d["shared_prefix_tokens"] and f["calls"] == d["calls"] == 2


def test_the_event_and_the_signal_appear_only_under_the_variant():
    _, default_ctx = ask_twice(False)
    _, friendly_ctx = ask_twice(True)
    kinds = lambda ctx: [e.outputs for e in ctx.log.events if (e.outputs or {}).get("type") == "prefix_signals"]  # noqa: E731
    assert kinds(default_ctx) == [] and len(kinds(friendly_ctx)) == 2 and kinds(friendly_ctx)[1]["shared_prefix_tokens"] > 0


def test_agents_of_one_batch_share_the_meter_through_the_retrieval_cache():
    from vakeel_sahayak.batch.cache import RetrievalCache

    a, ctx_a, _ = build_agent(PeshkarAgent, llm=RecordingLLM())
    b, ctx_b, _ = build_agent(PeshkarAgent, llm=RecordingLLM())
    ctx_a.cache = ctx_b.cache = RetrievalCache()
    assert a._prefix_meter() is b._prefix_meter()
