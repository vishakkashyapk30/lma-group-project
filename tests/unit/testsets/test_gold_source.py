"""T1 gold source: the agreed gold (primary) and the rule-only gold (secondary) load from their folders, list the same ids, differ in hash, and the swap is idempotent."""

from __future__ import annotations

import json

import pytest

from tests.unit.testsets._helpers import read_rows, write_t1_inputs
from vakeel_sahayak.testsets.gold_source import (
    gold_hashes,
    gold_info,
    gold_info_for_cases,
    load_t1,
    resolve_source,
    swap_t1,
    t1_dir,
)
from vakeel_sahayak.testsets.t1_court_grounded import build_t1


@pytest.fixture()
def root(tmp_path):
    """<root>/t1 built with rule-only gold; <root>/t1_gold_candidate with the same cases and a changed G1 label."""
    parts, gold = write_t1_inputs(tmp_path)
    root = tmp_path / "testsets"
    build_t1(str(parts), str(gold), str(root / "t1"))
    cand = root / "t1_gold_candidate"
    cand.mkdir()
    for name in ("cases.jsonl", "dev.jsonl"):
        rows = read_rows(root / "t1" / name)
        for r in rows:
            r["gold"]["G1"] = {**r["gold"]["G1"], "labels": ["antecedents"], "status": "agreed", "gold_source": "agreed"}
        (cand / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return root


def test_source_values_and_env_override(monkeypatch):
    monkeypatch.delenv("VS_GOLD_SOURCE", raising=False)
    assert resolve_source() == "agreed" and resolve_source("rule") == "rule"
    monkeypatch.setenv("VS_GOLD_SOURCE", "rule")
    assert resolve_source() == "rule" and resolve_source("agreed") == "agreed"
    with pytest.raises(ValueError):
        resolve_source("both")


def test_both_sources_load_same_ids_different_hashes_and_manifest_records_source(root):
    ids_before = [c["case_id"] for c in read_rows(root / "t1" / "cases.jsonl")]
    blind_before = (root / "t1" / "manifest_blind.json").read_text()
    out = swap_t1("agreed", root)
    assert (root / "t1_rule_only" / "cases.jsonl").is_file()
    agreed, rule = load_t1("test", "agreed", root), load_t1("test", "rule", root)
    assert [c["case_id"] for c in agreed] == [c["case_id"] for c in rule] == ids_before
    assert agreed[0]["gold"]["G1"]["labels"] == ["antecedents"] and rule[0]["gold"]["G1"].get("status") != "agreed"
    assert gold_info("agreed", root)["gold_sha256"] != gold_info("rule", root)["gold_sha256"] and out["gold_sha256"] == gold_hashes(root / "t1")["gold_sha256"]
    for src, d in (("agreed", root / "t1"), ("rule", root / "t1_rule_only")):
        rec = json.loads((d / "manifest.json").read_text())["details"]["gold"]
        assert rec["source"] == src and rec["gold_sha256"] == gold_hashes(d)["gold_sha256"]
        assert gold_info_for_cases(d / "cases.jsonl")["gold_source"] == src
    assert (root / "t1" / "manifest_blind.json").read_text() == blind_before  # no id, no id hash changes
    assert load_t1("dev", "agreed", root) == [] and load_t1("dev", "rule", root) == []


def test_swap_is_idempotent_and_reversible(root):
    swap_t1("agreed", root)
    again = swap_t1("agreed", root)
    assert "nothing to do" in again["actions"][0]
    back = swap_t1("rule", root)  # the agreed gold is kept in t1_gold_candidate, so no backup is needed
    assert back["gold_sha256"] == gold_hashes(root / "t1_rule_only")["gold_sha256"]
    assert t1_dir("agreed", root) == root / "t1_gold_candidate" and t1_dir("rule", root) == root / "t1_rule_only"
    swap_t1("agreed", root)
    assert t1_dir("agreed", root) == root / "t1"


def test_swap_refuses_to_overwrite_an_unsaved_gold(root):
    swap_t1("agreed", root)
    (root / "t1" / "cases.jsonl").write_text((root / "t1" / "cases.jsonl").read_text() + "\n", encoding="utf-8")  # an edited gold stored nowhere else
    with pytest.raises(ValueError, match="backup"):
        swap_t1("rule", root)
    swap_t1("rule", root, backup=root / "t1_edited_backup")
    assert (root / "t1_edited_backup" / "cases.jsonl").is_file()


def test_run_manifest_records_gold(root, monkeypatch):
    from vakeel_sahayak.eval.runners.driver import _gold_manifest

    swap_t1("agreed", root)
    rec = _gold_manifest(str(root / "t1_rule_only" / "cases.jsonl"))
    assert rec["gold_source"] == "rule" and rec["gold_sha256"] == gold_hashes(root / "t1_rule_only")["gold_sha256"]
    assert _gold_manifest(str(root / "t2" / "driver_cases.jsonl")) == {"gold_source": None, "gold_sha256": None}
