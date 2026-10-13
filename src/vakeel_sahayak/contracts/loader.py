"""Contract loader and validator (plan §6.1)."""

from __future__ import annotations

from pathlib import Path

import yaml

from vakeel_sahayak.contracts.models import EvidenceContract
from vakeel_sahayak.schemas.enums import Factor, StoreName

FACTORS_DIR = Path(__file__).parent / "factors"

# Appendix B, column "Stores Sutradhar may use": the stores a factor's slots may draw from (tools are checked apart).
ALLOWED_STORES: dict[Factor, frozenset[StoreName]] = {
    Factor.GRAVITY_AND_PUNISHMENT: frozenset(
        {
            StoreName.LAW_STATUTES,
            StoreName.CASELAW_REASONING,
            StoreName.CASELAW_CITATIONS,
            StoreName.ADVOCACY_OBJECTIONS,
        }
    ),
    Factor.CUSTODY_PERIOD: frozenset(
        {StoreName.CASE_TIMELINE, StoreName.CASELAW_REASONING, StoreName.ADVOCACY_OBJECTIONS}
    ),
    Factor.CHARGE_SHEET_FILED: frozenset(
        {StoreName.CASE_TIMELINE, StoreName.CASE_DOCS, StoreName.CASELAW_REASONING, StoreName.ADVOCACY_OBJECTIONS}
    ),
    Factor.TRIAL_DELAY: frozenset(
        {StoreName.CASE_DOCS, StoreName.CASE_TIMELINE, StoreName.CASELAW_REASONING, StoreName.CASELAW_CITATIONS}
    ),
    Factor.PARITY_WITH_CO_ACCUSED: frozenset(
        {
            StoreName.CASE_DOCS,
            StoreName.CASE_TIMELINE,
            StoreName.CASELAW_REASONING,
            StoreName.CASELAW_SIMILAR,
            StoreName.CASELAW_CITATIONS,
            StoreName.ADVOCACY_OBJECTIONS,
            StoreName.ADVOCACY_ARGUMENTS,  # plan §6.1's worked contract uses it; Appendix B omits it
        }
    ),
    Factor.ANTECEDENTS: frozenset({StoreName.CASE_FACTS, StoreName.CASELAW_REASONING, StoreName.ADVOCACY_OBJECTIONS}),
    Factor.FLIGHT_RISK: frozenset(
        {StoreName.CASE_FACTS, StoreName.CASELAW_REASONING, StoreName.CASELAW_SIMILAR, StoreName.ADVOCACY_OBJECTIONS}
    ),
    Factor.WITNESS_TAMPERING: frozenset(
        {StoreName.CASE_DOCS, StoreName.CASELAW_REASONING, StoreName.ADVOCACY_OBJECTIONS}
    ),
    Factor.WEAK_PRIMA_FACIE: frozenset({StoreName.CASE_DOCS, StoreName.LAW_STATUTES, StoreName.CASELAW_REASONING}),
    Factor.HEALTH_AGE_FAMILY: frozenset({StoreName.CASE_FACTS, StoreName.LAW_STATUTES, StoreName.CASELAW_REASONING}),
    Factor.STATUTORY_BAR: frozenset({StoreName.LAW_STATUTES, StoreName.CASELAW_REASONING, StoreName.CASELAW_CITATIONS}),
    Factor.UNDERTRIAL_PERIOD: frozenset({StoreName.LAW_STATUTES, StoreName.CASELAW_REASONING}),  # plus Rights Radar
}

# Appendix A order: the `number` each contract must carry.
FACTOR_NUMBERS: dict[Factor, int] = {factor: i for i, factor in enumerate(Factor, start=1)}


def load_contract(factor: Factor) -> EvidenceContract:
    """Load factors/<factor>.yaml and validate against EvidenceContract.

    Args:
        factor: which factor

    Returns:
        The contract.

    Raises:
        ValueError: if the YAML does not parse into an EvidenceContract or names another factor.
    """
    path = FACTORS_DIR / f"{Factor(factor).value}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"no evidence contract file for factor {factor!r}: {path}")
    contract = EvidenceContract.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    if contract.factor != Factor(factor):
        raise ValueError(f"{path.name} declares factor {contract.factor.value!r}")
    return contract


def load_all_contracts() -> dict[Factor, EvidenceContract]:
    """Load all twelve contracts.

    Returns:
        Mapping.
    """
    return {factor: load_contract(factor) for factor in Factor}


def _known_tool_names() -> set[str]:
    """Tool names registered in tools/registry.py, read from its static list (no tool module is imported)."""
    from vakeel_sahayak.tools.registry import ALL_TOOL_MODULES

    return {name for _, name in ALL_TOOL_MODULES}


def validate_contract(
    contract: EvidenceContract, factor_tokens: int | None = None, factor_store_calls: int | None = None
) -> list[str]:
    """Check that every slot's stores exist and are within the Appendix B allow-list for the factor.

    Also checks the Appendix A number, that slot `need` values are 'required', 'optional' or a positive count,
    that slot tools are registered tools, that every slot names a store or a tool, and the per-factor budget
    (8 store calls, 12,000 tokens by default; plan §6.2).

    Args:
        contract: see behaviour
        factor_tokens: per-factor token cap; defaults to configs/budgets.yaml
        factor_store_calls: per-factor store-call cap; defaults to configs/budgets.yaml

    Returns:
        List of problems (empty if valid).
    """
    from vakeel_sahayak.config import load_config

    problems: list[str] = []
    name = contract.factor.value
    if factor_tokens is None or factor_store_calls is None:
        budgets = load_config().budgets
        factor_tokens = factor_tokens if factor_tokens is not None else budgets.tokens_per_factor
        factor_store_calls = factor_store_calls if factor_store_calls is not None else budgets.store_calls_per_factor
    if contract.number != FACTOR_NUMBERS[contract.factor]:
        problems.append(f"{name}: number {contract.number} should be {FACTOR_NUMBERS[contract.factor]} (Appendix A)")
    allowed = ALLOWED_STORES[contract.factor]
    tools = _known_tool_names()
    if not contract.slots:
        problems.append(f"{name}: no slots")
    for slot_name, slot in contract.slots.items():
        if isinstance(slot.need, int):
            if isinstance(slot.need, bool) or slot.need < 1:
                problems.append(f"{name}.{slot_name}: need must be a positive count")
        elif slot.need not in ("required", "optional"):
            problems.append(f"{name}.{slot_name}: need {slot.need!r} is not required, optional or a count")
        for store in slot.stores:
            if store not in allowed:
                store_name = getattr(store, "value", store)  # a raw string when the enum check was bypassed
                problems.append(f"{name}.{slot_name}: store {store_name} is outside the Appendix B allow-list")
        for tool in slot.tools:
            if tool not in tools:
                problems.append(f"{name}.{slot_name}: unknown tool {tool!r}")
        if not slot.stores and not slot.tools:
            problems.append(f"{name}.{slot_name}: slot names neither a store nor a tool")
    if contract.budget.store_calls > factor_store_calls:
        problems.append(f"{name}: store_calls {contract.budget.store_calls} exceeds the cap of {factor_store_calls}")
    if contract.budget.tokens > factor_tokens:
        problems.append(f"{name}: tokens {contract.budget.tokens} exceeds the cap of {factor_tokens}")
    return problems


def validate_all_contracts(contracts: dict[Factor, EvidenceContract] | None = None) -> list[str]:
    """Validate every contract, that all twelve exist, and that factor token budgets fit the per-case budget.

    Args:
        contracts: defaults to load_all_contracts()

    Returns:
        List of problems (empty if valid).
    """
    from vakeel_sahayak.config import load_config

    contracts = contracts if contracts is not None else load_all_contracts()
    problems = [f"missing contract for {f.value}" for f in Factor if f not in contracts]
    for contract in contracts.values():
        problems += validate_contract(contract)
    case_cap = load_config().budgets.tokens_per_case
    total = sum(c.budget.tokens for c in contracts.values())
    if total > case_cap:
        problems.append(f"factor token budgets sum to {total}, above the per-case cap of {case_cap}")
    return problems
