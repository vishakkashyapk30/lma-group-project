"""P7 `munshi_image_only`: the vision-on-every-page cost reference of the RQ2 comparison (14-page constructed bundle)."""

from __future__ import annotations

from tests.unit.agents.munshi import _variants_helpers as vh
from vakeel_sahayak.orchestration.switches import Switches


def pages_of(env, tool: str) -> list[int]:
    return [c.kwargs["page"] for c in env.toolbox.calls if c.name == tool]


def run_p7():
    env = vh.build(switches=Switches.for_variant("P7"))
    return env, vh.run(env)


def test_the_variant_id_selects_the_switch_and_is_implemented():
    assert Switches.for_variant("P7").munshi_image_only is True and Switches().munshi_image_only is False
    assert "P7" in Switches.implemented_variants()


def test_every_page_goes_to_the_vision_model_and_no_page_is_read_by_text_layer_or_ocr():
    env, _ = run_p7()
    assert sorted(set(pages_of(env, "vision_read_page"))) == list(range(1, 15))
    assert pages_of(env, "ocr_page") == [] and pages_of(env, "read_text_layer") == [] and pages_of(env, "parse_layout") == []


def test_the_default_run_sends_only_the_weak_pages_to_vision():
    env = vh.build()
    vh.run(env)
    assert sorted(set(pages_of(env, "vision_read_page"))) == [2, 3] and pages_of(env, "ocr_page")


def test_vision_calls_stay_within_one_per_page_survey_plus_gap_rereads():
    env, _ = run_p7()
    assert len(pages_of(env, "vision_read_page")) <= 14 + 3 * 7  # the survey, then at most 3 re-reads for each of the 7 checklist items


def test_the_report_routes_start_at_vision_and_signals_count_the_pages():
    env, state = run_p7()
    routes = {pr.page: pr for d in state.ingestion.documents for pr in d.page_routes}
    assert all(any(step.startswith("vision") for step in pr.route) and not any(step.startswith("ocr") for step in pr.route) for pr in routes.values())
    sig = state.variant_signals["munshi"]["image_only"]
    assert sig["pages"] == 14 and sig["vision_pages"] == 14 and sig["image_only"] is True
    events = [e for e in env.log.events if (e.outputs or {}).get("type") == "image_only"]
    assert len(events) == 1 and events[0].outputs["vision_pages"] == 14


def test_the_default_leaves_no_signal_and_no_event():
    env = vh.build()
    state = vh.run(env)
    assert state.variant_signals == {} and not [e for e in env.log.events if (e.outputs or {}).get("type") == "image_only"]


def test_p7_is_deterministic_and_combines_with_the_other_munshi_switches():
    first = vh.digests(vh.canonical_run(vh.build(switches=Switches.for_variant("P7"))))
    second = vh.digests(vh.canonical_run(vh.build(switches=Switches.for_variant("P7"))))
    assert first == second
    both = Switches(munshi_image_only=True, munshi_gap_policy="hierarchy")
    env = vh.build(switches=both)
    state = vh.run(env)
    assert set(state.variant_signals["munshi"]) == {"gaps", "image_only"}
