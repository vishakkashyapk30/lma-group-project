"""orchestration/switches.Switches: ablation and variant flags (plan §15.4 A1-A10, §15.5 P5-P6, §19).

Defaults are the full system. Each ablation is a flag, not a code fork (skeleton conventions 'Agents').
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vakeel_sahayak.orchestration.switches import (
    ARCHITECTURE,
    INGESTION,
    VARIANT_ALIASES,
    Switches,
    assert_variant_implemented,
)
from vakeel_sahayak.schemas.enums import StoreName

# field -> plan id
FLAGS = {
    "no_dossier": "A1",
    "no_check_repair": "A2",
    "no_tools": "A3",
    "plain_retrieval": "A4",
    "fixed_router": "A6",
    "free_planner": "A7",
    "no_sparring": "A8",
    "munshi_no_gap_check": "P5",
    "munshi_no_bundle_split": "P6",
}
# EV-01 fields (evaluation plan 3.4) and their defaults: the current behaviour
EV01_DEFAULTS = {
    "retrieval_policy": "contract", "weak_signal": "rules", "graph_expansion": False, "store_prior": "off",
    "munshi_gap_policy": "sequential", "repair_mode": "grounded", "critic_mode": "abhiyojak", "abhiyojak_isolation": True,
    "draft_mode": "single", "topology": "orchestrated", "plan_cache": False, "urgency_policy": "urgency",
    "output_format": "answer_only", "no_typed_handoff": False, "no_spotlighting": False, "no_guard": False,
    "munshi_image_only": False, "chunking": "structure",
    "prefix_layout": False,  # RECONCILED: sweep 3 added S14d (prefix-friendly prompt layout), a field the plan does not name
}
EXTRACTORS = ["finetuned_4b", "base_4b", "prompted_32b"]


def test_field_set_matches_the_ablation_table():
    """Exactly the nine boolean flags plus knockout_store (A10) and extractor (A5): A9 is no_sparring + no_check_repair."""
    # RECONCILED: sweep 1 added the literature-derived architecture switches (evaluation plan 3.3); `stopping` is S3 (A11b)
    # RECONCILED: EV-01 adds fields per evaluation-plan §3.4
    assert set(Switches.model_fields) == set(FLAGS) | {"knockout_store", "extractor", "stopping"} | set(EV01_DEFAULTS)


def test_defaults_are_the_full_system():
    """With no arguments every flag is off, no store is knocked out and the fine-tuned 4B extractor is used."""
    s = Switches()
    assert all(getattr(s, f) is False for f in FLAGS)
    assert s.knockout_store is None
    assert s.extractor == "finetuned_4b"


@pytest.mark.parametrize("flag,ablation", sorted(FLAGS.items()))
def test_each_flag_toggles_alone(flag, ablation):
    """Turning on one flag changes only that flag relative to the full system."""
    s = Switches(**{flag: True})
    assert getattr(s, flag) is True, ablation
    assert [f for f in FLAGS if getattr(s, f)] == [flag]
    assert s.extractor == "finetuned_4b" and s.knockout_store is None


def test_a9_neither_sparring_nor_check_repair_is_a_combination():
    """A9 (2x2 completion) is expressed as no_sparring and no_check_repair together, not a separate flag."""
    s = Switches(no_sparring=True, no_check_repair=True)
    assert s.no_sparring and s.no_check_repair
    assert not s.no_dossier


@pytest.mark.parametrize("extractor", EXTRACTORS)
def test_extractor_variants_accepted(extractor):
    """A5: finetuned_4b, base_4b and prompted_32b are valid extractors."""
    assert Switches(extractor=extractor).extractor == extractor


@pytest.mark.parametrize("bad", ["", "finetuned_32b", "BASE_4B", "qwen3-4b"])
def test_unknown_extractor_is_rejected(bad):
    """A typo in the extractor must not silently run the full system."""
    with pytest.raises(ValidationError):
        Switches(extractor=bad)


@pytest.mark.parametrize("store", [s.value for s in StoreName])
def test_knockout_store_takes_any_store_name(store):
    """A10: knockout_store holds one of the ten dotted store names."""
    assert Switches(knockout_store=store).knockout_store == store


def test_unknown_flag_does_not_leak_into_the_model():
    """A misspelled flag is not stored as a switch (it is ignored or rejected, never active)."""
    try:
        s = Switches(no_dosier=True)  # typo for no_dossier
    except ValidationError:
        return
    assert s.no_dossier is False
    assert not hasattr(s, "no_dosier")


def test_roundtrip_through_dict():
    """Switches serialise to and from a dict (eval runs store them with the results)."""
    s = Switches(no_tools=True, extractor="base_4b", knockout_store="law.concordance")
    assert Switches(**s.model_dump()) == s


# ------------------------------------------------------------------ EV-01: evaluation plan 3.4 fields and the variant table

# S-ids and plan aliases the plan names, to the canonical id
ALIASES = {"A11a": "S7", "A11b": "S3", "A12": "S6", "A13": "S15", "A14": "S14", "A15": "S17", "A16": "S5", "A2b": "S8", "A8b": "S9",
           "A8c": "S10", "A8d": "S11", "S6b": "B5"}
EV01_VARIANTS = sorted({*ARCHITECTURE, "B5", "P7", "P5", "P6"} - {"S13"})


def test_ev01_defaults_leave_the_full_system_unchanged():
    """Every new field defaults to the current behaviour: variant() is 'full' and nothing is dumped as non-default."""
    s = Switches()
    assert {f: getattr(s, f) for f in EV01_DEFAULTS} == EV01_DEFAULTS
    assert s.variant() == "full" and s.model_dump(exclude_defaults=True) == {}


@pytest.mark.parametrize("name", EV01_VARIANTS + ["full"] + [f"A{i}" for i in (1, 2, 3, 4, 6, 7, 8, 9)])
def test_every_named_variant_round_trips(name):
    """for_variant(x).variant() == x for every canonical id."""
    assert Switches.for_variant(name).variant() == name


@pytest.mark.parametrize("alias,canonical", sorted(ALIASES.items()))
def test_plan_aliases_name_the_canonical_variant(alias, canonical):
    """A11a, A11b, A12-A16, A2b, A8b-d and S6b build the same switches as their S-id / B5, in any letter case."""
    assert Switches.for_variant(alias) == Switches.for_variant(canonical) == Switches.for_variant(alias.lower())
    assert Switches.for_variant(alias).variant() == canonical


def test_s13_needs_a_grid_point_and_a_grid_point_is_custom():
    """S13 is a searched grid of other switches: no point, no variant."""
    with pytest.raises(ValueError, match="S13"):
        Switches.for_variant("S13")
    assert Switches.for_variant("S13", stopping="llm", plan_cache=True).variant() == "custom"


def test_unknown_variant_lists_the_choices():
    """A typo is a ValueError, not the full system."""
    with pytest.raises(ValueError, match="unknown variant"):
        Switches.for_variant("S99")


def test_every_variant_changes_exactly_its_fields():
    """Each named variant differs from the full system in only the fields of its table entry."""
    for name, values in {**ARCHITECTURE, **INGESTION}.items():
        if values:
            assert Switches.for_variant(name).model_dump(exclude_defaults=True) == values


@pytest.mark.parametrize("field,bad", [("retrieval_policy", "react"), ("weak_signal", "gini"), ("store_prior", "on"), ("munshi_gap_policy", "random"),
                                       ("repair_mode", "cegis"), ("critic_mode", "debate"), ("draft_mode", "ensemble"), ("topology", "swarm"),
                                       ("urgency_policy", "lifo"), ("output_format", "xml"), ("chunking", "sentence")])
def test_enum_fields_reject_unknown_values(field, bad):
    """A typo in a new enum field must not silently run the full system."""
    with pytest.raises(ValidationError):
        Switches(**{field: bad})


@pytest.mark.parametrize("kwargs", [
    {"retrieval_policy": "self_critique", "fixed_router": True},
    {"retrieval_policy": "adaptive", "free_planner": True},
    {"stopping": "llm", "fixed_router": True},
    {"weak_signal": "skew", "fixed_router": True},
    {"store_prior": "order", "fixed_router": True},
    {"store_prior": "only", "fixed_router": True},
    {"store_prior": "order", "free_planner": True},
    {"topology": "single_agent", "stopping": "llm"},
    {"topology": "single_agent", "free_planner": True},
    {"munshi_gap_policy": "hierarchy", "munshi_no_gap_check": True},
    {"repair_mode": "self_critique", "no_check_repair": True},
    {"critic_mode": "sampling", "no_sparring": True},
    {"critic_mode": "three_role", "no_sparring": True},
    {"abhiyojak_isolation": False, "no_sparring": True},
    {"abhiyojak_isolation": False, "critic_mode": "none"},
])
def test_invalid_combinations_are_rejected_with_a_message(kwargs):
    """Cross-field validators reject switch sets in which one switch has nothing to act on."""
    with pytest.raises(ValidationError, match="cannot combine"):
        Switches(**kwargs)


def test_store_prior_only_may_run_with_the_free_planner():
    """B5 (prior alone) has no contracts, so free_planner is a legal partner."""
    assert Switches(store_prior="only", free_planner=True).store_prior == "only"


def test_repair_mode_none_and_critic_mode_none_are_the_existing_ablations():
    """repair_mode='none' is A2 and critic_mode='none' is A8; the legacy flags are set to match."""
    assert Switches(repair_mode="none").no_check_repair and Switches(repair_mode="none").variant() == "A2"
    assert Switches(critic_mode="none").no_sparring and Switches(critic_mode="none").variant() == "A8"
    assert Switches(repair_mode="none", critic_mode="none").variant() == "A9"


def test_new_fields_round_trip_through_dict():
    """Eval runs store switches with the results: the new fields survive dump and load."""
    s = Switches(store_prior="order", output_format="free_then_parse", no_guard=True, topology="sequential")
    assert Switches(**s.model_dump()) == s


def test_implemented_variants_are_s3_and_the_existing_ablations():
    """Only S3, S3b, A1-A10, P5, P6 and full have behaviour; every other defined id is not implemented yet."""
    done = Switches.implemented_variants()
    # RECONCILED: sweep 1 implemented S1 (retrieval_policy='self_critique') and S2 ('adaptive') and S5 (graph_expansion) and S4 (weak_signal)
    # RECONCILED: sweep 2 implemented S8 (repair_mode='self_critique'), S10 (abhiyojak_isolation=False) S9 (critic_mode='sampling'), S11 (critic_mode='three_role'), S11b / S11c (draft_mode) and S15 (output_format='reasoning_first')
    # RECONCILED: sweep 3 implemented S17, S17b, S17c, S17d (the injection-defence flags) and S7 (munshi_gap_policy='hierarchy') and P7 (munshi_image_only) and S14, S14b, S14c, S14d (serving)
    # RECONCILED: sweep 4 implemented S6 / A12 (store_prior='order') and B5 / S6b (store_prior='only')
    # RECONCILED: sweep 4 implemented S16 / S16b (chunking) and S12 (topology='sequential') and S12b ('single_agent')
    assert done == {"full", "S6", "B5", "S12", "S12b", "S13", "S16", "S16b", "S7", "S14", "S14b", "S14c", "S14d", "S1", "S2", "S3", "S3b", "S4", "S5", "S8", "S9", "S10", "S11", "S11b", "S11c", "S15", "S17", "S17b", "S17c", "S17d", "P5", "P6", "P7", *(f"A{i}" for i in range(1, 11))}
    # RECONCILED: every defined id is now implemented (S13 as the search harness, `eval/runners/workflow_search.py`)


@pytest.mark.parametrize("name", ["full", "A9", "a10", "S1", "S2", "S3", "S5", "S8", "A2b", "S10", "A8c", "S9", "A8b", "S15", "A13", "S11", "A8d", "A16", "A11b", "s3b", "P5", "S17", "A15", "S17b", "S17c", "S17d", "S7", "A11a", "P7", "S6", "A12", "B5", "S6b", "S12", "S12b", "S13", "S16", "S16b"])  # RECONCILED: S17 / A15, S7 / A11a and P7 built in sweep 3; S8 / A2b, S10 / A8c and S9 / A8b and S15 / A13 and S11 / A8d built in sweep 2
def test_assert_variant_implemented_accepts_built_variants(name):
    """Built variants (and the alias of S3) pass silently."""
    assert_variant_implemented(name)


@pytest.mark.parametrize("name", ["S13", "S6", "A12", "B5"])  # RECONCILED: every id is built in sweep 4, so the id is removed from the implemented set for this test
#  # RECONCILED: A15 (S17), S7 / A11a and P7 built in sweep 3; A2b (S8), A8c (S10) and A8b (S9) and A13 (S15) and A8d (S11) built in sweep 2
def test_assert_variant_implemented_fails_loudly_on_the_rest(name, monkeypatch):
    """A selected variant with no behaviour raises NotImplementedError naming it."""
    from vakeel_sahayak.orchestration import switches as sw_mod

    monkeypatch.setattr(sw_mod, "IMPLEMENTED_VARIANTS", sw_mod.IMPLEMENTED_VARIANTS - {sw_mod.canonical_variant(name)})
    with pytest.raises(NotImplementedError, match=name):
        assert_variant_implemented(name)


def test_assert_variant_implemented_rejects_unknown_ids():
    """An unknown id is a ValueError, not an unimplemented one."""
    with pytest.raises(ValueError):
        assert_variant_implemented("S99")


def test_alias_table_points_only_at_known_variants():
    """Every alias resolves to a defined variant."""
    for target in VARIANT_ALIASES.values():
        assert target in {*ARCHITECTURE, "B5"}


def test_runner_dispatch_raises_for_unimplemented_variant():
    """The system runner refuses an unimplemented arm with a NotImplementedError naming it; built arms still resolve."""
    from vakeel_sahayak.eval.runners.systems import system_runner

    assert system_runner("S12b")[1].variant() == "S12b"  # RECONCILED: S12 is built in sweep 4
    with pytest.raises(ValueError, match="grid point"):  # RECONCILED: S13 is built in sweep 4 (a searched grid point needs fields, so the runner cannot name it)
        system_runner("S13")
    assert system_runner("b5")[1].variant() == "B5"
    assert system_runner("A9")[1].variant() == "A9"
