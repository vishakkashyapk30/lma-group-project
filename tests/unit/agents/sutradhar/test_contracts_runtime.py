"""Run-time use of the real evidence contracts: unfilled slots and allowed stores (plan §6.1, Appendix B)."""

from __future__ import annotations

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from tests.unit.agents._helpers import REPO_ROOT
from vakeel_sahayak.agents.sutradhar.contracts_runtime import allowed_stores, unfilled_slots
from vakeel_sahayak.contracts.models import EvidenceContract
from vakeel_sahayak.schemas.enums import Factor, SlotStatus, StoreName
from vakeel_sahayak.schemas.retrieval_plan import SlotResult

ALL_FACTORS = [f.value for f in Factor]


def _contract(contracts_dir, factor: str) -> EvidenceContract:
    return EvidenceContract.model_validate(yaml.safe_load((contracts_dir / f"{factor}.yaml").read_text(encoding="utf-8")))


def _slot(name: str, status: SlotStatus) -> SlotResult:
    return SlotResult(slot=name, status=status)


def test_parity_unfilled_with_nothing_filled(contracts_dir):
    """With nothing filled every needed slot is open, in contract order; the optional slot never blocks."""
    # ASSUMPTION: 'need: optional' slots are not 'still needing evidence' (the loop stops when required slots are FILLED).
    contract = _contract(contracts_dir, "parity_with_co_accused")
    assert unfilled_slots(contract, []) == ["co_accused_order", "role_comparison", "authority", "good_law", "likely_objection"]


def test_parity_unfilled_weak_and_missing_still_count(contracts_dir):
    """Only FILLED closes a slot; WEAK and MISSING remain open; order follows the contract, not the input."""
    contract = _contract(contracts_dir, "parity_with_co_accused")
    filled = [
        _slot("good_law", SlotStatus.FILLED),
        _slot("co_accused_order", SlotStatus.FILLED),
        _slot("authority", SlotStatus.WEAK),
        _slot("likely_objection", SlotStatus.MISSING),
    ]
    assert unfilled_slots(contract, filled) == ["role_comparison", "authority", "likely_objection"]


def test_parity_all_filled_leaves_nothing(contracts_dir):
    """When every needed slot is FILLED nothing is left to retrieve."""
    contract = _contract(contracts_dir, "parity_with_co_accused")
    filled = [_slot(n, SlotStatus.FILLED) for n in contract.slots]
    assert unfilled_slots(contract, filled) == []


@pytest.mark.parametrize("factor", ALL_FACTORS)
def test_unfilled_with_nothing_filled_is_every_non_optional_slot(contracts_dir, factor):
    """For all 12 contracts: with no results, the open slots are exactly the non-optional ones, in YAML order."""
    raw = yaml.safe_load((contracts_dir / f"{factor}.yaml").read_text(encoding="utf-8"))
    expected = [n for n, s in raw["slots"].items() if s["need"] != "optional"]
    assert unfilled_slots(EvidenceContract.model_validate(raw), []) == expected


@given(data=st.data())
def test_unfilled_matches_statuses(data):
    """Property over random statuses: a needed slot is open iff its status is not FILLED; order preserved."""
    contracts_dir = REPO_ROOT / "src" / "vakeel_sahayak" / "contracts" / "factors"
    factor = data.draw(st.sampled_from(ALL_FACTORS))
    raw = yaml.safe_load((contracts_dir / f"{factor}.yaml").read_text(encoding="utf-8"))
    contract = EvidenceContract.model_validate(raw)
    statuses = {n: data.draw(st.sampled_from(list(SlotStatus))) for n in raw["slots"]}
    filled = [_slot(n, s) for n, s in statuses.items()]
    expected = [n for n, s in raw["slots"].items() if s["need"] != "optional" and statuses[n] != SlotStatus.FILLED]
    assert unfilled_slots(contract, filled) == expected


def test_allowed_stores_parity_examples(contracts_dir):
    """Plan §6.1 example: authority may use caselaw.reasoning and caselaw.similar, nothing else."""
    contract = _contract(contracts_dir, "parity_with_co_accused")
    assert allowed_stores(contract, "authority") == [StoreName.CASELAW_REASONING, StoreName.CASELAW_SIMILAR]
    assert allowed_stores(contract, "co_accused_order") == [StoreName.CASE_DOCS, StoreName.CASE_TIMELINE]
    assert allowed_stores(contract, "good_law") == [StoreName.CASELAW_CITATIONS]
    assert allowed_stores(contract, "argument_patterns") == [StoreName.ADVOCACY_ARGUMENTS]


def test_allowed_stores_tool_only_slot_has_no_store(contracts_dir):
    """A slot fed by a tool (rights_check) has an empty store list."""
    contract = _contract(contracts_dir, "undertrial_period")
    assert allowed_stores(contract, "rights_report") == []


@pytest.mark.parametrize("factor", ALL_FACTORS)
def test_allowed_stores_equal_the_yaml_for_every_slot(contracts_dir, factor):
    """For every slot of every contract the allowed stores are exactly the YAML list (as StoreName, same order)."""
    raw = yaml.safe_load((contracts_dir / f"{factor}.yaml").read_text(encoding="utf-8"))
    contract = EvidenceContract.model_validate(raw)
    for name, slot in raw["slots"].items():
        assert allowed_stores(contract, name) == [StoreName(s) for s in slot.get("stores", [])]


def test_allowed_stores_unknown_slot_is_rejected(contracts_dir):
    """Asking for a slot the contract does not have is an error, not an empty list."""
    contract = _contract(contracts_dir, "parity_with_co_accused")
    # ASSUMPTION: KeyError (or another LookupError/ValueError) for an unknown slot name.
    with pytest.raises((KeyError, ValueError, LookupError)):
        allowed_stores(contract, "no_such_slot")
