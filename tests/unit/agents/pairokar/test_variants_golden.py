"""The default Pairokar batch run is byte-identical to the run captured BEFORE the Sweep-3 serving variants (S14, S14b, S14c, S14d) were added.

`golden_default_run.json`: digests of the cards in order (rank and next step), the cases run under a GPU budget, and the events, for six constructed files
on stub runners.
"""

from __future__ import annotations

import json

from tests.unit.agents.pairokar import _variants_helpers as vh
from vakeel_sahayak.orchestration.switches import Switches


def test_the_default_switches_are_the_full_system():
    s = Switches()
    assert s.variant() == "full" and (s.plan_cache, s.urgency_policy, s.prefix_layout) == (False, "urgency", False)


def test_default_run_matches_the_golden_digests():
    assert vh.digests(vh.canonical_run(vh.build())) == json.loads(vh.GOLDEN.read_text(encoding="utf-8"))


def test_default_run_adds_no_batch_signals_to_the_stage_2_message():
    env = vh.build()
    vh.canonical_run(env)
    assert not [e for e in env.log.events if "batch_signals" in (e.outputs or {})]
