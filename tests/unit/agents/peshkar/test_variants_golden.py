"""The default Peshkar run is byte-identical to the run captured BEFORE the Sweep-3 injection-defence arms (S17) were added.

RECONCILED 2026-10-26: the golden was re-captured after fixes to the offline reader: the FIR date is read only when it sits right after the FIR
number (it used to take the arrest date out of the same window), and a Hindi FIR number split across a sentence break is read; an empty reply from counsel leaves the question open; the dossier and the
events differ, the prompts the model saw do not. Variants must still leave this run unchanged.

RECONCILED 2026-10-27: the `events` digest only was re-captured after the HA-03 Rights Radar fixes (docs/handoff/rights-fixes.md): the rights_check tool result carries each rule's text and detail,
which changed for default_bail, undertrial_limit, antil_category and statutory_bar; every status for case-0007 is the same, and the dossier, List of Dates and prompt digests did not move.

`golden_default_run.json` holds one digest per part of the offline run over the three-chunk shelf with a planted instruction (dossier, List of Dates, the
events in order with ids and times removed, every prompt the model saw). All three defence flags default to False (defences ON), which is the current behaviour.
"""

from __future__ import annotations

import json

from tests.unit.agents.peshkar import _variants_helpers as vh
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.privacy.defences import Defences, channels


def test_the_default_switches_leave_every_defence_on():
    s = Switches()
    assert s.variant() == "full"
    assert (s.no_typed_handoff, s.no_spotlighting, s.no_guard) == (False, False, False)
    assert Defences.from_switches(s).all_on


def test_default_run_matches_the_golden_digests():
    golden = json.loads(vh.GOLDEN.read_text(encoding="utf-8"))
    assert vh.digests(vh.canonical_run(vh.build())) == golden


def test_default_run_has_no_variant_signals_and_no_defence_events():
    env = vh.build()
    run = vh.canonical_run(env)
    assert run["variant_signals"] == {}
    kinds = {(e.outputs or {}).get("type") for e in env.log.events}
    assert not kinds & {"typed_handoff", "typed_handoff_off"}


def test_default_prompts_keep_the_planted_text_inside_the_delimiter_block_only():
    env = vh.build()
    vh.canonical_run(env)
    got = channels(env.llm.seen, vh.PLANTED)
    assert got["fenced"] > 0 and got["unfenced"] == 0 and got["instructions"] == 0
