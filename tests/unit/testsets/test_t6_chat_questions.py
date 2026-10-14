"""T6 chat questions (plan §15.2, §6.4, §15.8): about 150 templated questions over T1 and T2 cases, including routing questions. Answers
come from G3, the timeline and the concordance, so tool-calling accuracy and valid arguments are measured without labels.

# ASSUMPTION: out_dir/questions.jsonl rows {"qid", "case_id", "question", "expected_answer", "answer_source": "G3" | "timeline" |
#   "concordance" | None, "expected_tools": [<tool names>], "kind": "fact" | "routing"}.
"""

from __future__ import annotations

import collections

import pytest

from tests.unit.testsets._helpers import assert_manifest, read_manifest, read_rows, write_t1_dir, write_t2_dir
from tests.unit.tools._helpers import PLAN_TOOL_NAMES
from vakeel_sahayak.testsets.t6_chat_questions import build_t6


@pytest.fixture()
def built(tmp_path):
    t1 = write_t1_dir(tmp_path)
    t2 = write_t2_dir(tmp_path, t1, 20)
    out = tmp_path / "t6"
    m = build_t6(str(t1), str(t2), str(out))
    return m, read_rows(out / "questions.jsonl"), out


def test_about_150_questions(built):
    m, rows, out = built
    assert_manifest(m, "T6")
    assert 140 <= m.size <= 160 and m.size == len(rows)
    assert "tool" in " ".join(m.used_for).lower()
    assert read_manifest(out)["size"] == len(rows)


def test_answers_come_from_g3_the_timeline_and_the_concordance(built):
    _, rows, _ = built
    sources = collections.Counter(r["answer_source"] for r in rows if r["kind"] == "fact")
    assert set(sources) == {"G3", "timeline", "concordance"}


def test_expected_tools_are_real_tools(built):
    """Tool-call accuracy compares names: every expected tool is one of the 39 plan tools."""
    _, rows, _ = built
    for r in rows:
        assert set(r["expected_tools"]) <= set(PLAN_TOOL_NAMES), r


@pytest.mark.parametrize(
    ("needle", "tool"),
    [("days in custody", "date_calc"), ("BNS equivalent", "map_section"), ("s.479", "rights_check"),
     ("parity", "search_reasoning"), ("State oppose", "search_objections")],
)
def test_the_routing_table_of_plan_6_4_is_covered(built, needle, tool):
    """Plan §6.4: custody -> timeline + date_calc; BNS equivalent -> map_section; s.479 -> Rights Radar; SC case on parity ->
    caselaw; State's opposition -> advocacy.objections. Routing questions exist for each route."""
    _, rows, _ = built
    routed = [r for r in rows if r["kind"] == "routing" and needle.lower() in r["question"].lower()]
    assert routed, needle
    assert all(tool in r["expected_tools"] for r in routed)


def test_ipc_420_maps_to_bns_318_4(built):
    """The concordance question of plan §6.4 has the known answer."""
    _, rows, _ = built
    q = next(r for r in rows if r["answer_source"] == "concordance" and "420" in r["question"])
    assert "318(4)" in q["expected_answer"] and q["expected_tools"] == ["map_section"]


def test_a_g3_question_has_the_case_value_as_its_answer(built):
    """A question about the arrest date has that case's G3 arrest date as the expected answer (either date format)."""
    _, rows, _ = built
    q = next(r for r in rows if r["answer_source"] == "G3" and "arrest" in r["question"].lower())
    assert any(form in q["expected_answer"] for form in ("2024-08-20", "20.08.2024"))


def test_questions_span_t1_and_t2_cases(built):
    _, rows, _ = built
    assert any(r["case_id"].startswith("t1-") for r in rows)
    assert len({r["case_id"] for r in rows}) > 10


def test_question_texts_are_unique_per_case(built):
    _, rows, _ = built
    keys = [(r["case_id"], r["question"]) for r in rows]
    assert len(keys) == len(set(keys))


def test_build_is_deterministic(tmp_path):
    t1 = write_t1_dir(tmp_path)
    t2 = write_t2_dir(tmp_path, t1, 20)
    build_t6(str(t1), str(t2), str(tmp_path / "a"))
    build_t6(str(t1), str(t2), str(tmp_path / "b"))
    assert (tmp_path / "a" / "questions.jsonl").read_bytes() == (tmp_path / "b" / "questions.jsonl").read_bytes()
