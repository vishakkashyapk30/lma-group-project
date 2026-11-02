"""scripts/check_rights_rules.py on a synthetic statute store (no dependency on data/): citations, headings, conditions, quantities, yaml."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_rights_rules.py"
_spec = importlib.util.spec_from_file_location("check_rights_rules", _SCRIPT)
assert _spec and _spec.loader
crr = importlib.util.module_from_spec(_spec)
sys.modules["check_rights_rules"] = crr
_spec.loader.exec_module(crr)

S58 = ("Person arrested not to be detained more than twenty-four hours\n\n58. Person arrested not to be detained more than twenty-four hours.—"
       "No police officer shall detain ... exceed twenty-four hours exclusive of the time necessary for the journey from the place of arrest "
       "to the Magistrate’s Court.")
S59_UNDER_58 = ("Person arrested not to be detained more than twenty-four hours\n\n58. Person arrested not to be detained more than twenty-four "
                "hours .—Officers in charge of police stations shall report to the District Magistrate ...")
RULE = {"production_24h": {"rule": "Produce within 24 hours of arrest, excluding travel time", "sources": ["Art. 22(2)", "BNSS s.58"]}}
SPEC = {"production_24h": {"sections": {"BNSS s.58": {
    "heading": "Person arrested not to be detained more than twenty-four hours",
    "conditions": [{"says": "within 24 hours", "pattern": "exceed twenty-four hours"},
                   {"says": "excluding travel time", "pattern": "exclusive of the time necessary for the journey from the place of arrest to the magistrate's court"}]}}}}


def test_citations_found_in_rule_text_and_sources_and_the_rest_is_outside_the_store():
    cites, outside = crr.citations({"rule": "UAPA s.43D(2): 90 days; NDPS s.36A(4) for s.19", "sources": ["BNSS s.187(3) (CrPC s.167(2))", "Art. 22(1)", "M. Ravindran v. DRI (2020)"]})
    assert cites == {"UAPA s.43D": {"(2)"}, "NDPS s.36A": {"(4)"}, "BNSS s.187": {"(3)"}, "CrPC s.167": {"(2)"}}
    assert outside == ["Art. 22(1)", "M. Ravindran v. DRI (2020)"]


@pytest.mark.parametrize("text, heading", [
    (S58, "Person arrested not to be detained more than twenty-four hours"),
    ("57. Person arrested not to be detained more than twenty-four hours.—No police officer", "Person arrested not to be detained more than twenty-four hours"),
    ("37. Offences to be cognizable and non-bailable.—(1) Notwithstanding", "Offences to be cognizable and non-bailable"),
])
def test_heading_keeps_hyphens_and_stops_at_the_dash(text, heading):
    assert crr.heading_of(text) == heading


def test_the_correct_section_matches_and_the_wrong_body_does_not():
    good = crr.check_rules(RULE, SPEC, {("BNSS", "58"): S58})["production_24h"]
    assert good["matched"] and good["outside_store"] == ["Art. 22(2)"]
    bad = crr.check_rules(RULE, SPEC, {("BNSS", "58"): S59_UNDER_58})["production_24h"]
    assert not bad["matched"]
    assert any("does not state 'within 24 hours'" in p for p in bad["problems"])


def test_missing_section_missing_spec_and_wrong_heading_each_fail():
    assert crr.check_rules(RULE, SPEC, {})["production_24h"]["problems"] == ["BNSS s.58: not in the statute store", "rule text: '24 hours' ('twenty-four hours') is in none of the cited sections"]
    assert "no entry in configs/rights_statute_checks.yaml" in crr.check_rules(RULE, {}, {("BNSS", "58"): S58})["production_24h"]["problems"][0]
    wrong = S58.replace("Person arrested not to be detained more than twenty-four hours", "Police to report apprehensions", 1)
    assert "heading in the store" in crr.check_rules(RULE, SPEC, {("BNSS", "58"): wrong})["production_24h"]["problems"][0]


def test_a_cited_sub_section_must_be_in_the_text():
    rule = {"r": {"rule": "x", "sources": ["BNSS s.58(9)"]}}
    spec = {"r": {"sections": {"BNSS s.58": {"heading": SPEC["production_24h"]["sections"]["BNSS s.58"]["heading"]}}}}
    assert crr.check_rules(rule, spec, {("BNSS", "58"): S58})["r"]["problems"] == ["BNSS s.58: sub-section (9) is not in the store text"]


def test_quantities_need_their_word_form_or_a_cited_judgment():
    assert crr.quantity_problems("within 90 days", ["ninety days, where"]) == []
    assert crr.quantity_problems("within 60 days", ["ninety days"]) == ["rule text: '60 days' ('sixty days') is in none of the cited sections"]
    assert crr.quantity_problems(">=2 hours before (X)", [], {"2 hours": "X v. Y (2025)"}, ["X v. Y (2025)"]) == []
    assert "not among the rule's sources" in crr.quantity_problems(">=2 hours", [], {"2 hours": "X v. Y (2025)"}, [])[0]


def test_a_rule_with_no_statute_citation_is_never_verified():
    assert not crr.check_rules({"r": {"rule": "A: up to 7 years", "sources": ["Antil (2022)"]}}, {}, {})["r"]["matched"]


def test_yaml_update_touches_only_the_verification_keys():
    text = ("a_rule:\n  rule: \"x\"\n  last_verified: \"2026-10-27\"  # old\n  # no verified_hash: stale reason\n  params:\n    k: []\n"
            "b_rule:\n  rule: \"y\"\n  last_verified: null\n")
    results = {"a_rule": {"matched": False}, "b_rule": {"matched": True}}
    out = crr.update_rules_yaml(text, results, {"a_rule": "1111", "b_rule": "2222"}, "2026-11-02")
    data = yaml.safe_load(out)
    assert data["a_rule"] == {"rule": "x", "last_verified": None, "params": {"k": []}}
    assert data["b_rule"] == {"rule": "y", "last_verified": "2026-11-02", "verified_hash": 2222}
    assert "no verified_hash" not in out


def test_open_store_refuses_a_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        crr.open_store(tmp_path / "absent.sqlite")
    db = tmp_path / "s.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE statutes (code TEXT, section TEXT, text TEXT, max_punishment TEXT, bailable INTEGER, cognisable INTEGER)")
    con.execute("INSERT INTO statutes VALUES ('BNSS', '58', ?, NULL, NULL, NULL)", (S58,))
    con.commit()
    con.close()
    assert crr.open_store(db) == {("BNSS", "58"): S58}


def test_qa_section_replaces_only_the_marked_part():
    sec = crr.qa_section({"r": {"matched": False, "sections": [], "problems": ["p"], "outside_store": []}}, "2026-11-02", "store")
    doc = crr.replace_marked("intro\n\n" + crr.START + "\nold\n" + crr.END + "\ntail\n", sec)
    assert doc.startswith("intro") and doc.endswith("\ntail\n") and "old" not in doc and "- `r`\n  - p" in doc


def test_committed_spec_covers_every_rule_in_the_config():
    root = Path(__file__).resolve().parents[3]
    rules = yaml.safe_load((root / "configs/rights_rules.yaml").read_text(encoding="utf-8"))
    spec = yaml.safe_load((root / "configs/rights_statute_checks.yaml").read_text(encoding="utf-8"))
    for name, section in rules.items():
        cites, _ = crr.citations(section)
        assert set(cites) <= set((spec.get(name) or {}).get("sections") or {}), name
