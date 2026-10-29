"""`last_verified` is bound to what was verified (design review 2026-10-27, item 7): a date counts only while `verified_hash`
matches the rule's yaml section and its code, so a change to either shows the rule as unverified again."""

from __future__ import annotations

import copy

import pytest

from vakeel_sahayak.config import load_config
from vakeel_sahayak.rights import verify_hash
from vakeel_sahayak.rights.engine import default_rules
from vakeel_sahayak.rights.verify_hash import effective_last_verified, rule_hash
from vakeel_sahayak.schemas.enums import RightsCheckName

RULES = [c.value for c in RightsCheckName]


@pytest.fixture()
def config():
    return copy.deepcopy(load_config().rights_rules)


@pytest.mark.parametrize("rule", RULES)
def test_hash_is_stable_and_ignores_the_verification_keys(config, rule):
    before = rule_hash(rule, config)
    config[rule]["last_verified"] = "2026-11-01"
    config[rule]["verified_hash"] = "anything"
    assert rule_hash(rule, config) == before and len(before) == 16


def test_a_date_with_the_matching_hash_counts(config):
    rule = "default_bail"
    section = {**config[rule], "last_verified": "2026-11-01", "verified_hash": rule_hash(rule, config)}
    assert effective_last_verified(rule, section, config) == "2026-11-01"


@pytest.mark.parametrize("hash_value", [None, "0000000000000000"])
def test_a_date_without_a_matching_hash_reads_unverified(config, hash_value):
    rule = "default_bail"
    section = {**config[rule], "last_verified": "2026-11-01"}
    if hash_value:
        section["verified_hash"] = hash_value
    assert effective_last_verified(rule, section, config) is None


def test_a_change_to_the_rule_text_clears_the_verification(config):
    rule = "notice_of_appearance"
    recorded = rule_hash(rule, config)
    config[rule]["rule"] = config[rule]["rule"] + " (edited)"
    section = {**config[rule], "last_verified": "2026-11-01", "verified_hash": recorded}
    assert effective_last_verified(rule, section, config) is None


def test_a_change_to_the_rule_code_clears_the_verification(config, monkeypatch):
    rule = "notice_of_appearance"
    recorded = rule_hash(rule, config)
    monkeypatch.setattr(verify_hash, "_module_source", lambda r: "changed code")
    section = {**config[rule], "last_verified": "2026-11-01", "verified_hash": recorded}
    assert effective_last_verified(rule, section, config) is None


def test_engine_applies_the_binding_to_every_rule():
    config = load_config().rights_rules
    for rule in default_rules():
        section = config.get(rule.rule_id.value) or {}
        assert rule.last_verified == effective_last_verified(rule.rule_id.value, section, config)


def test_main_prints_one_line_per_rule(capsys):
    assert verify_hash.main([]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert [ln.split("\t")[0] for ln in lines] == RULES
