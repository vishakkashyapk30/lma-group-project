"""S7 / A11a: Munshi's gap re-reading under the sequential and the hierarchy policy on a constructed file (four weak scanned pages of one remand document;
the arrest and the remand are on the last page)."""

from __future__ import annotations

import pytest

from tests.fakes.toolbox import FakePage
from tests.unit.agents.munshi import _variants_helpers as vh
from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import DocumentType

REMAND = DocumentType.REMAND_ORDER


def scan(ocr: str, vision: str, conf: float = 0.7) -> FakePage:
    return FakePage(text="", signals=PageSignals(has_text_layer=False, text_coverage=0.0), ocr_text=ocr, ocr_conf=conf, vision_text=vision, doc_type=REMAND)


def weak_file() -> list[FakePage]:
    cover = scan("Copy of the order supplied to the accused and to the counsel for the record.", "Copy of the order supplied to the accused.")
    last = scan("Arrest and remand order of the Court is attached for the accused and the counsel.",
                "The accused was arrested on 20.08.2024 and remanded to judicial custody on 21.08.2024.")
    return [cover, cover, cover, last]


BOUNDARIES = [(1, 4, REMAND, "en")]


def run(policy: str):
    env = vh.build(switches=Switches(munshi_gap_policy=policy), pages=weak_file(), boundaries=BOUNDARIES)
    state = vh.run(env)
    return env, state


def test_the_policy_selects_through_the_variant_id():
    assert Switches.for_variant("S7").munshi_gap_policy == "hierarchy" == Switches.for_variant("A11a").munshi_gap_policy
    assert Switches().munshi_gap_policy == "sequential" and "S7" in Switches.implemented_variants()


def test_hierarchy_cannot_combine_with_no_gap_check():
    with pytest.raises(ValueError):
        Switches(munshi_gap_policy="hierarchy", munshi_no_gap_check=True)


def test_sequential_reads_the_cover_pages_first_and_hierarchy_goes_to_the_page_that_shows_the_item():
    seq_env, _ = run("sequential")
    hier_env, _ = run("hierarchy")
    seq, hier = seq_env.munshi.gap_signals(), hier_env.munshi.gap_signals()
    by_item = lambda s, item: next(r for r in s["records"] if r["item"] == item)  # noqa: E731
    assert [c["page"] for c in by_item(seq, "arrest_date")["candidates"]] == [1, 2, 3] and by_item(seq, "arrest_date")["resolved_by"] is None
    assert by_item(hier, "arrest_date")["read"] == [{"file": "bundle_1.pdf", "page": 4}] and by_item(hier, "arrest_date")["resolved_by"] == "reread"
    assert hier["pages_reread"] < seq["pages_reread"]
    assert hier["gaps_resolved"] >= seq["gaps_resolved"]


def test_hierarchy_stops_when_an_earlier_reread_filed_the_field():
    env, state = run("hierarchy")
    rec = next(r for r in env.munshi.gap_signals()["records"] if r["item"] == "first_remand")
    assert rec["resolved_by"] == "earlier_reread" and rec["reads"] == 0
    assert any(g.item == "first remand" and "earlier re-read" in g.action for g in state.ingestion.gaps)


def test_signals_reach_the_event_log_the_state_and_the_agent_in_the_hierarchy_arm_only():
    env, state = run("hierarchy")
    events = [e for e in env.log.events if (e.outputs or {}).get("type") == "gap_policy"]
    sig = state.variant_signals["munshi"]["gaps"]
    assert len(events) == 1 and events[0].outputs["pages_reread"] == sig["pages_reread"] and "records" not in events[0].outputs
    assert sig["resolved_per_page_read"] == sig["gaps_resolved_by_reread"] / sig["pages_reread"] and sig["oracle_regret"] >= 0
    seq_env, seq_state = run("sequential")
    assert seq_state.variant_signals == {} and not [e for e in seq_env.log.events if (e.outputs or {}).get("type") == "gap_policy"]
    assert seq_env.munshi.gap_signals()["policy"] == "sequential"  # the default policy still measures itself, in memory


def test_the_reread_cap_is_respected_in_both_policies():
    pages = [scan("Copy of the order supplied to the accused and to the counsel for the record.", "Copy supplied.") for _ in range(6)]
    for policy in ("sequential", "hierarchy"):
        env = vh.build(switches=Switches(munshi_gap_policy=policy), pages=pages, boundaries=[(1, 6, REMAND, "en")])
        vh.run(env)
        assert all(r["reads"] <= 3 for r in env.munshi.gap_signals()["records"])


def test_a_hierarchy_run_is_deterministic():
    first = vh.digests(vh.canonical_run(vh.build(switches=Switches(munshi_gap_policy="hierarchy"), pages=weak_file(), boundaries=BOUNDARIES)))
    second = vh.digests(vh.canonical_run(vh.build(switches=Switches(munshi_gap_policy="hierarchy"), pages=weak_file(), boundaries=BOUNDARIES)))
    assert first == second
