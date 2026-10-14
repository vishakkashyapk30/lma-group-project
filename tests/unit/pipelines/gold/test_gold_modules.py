"""Gold modules G1-G7 (plan §15.1 table): which part of the order each gold label is read from, and how it is labelled.

| G1 defense factors   | defense submissions | keyword rules + Llama, agreed only |
| G2 cited precedents  | reasoning           | citation regexes resolved to OIL   |
| G3 dossier fields    | whole order         | regex rules and Llama agree        |
| G4 prosecution       | prosecution subs.   | keyword rules + Llama, agreed only |
| G5 court factors     | reasoning           | keyword rules + Llama, agreed only |
| G6 conditions        | operative order     | regexes + Llama, agreed only       |
| G7 rights            | reasoning           | keywords + Llama, agreed only      |
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

from vakeel_sahayak.models.labeler import EvalLabeler
from vakeel_sahayak.schemas.enums import Factor, OrderPart

MODULES = {
    "g1": "vakeel_sahayak.pipelines.gold.g1_defense_factors",
    "g2": "vakeel_sahayak.pipelines.gold.g2_cited_precedents",
    "g3": "vakeel_sahayak.pipelines.gold.g3_dossier_fields",
    "g4": "vakeel_sahayak.pipelines.gold.g4_prosecution_objections",
    "g5": "vakeel_sahayak.pipelines.gold.g5_court_factors",
    "g6": "vakeel_sahayak.pipelines.gold.g6_conditions",
    "g7": "vakeel_sahayak.pipelines.gold.g7_rights_computations",
}

# gold -> phrases that the module docstring must contain (the declared gold source of plan §15.1)
DECLARED_SOURCE = {
    "g1": ["G1", "defense submissions"],
    "g2": ["G2", "reasoning", "resolvable"],
    "g3": ["G3", "whole order"],
    "g4": ["G4", "prosecution submissions"],
    "g5": ["G5", "reasoning"],
    "g6": ["G6", "operative order"],
    "g7": ["G7", "reasoning", "167(2)", "187(3)", "default bail", "436A", "479"],
}


@pytest.mark.parametrize("gold", sorted(MODULES))
def test_module_declares_its_gold_source(gold):
    """Each gold module's docstring names its gold and the order part it reads (plan §15.1 table)."""
    doc = importlib.import_module(MODULES[gold]).__doc__
    for phrase in DECLARED_SOURCE[gold]:
        assert phrase.lower() in doc.lower(), f"{gold}: docstring should mention {phrase!r}"


@pytest.mark.parametrize("gold", sorted(MODULES))
def test_module_has_the_gold_interface(gold):
    """Every gold module offers build_gold(parts_path, out_path) -> int and label_order(parts) -> dict."""
    mod = importlib.import_module(MODULES[gold])
    assert list(inspect.signature(mod.build_gold).parameters) == ["parts_path", "out_path"]
    assert list(inspect.signature(mod.label_order).parameters) == ["parts"]


def test_g6_declares_ten_condition_types_in_docstring():
    """G6 is 'a fixed list of about 10 types': passport, travel, reporting, personal bond, no contact with witnesses."""
    doc = importlib.import_module(MODULES["g6"]).__doc__.lower()
    for word in ("passport", "travel", "reporting", "personal bond", "witnesses"):
        assert word in doc


def test_gold_modules_never_import_qwen_or_system_model_clients():
    """Plan §15.1 'No Qwen gold': gold modules must not import the teacher, local LLM, vLLM client or the factory's LLM."""
    forbidden = {"vakeel_sahayak.models.teacher", "vakeel_sahayak.models.local_llm", "vakeel_sahayak.models.vllm_client",
                 "vakeel_sahayak.models.factory", "vllm"}
    root = Path(inspect.getfile(importlib.import_module("vakeel_sahayak.pipelines.gold"))).parent
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            assert not forbidden & set(names), f"{path.name} imports {forbidden & set(names)}"


# ---- label_order with a fake labeler: only agreed labels survive ---------------------------------------------------
def flatten(value) -> list[str]:
    """All string leaves of a nested record (enum members by value)."""
    out: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            out += flatten(k) + flatten(v)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            out += flatten(v)
    elif hasattr(value, "value") and isinstance(getattr(value, "value"), str):
        out.append(value.value)
    elif isinstance(value, str):
        out.append(value)
    return out


class OverEagerLabeler:
    """Fake Llama that returns the whole label set for any text and records the label sets it was given."""

    def __init__(self) -> None:
        self.label_sets: list[list[str]] = []
        self.texts: list[str] = []

    def install(self, monkeypatch) -> "OverEagerLabeler":
        outer = self

        def label(self, text, label_set):
            outer.label_sets.append(list(label_set))
            outer.texts.append(text)
            return list(label_set)

        monkeypatch.setattr(EvalLabeler, "label", label)
        return self


FACTOR_IDS = {f.value for f in Factor}

PARTS = {
    OrderPart.FACTS: "The applicant was arrested on 20.08.2024 in FIR No. 112/2024 and remains in custody.",
    OrderPart.DEFENSE: ("Learned counsel for the petitioner submits that the applicant has no criminal antecedents and is "
                        "not a flight risk."),
    OrderPart.PROSECUTION: ("Learned APP submits that the applicant may tamper with witnesses and that the co-accused "
                            "is absconding."),
    OrderPart.REASONING: ("Heard and perused the record. The charge sheet has been filed and the trial is likely to take long. "
                          "The applicant has undergone the period contemplated in Section 479 BNSS and default bail under "
                          "Section 167(2) CrPC was not claimed."),
    OrderPart.OPERATIVE: ("Accordingly, the bail application is allowed. The applicant shall surrender his passport, shall not "
                          "leave the country without permission and shall furnish a personal bond of Rs. 50,000."),
}


@pytest.mark.parametrize(
    ("gold", "part", "expected", "forbidden"),
    [
        # G1 reads the defense part only: antecedents and flight risk are there; witness tampering is only in the prosecution part
        ("g1", OrderPart.DEFENSE, {"antecedents", "flight_risk"}, {"witness_tampering", "parity_with_co_accused", "charge_sheet_filed"}),
        # G4 reads the prosecution part only
        ("g4", OrderPart.PROSECUTION, {"witness_tampering", "parity_with_co_accused"}, {"antecedents", "flight_risk", "charge_sheet_filed"}),
        # G5 reads the reasoning only
        ("g5", OrderPart.REASONING, {"charge_sheet_filed", "trial_delay", "undertrial_period"}, {"antecedents", "witness_tampering", "flight_risk"}),
    ],
)
def test_factor_golds_keep_only_rule_labels_from_their_own_part(monkeypatch, gold, part, expected, forbidden):
    """G1, G4, G5: even if the LLM claims every factor, only factors the keyword rules also find in the right part are kept."""
    fake = OverEagerLabeler().install(monkeypatch)
    record = importlib.import_module(MODULES[gold]).label_order(PARTS)
    kept = {s for s in flatten(record) if s in FACTOR_IDS}
    assert expected <= kept, f"{gold} should keep {expected}, kept {kept}"
    assert not (forbidden & kept), f"{gold} must not keep {forbidden & kept}"
    assert fake.label_sets, "the LLM labeler is consulted (rules alone are not gold)"
    assert all(set(ls) == FACTOR_IDS for ls in fake.label_sets), "ASSUMPTION: the factor label set is the 12 Appendix A ids"
    assert all(t == PARTS[part] for t in fake.texts), f"{gold} must label the {part.value} part only"


def test_g1_drops_a_factor_only_the_llm_claims(monkeypatch):
    """A factor the LLM claims but the rules do not see (health_age_family) is not in G1."""

    def label(self, text, label_set):
        return ["antecedents", "health_age_family"]

    monkeypatch.setattr(EvalLabeler, "label", label)
    record = importlib.import_module(MODULES["g1"]).label_order(PARTS)
    kept = {s for s in flatten(record) if s in FACTOR_IDS}
    assert kept == {"antecedents"}


def test_g1_drops_a_factor_only_the_rules_find(monkeypatch):
    """A factor the rules find but the LLM does not (flight_risk) is not in G1 either: agreed labels only."""

    def label(self, text, label_set):
        return ["antecedents"]

    monkeypatch.setattr(EvalLabeler, "label", label)
    kept = {s for s in flatten(importlib.import_module(MODULES["g1"]).label_order(PARTS)) if s in FACTOR_IDS}
    assert kept == {"antecedents"}


def test_g6_keeps_only_conditions_both_methods_find(monkeypatch):
    """G6 reads the operative order: passport and personal bond are there, 'reporting' and 'witness' conditions are not."""
    fake = OverEagerLabeler().install(monkeypatch)
    record = importlib.import_module(MODULES["g6"]).label_order(PARTS)
    label_set = fake.label_sets[0]
    assert 8 <= len(label_set) <= 12, "ASSUMPTION: 'about 10' condition types"
    kept = [s for s in flatten(record) if s in label_set]
    assert any("passport" in s for s in kept) and any("bond" in s for s in kept)
    assert not any("witness" in s or "report" in s for s in kept)
    assert fake.texts == [PARTS[OrderPart.OPERATIVE]]


def test_g7_has_no_labels_without_a_rights_keyword(monkeypatch):
    """G7: reasoning that never mentions 167(2), 187(3), default bail, 436A or 479 yields no rights label."""
    fake = OverEagerLabeler().install(monkeypatch)
    parts = dict(PARTS)
    parts[OrderPart.REASONING] = "Heard and perused the record. The applicant has no antecedents."
    record = importlib.import_module(MODULES["g7"]).label_order(parts)
    label_set = fake.label_sets[0] if fake.label_sets else []
    assert not [s for s in flatten(record) if s in label_set]


def test_g7_keeps_a_label_when_a_rights_keyword_is_present(monkeypatch):
    """G7: reasoning that states Section 479 BNSS and default bail under 167(2) yields at least one label."""
    fake = OverEagerLabeler().install(monkeypatch)
    record = importlib.import_module(MODULES["g7"]).label_order(PARTS)
    assert fake.label_sets
    assert [s for s in flatten(record) if s in fake.label_sets[0]]
    assert fake.texts == [PARTS[OrderPart.REASONING]]
