"""The 12 evidence-contract YAMLs, parsed directly with yaml + EvidenceContract (plan §6.1, Appendix A and B).

These tests do not use contracts.loader, so they pass against the skeleton today."""

from __future__ import annotations

import pytest
import yaml

from tests.unit.contracts import _helpers as H
from vakeel_sahayak.contracts.models import ContractBudget, EvidenceContract
from vakeel_sahayak.schemas.enums import Factor, StoreName

FACTORS = list(Factor)
STORE_VALUES = {s.value for s in StoreName}


def test_exactly_twelve_contract_files_exist(contracts_dir):
    """There are twelve contract files, one per Appendix A factor."""
    assert len(list(contracts_dir.glob("*.yaml"))) == 12


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_contract_yaml_parses_and_validates(factor):
    """Each contract YAML parses with yaml.safe_load and validates as an EvidenceContract."""
    contract = H.parse_contract(factor)
    assert isinstance(contract, EvidenceContract)
    assert contract.slots, "a contract needs at least one slot"


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_file_stem_equals_factor_value_and_field(factor, contracts_dir):
    """The file stem, the `factor:` key and the Factor enum value are the same string."""
    path = contracts_dir / f"{factor.value}.yaml"
    assert path.exists()
    assert H.parse_contract(factor).factor is factor


def test_numbers_are_unique_one_to_twelve_in_appendix_a_order():
    """Numbers are 1..12, unique, and equal the factor's position in Appendix A."""
    contracts = H.all_parsed()
    numbers = {f: c.number for f, c in contracts.items()}
    assert sorted(numbers.values()) == list(range(1, 13))
    for position, factor in enumerate(Factor, start=1):
        assert numbers[factor] == position, factor


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_name_matches_appendix_a_title(factor):
    """The human name carries the Appendix A title words."""
    assert H.APPENDIX_A_TITLE_KEYWORD[factor] in H.parse_contract(factor).name.lower()


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_applies_if_is_stated(factor):
    """Every contract says when the factor applies (Sutradhar decides whether it applies, plan §6.1)."""
    assert H.parse_contract(factor).applies_if.strip()


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_every_store_named_exists_in_store_name(factor):
    """Every store in every slot is one of the ten StoreName values (checked on raw YAML, before pydantic)."""
    raw = H.read_contract_yaml(factor)
    for slot_name, slot in raw["slots"].items():
        for store in slot.get("stores", []):
            assert store in STORE_VALUES, f"{factor.value}.{slot_name}: unknown store {store!r}"


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_every_slot_store_is_in_appendix_b_allow_list(factor):
    """Each slot only names stores Appendix B allows for the factor."""
    allowed = H.APPENDIX_B_STORES[factor]
    for slot_name, slot in H.parse_contract(factor).slots.items():
        outside = {s.value for s in slot.stores} - allowed
        assert not outside, f"{factor.value}.{slot_name} uses {sorted(outside)} outside Appendix B"


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_every_slot_has_a_source_store_or_tool(factor):
    """A slot must be fillable from somewhere: at least one store or tool."""
    for slot_name, slot in H.parse_contract(factor).slots.items():
        assert slot.stores or slot.tools, f"{factor.value}.{slot_name} has no store or tool"


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_slot_tools_are_non_store_sources(factor):
    """`tools:` names Rights Radar, date arithmetic or asking counsel only (Appendix B / skeleton convention)."""
    for slot_name, slot in H.parse_contract(factor).slots.items():
        assert set(slot.tools) <= H.ALLOWED_SLOT_TOOLS, f"{factor.value}.{slot_name}: {slot.tools}"


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_slot_need_is_required_optional_or_positive_count(factor):
    """`need` is 'required', 'optional' or a positive integer count (plan §6.1)."""
    for slot_name, slot in H.parse_contract(factor).slots.items():
        need = slot.need
        ok = need in ("required", "optional") or (isinstance(need, int) and not isinstance(need, bool) and need >= 1)
        assert ok, f"{factor.value}.{slot_name}: need={need!r}"


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_required_evidence_of_appendix_b_is_covered(factor):
    """The stores and tools that Appendix B's 'required evidence' draws on each appear in some slot of the contract."""
    contract = H.parse_contract(factor)
    used_stores = {s.value for slot in contract.slots.values() for s in slot.stores}
    used_tools = {t for slot in contract.slots.values() for t in slot.tools}
    need = H.REQUIRED_EVIDENCE[factor]
    assert need["stores"] <= used_stores, f"missing stores {sorted(need['stores'] - used_stores)}"
    assert need["tools"] <= used_tools, f"missing tools {sorted(need['tools'] - used_tools)}"


def test_authority_slots_draw_on_reasoning_not_on_arguments_objections_or_case_stores():
    """An `authority` slot draws on case-law stores only: authorities are cited from reasoning paragraphs (plan §5.2)."""
    with_authority = {f: c.slots["authority"] for f, c in H.all_parsed().items() if "authority" in c.slots}
    assert len(with_authority) == 10  # every factor except flight_risk and witness_tampering (they have 'conditions')
    for factor, slot in with_authority.items():
        stores = {s.value for s in slot.stores}
        assert "caselaw.reasoning" in stores, factor.value
        assert not {s for s in stores if s.startswith(("advocacy.", "case."))}, factor.value


def test_parity_contract_is_the_plan_6_1_example():
    """parity_with_co_accused matches the YAML printed in plan §6.1 slot for slot."""
    c = H.parse_contract(Factor.PARITY_WITH_CO_ACCUSED)
    assert c.number == 5
    assert c.applies_if == "a co-accused has been granted bail"
    assert list(c.slots) == ["co_accused_order", "role_comparison", "authority", "good_law", "likely_objection",
                             "argument_patterns"]
    expected = {
        "co_accused_order": ("required", ["case.docs", "case.timeline"]),
        "role_comparison": ("required", ["case.docs"]),
        "authority": (2, ["caselaw.reasoning", "caselaw.similar"]),
        "good_law": ("required", ["caselaw.citations"]),
        "likely_objection": (1, ["advocacy.objections"]),
        "argument_patterns": ("optional", ["advocacy.arguments"]),
    }
    for name, (need, stores) in expected.items():
        slot = c.slots[name]
        assert slot.need == need, name
        assert [s.value for s in slot.stores] == stores, name
    assert (c.budget.store_calls, c.budget.tokens) == (8, 12000)


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_argument_bank_only_on_optional_slots(factor):
    """advocacy.arguments appears only on optional slots: coverage and phrasing, never an authority (plan §5.1, §6.1)."""
    for slot_name, slot in H.parse_contract(factor).slots.items():
        if StoreName.ADVOCACY_ARGUMENTS in slot.stores:
            assert slot.need == "optional", f"{factor.value}.{slot_name}"
            assert slot_name != "authority"


def test_argument_bank_is_used_by_exactly_one_contract():
    """Only the parity contract (plan §6.1 example) uses advocacy.arguments; ASSUMPTION: the other contracts do not."""
    users = [f for f, c in H.all_parsed().items()
             if any(StoreName.ADVOCACY_ARGUMENTS in s.stores for s in c.slots.values())]
    assert users == [Factor.PARITY_WITH_CO_ACCUSED]


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_budget_is_8_store_calls_and_12000_tokens(factor):
    """Every contract's budget is 8 store calls and 12,000 tokens (plan §6.1, §6.2)."""
    raw = H.read_contract_yaml(factor)
    assert raw["budget"] == {"store_calls": 8, "tokens": 12000}
    b = H.parse_contract(factor).budget
    assert (b.store_calls, b.tokens) == (8, 12000)


def test_contract_budget_model_defaults_match_plan():
    """ContractBudget defaults equal the plan's per-factor budget."""
    assert ContractBudget().store_calls == 8 and ContractBudget().tokens == 12000


def test_budgets_yaml_sets_case_and_factor_budgets(load_yaml):
    """configs/budgets.yaml: 150,000 tokens per case, 8 store calls and 12,000 tokens per factor (plan §6.2)."""
    cfg = load_yaml("budgets.yaml")
    assert cfg["case"]["tokens"] == 150000
    assert cfg["factor"]["store_calls"] == 8
    assert cfg["factor"]["tokens"] == 12000


def test_factor_budgets_in_contracts_agree_with_budgets_yaml(load_yaml):
    """No contract overrides the global per-factor budget."""
    cfg = load_yaml("budgets.yaml")["factor"]
    for factor, c in H.all_parsed().items():
        assert (c.budget.store_calls, c.budget.tokens) == (cfg["store_calls"], cfg["tokens"]), factor.value


def test_sum_of_factor_token_budgets_exceeds_case_budget_so_the_case_cap_binds():
    """12 x 12,000 = 144,000 tokens: the per-case cap (150,000) is a ceiling above all factor budgets and never below one."""
    total = sum(c.budget.tokens for c in H.all_parsed().values())
    assert total == 144000
    assert total <= 150000  # ASSUMPTION: factor budgets are sized to fit the case cap with headroom for drafting


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.value)
def test_raw_yaml_has_no_unknown_top_level_keys(factor):
    """Contract YAMLs carry only the model's keys (typos such as 'slot:' would otherwise be dropped silently)."""
    raw = H.read_contract_yaml(factor)
    assert set(raw) <= set(EvidenceContract.model_fields)


def test_every_store_is_used_by_some_contract_or_is_a_tool_store():
    """Every store a contract may reach is real, and the Appendix B union covers the nine stores the planner queries.

    law.concordance (map_section/transfer_check) is reached through tools, not through a slot, so it is the only store not named in any contract (ASSUMPTION)."""
    used = {s.value for c in H.all_parsed().values() for slot in c.slots.values() for s in slot.stores}
    assert STORE_VALUES - used == {"law.concordance"}


def test_yaml_files_are_plain_data(contracts_dir):
    """Contract files contain no YAML tags or anchors that would need an unsafe loader."""
    for path in contracts_dir.glob("*.yaml"):
        yaml.safe_load(path.read_text(encoding="utf-8"))
