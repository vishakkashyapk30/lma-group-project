"""Fixed router (A6, plan §6.5, §15.4, §19): contracts run in a fixed order with templated queries; no planning, no
sufficiency check, no LLM call."""

from __future__ import annotations

import sys

import pytest

from tests.fakes.models import ScriptedLLM
from tests.unit.agents._helpers import CASE_DATE, make_state
from vakeel_sahayak.agents.sutradhar.fixed_router import run_fixed_router
from vakeel_sahayak.contracts.models import EvidenceContract
from vakeel_sahayak.schemas.enums import Factor, StoreName
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack

import yaml


@pytest.fixture()
def no_llm(monkeypatch):
    """A strict ScriptedLLM with no scripts, installed wherever `get_llm` is imported: any LLM use fails the test."""
    llm = ScriptedLLM()  # strict: an unscripted call raises AssertionError

    def fake_get_llm(role: str):
        return llm

    monkeypatch.setattr("vakeel_sahayak.models.factory.get_llm", fake_get_llm)
    for name, mod in list(sys.modules.items()):
        if name.startswith("vakeel_sahayak") and mod is not None and hasattr(mod, "get_llm"):
            monkeypatch.setattr(mod, "get_llm", fake_get_llm)
    return llm


@pytest.fixture()
def run(no_llm, install_stores, dossier, expected_rights_report):
    install_stores()
    state = make_state(dossier=dossier, rights=expected_rights_report)
    return lambda: run_fixed_router(state)


def test_returns_one_pack_per_applicable_factor(run):
    """Each applicable contract yields exactly one EvidencePack; no factor repeats."""
    packs = run()
    assert packs and all(isinstance(p, EvidencePack) for p in packs)
    factors = [p.factor for p in packs]
    assert len(factors) == len(set(factors))
    assert Factor.PARITY_WITH_CO_ACCUSED in factors  # co-accused Co-accused-1 granted bail on 2024-12-05
    assert Factor.CHARGE_SHEET_FILED in factors  # charge sheet filed 2024-11-02
    assert Factor.STATUTORY_BAR not in factors  # no special act in case-0007


def test_parity_runs_first_then_appendix_a_order(run):
    """ASSUMPTION: parity goes first when a co-accused was granted bail; the rest follow Appendix A order."""
    factors = [p.factor for p in run()]
    assert factors[0] == Factor.PARITY_WITH_CO_ACCUSED
    rest = factors[1:]
    order = list(Factor)  # enum order is Appendix A order
    assert rest == sorted(rest, key=order.index)


def test_makes_no_llm_planning_call(run, no_llm):
    """The fixed router uses templated queries: the LLM is never called."""
    run()
    assert no_llm.calls == []


def test_every_pack_slot_uses_only_stores_of_its_contract(run, world, contracts_dir):
    """Only stores named in the applicable contracts are queried (no 'query everything', plan §6.5 B4 vs A6)."""
    packs = run()
    allowed: set[StoreName] = set()
    for p in packs:
        raw = yaml.safe_load((contracts_dir / f"{p.factor.value}.yaml").read_text(encoding="utf-8"))
        allowed |= {StoreName(s) for slot in EvidenceContract.model_validate(raw).slots.values() for s in slot.stores}
    queried = {name for name, store in world.stores.items() if store.calls}
    assert queried
    assert queried <= allowed


def test_shared_store_calls_carry_the_case_date_and_never_surface_later_orders(run, world):
    """Every reasoning search is bounded by the case date and DLHC-2025-0099 never appears in a pack."""
    packs = run()
    for method, kw in world.stores[StoreName.CASELAW_REASONING].calls:
        if method == "search":
            assert kw["before"] == CASE_DATE
    assert "DLHC-2025-0099" not in repr([p.model_dump() for p in packs])


def test_store_calls_stay_within_the_per_factor_budget(run, world):
    """No more than 8 store calls per factor (configs/budgets.yaml factor.store_calls)."""
    packs = run()
    total = sum(len(s.calls) for s in world.stores.values())
    assert total <= 8 * len(packs)


def test_deterministic(run):
    """Two runs over the same case give identical packs."""
    first = [p.model_dump() for p in run()]
    second = [p.model_dump() for p in run()]
    assert first == second
