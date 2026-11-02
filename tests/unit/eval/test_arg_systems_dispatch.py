"""Dispatch of the three ids that need an argument (`driver run --system A5:base_4b | A10:<store> | S13:<field>=<value>`): each is accepted with its argument,
a bare id is refused with a message that names the `ID:ARG` form (a run never starts as Full under another name), and every shared store has its own A10 arm."""
from __future__ import annotations

import pytest

from vakeel_sahayak.eval.runners.systems import shared_stores, system_runner, system_switches


@pytest.mark.parametrize("bare,hint", [("A5", "A5:base_4b"), ("A10", "A10:<store>"), ("S13", "S13:stopping=llm")])
def test_a_bare_argument_id_is_refused_naming_the_argument_form(bare, hint):
    with pytest.raises(ValueError, match=hint.replace("<", "\\<").replace(">", "\\>").replace("|", "\\|")):
        system_runner(bare)


def test_a5_arms_set_the_extractor_and_default_is_untouched():
    assert system_switches("A5:base_4b").extractor == "base_4b"
    assert system_switches("A5:prompted_32b").extractor == "prompted_32b"
    with pytest.raises(ValueError):
        system_switches("A5:finetuned_4b")


def test_a10_has_one_arm_per_shared_store_and_refuses_an_unknown_store():
    stores = shared_stores()
    assert len(stores) == 7
    assert {system_switches(f"A10:{s}").knockout_store for s in stores} == set(stores)
    with pytest.raises(ValueError):
        system_switches("A10:not.a.store")


def test_s13_grid_point_sets_its_field_and_a_bad_field_is_refused():
    assert system_switches("S13:stopping=llm").stopping == "llm"
    with pytest.raises(ValueError):
        system_switches("S13:stopping")
