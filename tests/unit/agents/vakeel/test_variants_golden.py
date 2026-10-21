"""The default Vakeel + Abhiyojak run is byte-identical to the run captured BEFORE the Sweep-2 variants (S8, S9, S10, S15) were added.

`golden_default_run.json` holds one digest per part of the case-0007 offline run (brief, sparring record, hearing card, the events in
order with ids and times removed, budget). Every Sweep-2 switch defaults to the current behaviour, so none of these may move.
"""

from __future__ import annotations

import json

from tests.unit.agents.vakeel import _variants_helpers as vh
from vakeel_sahayak.orchestration.switches import Switches


def test_the_default_switches_are_the_full_system():
    s = Switches()
    assert s.variant() == "full"
    assert (s.repair_mode, s.critic_mode, s.abhiyojak_isolation, s.draft_mode, s.output_format) == ("grounded", "abhiyojak", True, "single", "answer_only")


def test_default_run_matches_the_golden_digests():
    golden = json.loads(vh.GOLDEN.read_text(encoding="utf-8"))
    assert vh.digests(vh.canonical_run(vh.build())) == golden


def test_default_run_has_no_variant_signals_and_no_variant_events():
    env = vh.build()
    out = vh.run_both(env)
    assert out.state.variant_signals == {}
    kinds = {(e.outputs or {}).get("type") for e in env.log.events}
    assert not kinds & {"self_critique", "repair_signals", "critic_signals", "isolation_off", "sampling_critic", "reasoning_first", "output_signals", "three_role", "draft_vote", "draft_debate"}
