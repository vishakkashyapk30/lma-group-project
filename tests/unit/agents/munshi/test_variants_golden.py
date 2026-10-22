"""The default Munshi run is byte-identical to the run captured BEFORE the Sweep-3 Munshi variants (S17 guard and spotlighting, S7, P7) were added.

`golden_default_run.json`: digests of the ingestion report, the events in order (ids and times removed) and the tool calls in order, over the 14-page bundle.
"""

from __future__ import annotations

import json

from tests.unit.agents.munshi import _variants_helpers as vh
from vakeel_sahayak.orchestration.switches import Switches


def test_the_default_switches_are_the_full_system():
    s = Switches()
    assert s.variant() == "full"
    assert (s.munshi_gap_policy, s.munshi_image_only, s.no_guard, s.no_spotlighting) == ("sequential", False, False, False)


def test_default_run_matches_the_golden_digests():
    golden = json.loads(vh.GOLDEN.read_text(encoding="utf-8"))
    assert vh.digests(vh.canonical_run(vh.build())) == golden


def test_default_run_has_no_variant_signals():
    run = vh.canonical_run(vh.build())
    assert run["variant_signals"] == {}
    assert not [e for e in run["events"] if (e["outputs"] or {}).get("type") in {"gap_policy", "image_only"}]
