"""Appendix B as data (plan Appendix B, §6.1) plus helpers for reading contract YAMLs directly."""

from __future__ import annotations

from pathlib import Path

import yaml

from vakeel_sahayak.contracts.models import EvidenceContract
from vakeel_sahayak.schemas.enums import Factor

F = Factor

# Appendix B column "Stores Sutradhar may use" (factor -> allowed store names).
# Rights Radar for factor 12 is a tool (rights_check), not a store, so it is listed in APPENDIX_B_TOOLS instead.
APPENDIX_B_STORES: dict[Factor, set[str]] = {
    F.GRAVITY_AND_PUNISHMENT: {"law.statutes", "caselaw.reasoning", "caselaw.citations", "advocacy.objections"},
    F.CUSTODY_PERIOD: {"case.timeline", "caselaw.reasoning", "advocacy.objections"},
    F.CHARGE_SHEET_FILED: {"case.timeline", "case.docs", "caselaw.reasoning", "advocacy.objections"},
    F.TRIAL_DELAY: {"case.docs", "case.timeline", "caselaw.reasoning", "caselaw.citations"},
    # ASSUMPTION: advocacy.arguments is added for parity only: the plan §6.1 example contract has the optional
    # argument_patterns slot on advocacy.arguments although the Appendix B row does not list it.
    F.PARITY_WITH_CO_ACCUSED: {
        "case.docs", "case.timeline", "caselaw.reasoning", "caselaw.similar", "caselaw.citations",
        "advocacy.objections", "advocacy.arguments",
    },
    F.ANTECEDENTS: {"case.facts", "caselaw.reasoning", "advocacy.objections"},
    F.FLIGHT_RISK: {"case.facts", "caselaw.reasoning", "caselaw.similar", "advocacy.objections"},
    F.WITNESS_TAMPERING: {"case.docs", "caselaw.reasoning", "advocacy.objections"},
    F.WEAK_PRIMA_FACIE: {"case.docs", "law.statutes", "caselaw.reasoning"},
    F.HEALTH_AGE_FAMILY: {"case.facts", "law.statutes", "caselaw.reasoning"},
    F.STATUTORY_BAR: {"law.statutes", "caselaw.reasoning", "caselaw.citations"},
    F.UNDERTRIAL_PERIOD: {"law.statutes", "caselaw.reasoning"},  # + Rights Radar (tool)
}

# Tools a slot may name in `tools:` (non-store sources: Rights Radar, date arithmetic, asking counsel).
ALLOWED_SLOT_TOOLS = {"rights_check", "date_calc", "ask_user"}

# Appendix B "Required evidence": for every factor, the stores/tools that at least one slot must draw on.
# Slot names other than parity's are inferred by the skeleton; the evidence itself is the plan's.
REQUIRED_EVIDENCE: dict[Factor, dict[str, set[str]]] = {
    # max punishment + bailability; Antil category (Rights Radar); gravity authority; likely objection
    F.GRAVITY_AND_PUNISHMENT: {"stores": {"law.statutes", "caselaw.reasoning", "advocacy.objections"},
                               "tools": {"rights_check"}},
    # custody days; prolonged-custody authority; likely objection
    F.CUSTODY_PERIOD: {"stores": {"case.timeline", "caselaw.reasoning", "advocacy.objections"},
                       "tools": {"date_calc"}},
    # charge-sheet date; authority; likely objection
    F.CHARGE_SHEET_FILED: {"stores": {"case.timeline", "caselaw.reasoning", "advocacy.objections"}, "tools": set()},
    # trial stage; delay authority; SC root
    F.TRIAL_DELAY: {"stores": {"case.docs", "caselaw.reasoning", "caselaw.citations"}, "tools": set()},
    # co-accused order; role comparison; >=2 authorities; good law; likely objection
    F.PARITY_WITH_CO_ACCUSED: {"stores": {"case.docs", "case.timeline", "caselaw.reasoning", "caselaw.similar",
                                          "caselaw.citations", "advocacy.objections"}, "tools": set()},
    # antecedents or a question to counsel; authority; likely objection
    F.ANTECEDENTS: {"stores": {"case.facts", "caselaw.reasoning", "advocacy.objections"}, "tools": {"ask_user"}},
    # roots in the community; conditions; likely objection
    F.FLIGHT_RISK: {"stores": {"case.facts", "caselaw.reasoning", "advocacy.objections"}, "tools": set()},
    # trial stage; key witnesses examined; conditions; likely objection
    F.WITNESS_TAMPERING: {"stores": {"case.docs", "caselaw.reasoning", "advocacy.objections"}, "tools": set()},
    # FIR allegations against sections; limited scope of a bail inquiry
    F.WEAK_PRIMA_FACIE: {"stores": {"case.docs", "law.statutes", "caselaw.reasoning"}, "tools": set()},
    # medical/personal papers; BNSS s.480 proviso; authority
    F.HEALTH_AGE_FAMILY: {"stores": {"case.facts", "law.statutes", "caselaw.reasoning"}, "tools": set()},
    # bar provision; twin-conditions authority; SC root
    F.STATUTORY_BAR: {"stores": {"law.statutes", "caselaw.reasoning", "caselaw.citations"}, "tools": set()},
    # RightsReport; statute text; authority
    F.UNDERTRIAL_PERIOD: {"stores": {"law.statutes", "caselaw.reasoning"}, "tools": {"rights_check"}},
}

# Appendix A titles: the contract's `name` must start from the same words.
APPENDIX_A_TITLE_KEYWORD: dict[Factor, str] = {
    F.GRAVITY_AND_PUNISHMENT: "gravity",
    F.CUSTODY_PERIOD: "custody",
    F.CHARGE_SHEET_FILED: "charge sheet",
    F.TRIAL_DELAY: "trial delay",
    F.PARITY_WITH_CO_ACCUSED: "parity",
    F.ANTECEDENTS: "antecedents",
    F.FLIGHT_RISK: "flight",
    F.WITNESS_TAMPERING: "witness",
    F.WEAK_PRIMA_FACIE: "prima facie",
    F.HEALTH_AGE_FAMILY: "health",
    F.STATUTORY_BAR: "statutory bar",
    F.UNDERTRIAL_PERIOD: "479",
}


def contracts_path() -> Path:
    return Path(__file__).resolve().parents[3] / "src" / "vakeel_sahayak" / "contracts" / "factors"


def read_contract_yaml(factor: Factor) -> dict:
    return yaml.safe_load((contracts_path() / f"{factor.value}.yaml").read_text(encoding="utf-8"))


def parse_contract(factor: Factor) -> EvidenceContract:
    """Parse directly with yaml + pydantic, independent of contracts.loader."""
    return EvidenceContract.model_validate(read_contract_yaml(factor))


def all_parsed() -> dict[Factor, EvidenceContract]:
    return {f: parse_contract(f) for f in Factor}
