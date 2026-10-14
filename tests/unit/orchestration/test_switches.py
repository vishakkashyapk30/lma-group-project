"""orchestration/switches.Switches: ablation and variant flags (plan §15.4 A1-A10, §15.5 P5-P6, §19).

Defaults are the full system. Each ablation is a flag, not a code fork (skeleton conventions 'Agents').
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vakeel_sahayak.orchestration.switches import Switches
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
EXTRACTORS = ["finetuned_4b", "base_4b", "prompted_32b"]


def test_field_set_matches_the_ablation_table():
    """Exactly the nine boolean flags plus knockout_store (A10) and extractor (A5): A9 is no_sparring + no_check_repair."""
    assert set(Switches.model_fields) == set(FLAGS) | {"knockout_store", "extractor"}


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
