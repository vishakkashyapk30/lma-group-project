"""scripts/check_consistency.py: the parsing behind the pre-registration and Rights checks, on synthetic text and files."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_consistency.py"
_spec = importlib.util.spec_from_file_location("check_consistency", _SCRIPT)
assert _spec and _spec.loader
cc = importlib.util.module_from_spec(_spec)
sys.modules["check_consistency"] = cc
_spec.loader.exec_module(cc)


@pytest.mark.parametrize("cell, vals, ns", [
    ("-0.237 [-0.450, -0.037], n 20", [(-0.237, -0.45, -0.037)], [20]),
    ("+0.017, +0.095 [+0.026, +0.162]", [(0.017, None, None), (0.095, 0.026, 0.162)], []),
    ("-0.306, -0.262 (n 6, 7)", [(-0.306, None, None), (-0.262, None, None)], [6, 7]),
    ("0.000, n 4", [(0.0, None, None)], [4]),
])
def test_cell_numbers(cell, vals, ns):
    assert cc._cell_numbers(cell) == (vals, ns)


def test_comparators():
    assert cc._comparators("B0, B1", set()) == ["b0", "b1"]
    assert cc._comparators("B0 to B3 (B6)", {"b0", "b1", "b2", "b3"}) == ["b0", "b1", "b2", "b3"]


def test_md_rows_reads_the_table_under_its_header():
    text = "intro\n| Id | Text today | x |\n|---|---|---|\n| H1 | a | b |\n| H2 | c | d |\n\nafter"
    assert cc.md_rows(text, "| Id | Text today") == (["Id", "Text today", "x"], [["H1", "a", "b"], ["H2", "c", "d"]])


def _dev(diff=-0.2375, lo=-0.45, hi=-0.0375, n=20):
    s = {"n": n, "full": 0.6, "comp": 0.8, "diff": diff, "lo": lo, "hi": hi}
    return {"v1": {"metrics": {"objection_recall": {"b4": s}}}}


def test_dev_evidence_matches_and_catches_a_wrong_number():
    prereg = "| Test | v1 (50 orders) |\n|---|---|\n| Objection recall vs B4 | -0.237 [-0.450, -0.037], n 20 |\n"
    good, bad = cc.Report(), cc.Report()
    cc.dev_evidence(good, prereg, _dev())
    cc.dev_evidence(bad, prereg, _dev(diff=-0.25))
    assert good.failed == 0 and bad.failed == 1
    wrong_n = cc.Report()
    cc.dev_evidence(wrong_n, prereg, _dev(n=19))
    assert wrong_n.failed == 1


def _rights(tmp_path, monkeypatch, matched: int, sentence: str):
    rights = tmp_path / "rights"
    rights.mkdir()
    rules = {f"r{i}": {"matched": i < matched} for i in range(7)}
    (rights / "rule_check.json").write_text(json.dumps({"rules": rules}))
    sections = tmp_path / "report" / "sections"
    sections.mkdir(parents=True)
    (sections / "x.tex").write_text(sentence)
    monkeypatch.setattr(cc, "RIGHTS", rights)
    monkeypatch.setattr(cc, "REPORT", tmp_path / "report")
    rep = cc.Report()
    cc.verification_counts(rep)
    return rep


@pytest.mark.parametrize("sentence, failed", [
    ("One of the seven rules is unverified.", 0),
    ("Six of the seven rules are unverified.", 1),
    ("Six of seven rules await a check.", 1),
    ("the rule texts match (six of the seven rules match).", 0),
    ("Rights rules (6 of 7 match) & done", 0),
    ("Rights rules (5 of 7 match) & done", 1),
    ("the scenarios cover six of the seven rules (grounds of arrest has none)", 0),
])
def test_verification_sentences_must_agree_with_the_rule_check(tmp_path, monkeypatch, sentence, failed):
    assert _rights(tmp_path, monkeypatch, 6, sentence).failed == failed
