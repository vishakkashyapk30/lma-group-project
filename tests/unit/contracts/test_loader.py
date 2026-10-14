"""contracts.loader behaviour (plan §6.1, Appendix B): load_contract, load_all_contracts, validate_contract.

These tests fail with NotImplementedError until the loader is implemented."""

from __future__ import annotations

import pytest

from tests.unit.contracts import _helpers as H
from vakeel_sahayak.contracts.loader import load_all_contracts, load_contract, validate_contract
from vakeel_sahayak.contracts.models import EvidenceContract, Slot
from vakeel_sahayak.schemas.enums import Factor, StoreName


@pytest.mark.parametrize("factor", list(Factor), ids=lambda f: f.value)
def test_load_contract_returns_the_factors_contract(factor):
    """load_contract(f) returns the validated contract of that factor, equal to the YAML parsed directly."""
    contract = load_contract(factor)
    assert isinstance(contract, EvidenceContract)
    assert contract.factor is factor
    assert contract == H.parse_contract(factor)


def test_load_all_contracts_returns_twelve_keyed_by_factor():
    """load_all_contracts returns all twelve contracts keyed by Factor, numbered 1..12."""
    contracts = load_all_contracts()
    assert set(contracts) == set(Factor)
    assert len(contracts) == 12
    assert sorted(c.number for c in contracts.values()) == list(range(1, 13))
    assert all(c.factor is f for f, c in contracts.items())


def test_load_contract_parity_has_the_plan_slots():
    """The loaded parity contract has the six slots of plan §6.1 with authority need 2."""
    c = load_contract(Factor.PARITY_WITH_CO_ACCUSED)
    assert list(c.slots) == ["co_accused_order", "role_comparison", "authority", "good_law", "likely_objection",
                             "argument_patterns"]
    assert c.slots["authority"].need == 2


@pytest.mark.parametrize("factor", list(Factor), ids=lambda f: f.value)
def test_validate_contract_returns_no_problems_for_shipped_contracts(factor):
    """Every shipped contract validates cleanly: validate_contract returns an empty list."""
    assert validate_contract(load_contract(factor)) == []


def _contract_with_slot(factor: Factor, slot_name: str, slot: Slot) -> EvidenceContract:
    base = H.parse_contract(factor)
    slots = dict(base.slots)
    slots[slot_name] = slot
    return base.model_copy(update={"slots": slots})


def test_validate_contract_reports_store_outside_the_allow_list():
    """A slot using a real store that Appendix B does not allow for the factor yields a problem naming that store."""
    # custody_period may not use law.concordance (Appendix B row 2: case.timeline, caselaw.reasoning, advocacy.objections)
    bad = _contract_with_slot(
        Factor.CUSTODY_PERIOD, "mapping", Slot(need="required", stores=[StoreName.LAW_CONCORDANCE])
    )
    problems = validate_contract(bad)
    assert problems, "a store outside the allow-list must be reported"
    assert any("law.concordance" in p for p in problems)
    assert all(isinstance(p, str) for p in problems)


def test_validate_contract_reports_argument_bank_for_a_non_parity_factor():
    """advocacy.arguments is outside every allow-list except parity's, so using it elsewhere is a problem."""
    bad = _contract_with_slot(
        Factor.TRIAL_DELAY, "patterns", Slot(need="optional", stores=[StoreName.ADVOCACY_ARGUMENTS])
    )
    assert any("advocacy.arguments" in p for p in validate_contract(bad))


def test_validate_contract_reports_unknown_store_name():
    """A slot naming a store that does not exist (bypassing enum validation) is reported by name."""
    base = H.parse_contract(Factor.CHARGE_SHEET_FILED)
    ghost = Slot.model_construct(need="required", stores=["case.dossier"], tools=[], description="")
    bad = base.model_copy(update={"slots": {**base.slots, "ghost": ghost}})
    problems = validate_contract(bad)
    assert any("case.dossier" in p for p in problems)


def test_validate_contract_reports_every_offending_slot():
    """Two bad slots give at least two problems (one per slot), none for the good slots."""
    base = H.parse_contract(Factor.WEAK_PRIMA_FACIE)
    slots = dict(base.slots)
    slots["a"] = Slot(need="required", stores=[StoreName.ADVOCACY_OBJECTIONS])
    slots["b"] = Slot(need="required", stores=[StoreName.CASELAW_SIMILAR])
    problems = validate_contract(base.model_copy(update={"slots": slots}))
    assert len(problems) >= 2
    assert any("advocacy.objections" in p for p in problems)
    assert any("caselaw.similar" in p for p in problems)
    assert not any("sections_text" in p for p in problems)


def test_validate_contract_does_not_mutate_the_contract():
    """Validation is read-only."""
    c = load_contract(Factor.STATUTORY_BAR)
    before = c.model_dump()
    validate_contract(c)
    assert c.model_dump() == before
