"""Model-assisted rescue of unclean order splits (plan §19): opt-in, labeler facade only, verbatim spans, offline keeps the rule decision."""

from __future__ import annotations

import json

import pytest

from vakeel_sahayak.models.base import LLMClient
from vakeel_sahayak.models.labeler import EvalLabeler
from vakeel_sahayak.pipelines.order_splitter import (
    analyse_split,
    rescue_dropped,
    rescue_split,
    rescue_with_non_qwen,
    split_all,
)
from vakeel_sahayak.pipelines.text_utils import read_jsonl, write_jsonl

# No cue phrase anywhere, so the rules cannot split it.
BLOCKS = [
    "1. The applicant is accused of cheating the complainant of a large sum of money in the year 2024 at the market.",
    "2. The applicant says he is innocent and was falsely named by the complainant in the first information report filed.",
    "3. The State says the offence is grave and the investigation has found his role in the transaction with the victim.",
    "4. The charge sheet is already filed, custody is no longer needed, and the trial will take a long time to conclude here.",
    "5. Bail is given on a bond of fifty thousand rupees with one surety and the passport shall be handed to the court.",
]
ORDER = "\n".join(BLOCKS)


class FakeClient(LLMClient):
    name = "fake-labeler"
    model_id = "gpt-fake"

    def __init__(self, parts: list[str]) -> None:
        self.parts = parts
        self.calls = 0

    def count_tokens(self, text):
        return len(text.split())

    def generate(self, prompt, max_tokens=1024, temperature=0.0, json_schema=None):
        self.calls += 1
        return json.dumps({"parts": self.parts})


GOOD = ["facts", "defense_submissions", "prosecution_submissions", "reasoning", "operative_order"]


def test_rules_fail_then_rescue_gives_verbatim_parts():
    assert not analyse_split(ORDER).clean
    res = rescue_split(ORDER, EvalLabeler(llm=FakeClient(GOOD)))
    assert res is not None and res.clean
    for part, text in res.parts.items():
        assert text in ORDER or all(b in ORDER for b in text.split("\n\n")), part
    assert res.parts[next(iter(res.parts))].startswith("1. The applicant")


@pytest.mark.parametrize("bad", [["facts"] * 5, ["facts", "defense_submissions", "prosecution_submissions", "operative_order", "reasoning"], ["facts", "x", "a", "b", "c"], ["facts"]])
def test_bad_answers_keep_the_rule_decision(bad):
    assert rescue_split(ORDER, EvalLabeler(llm=FakeClient(bad))) is None


def test_offline_default_is_unavailable_and_rescues_nothing(tmp_path, monkeypatch):
    from vakeel_sahayak.pipelines.text_utils import read_jsonl as rj
    monkeypatch.setenv("VS_MODELS", "offline")
    dropped = tmp_path / "d.jsonl"
    write_jsonl(dropped, [{"doc_id": "a", "text": ORDER, "reasons": ["missing:facts"]}])
    assert rescue_with_non_qwen(str(dropped)) == 0
    assert list(rj(str(dropped) + ".rescued.jsonl")) == []


def test_rescue_file_round_trip(tmp_path):
    orders = tmp_path / "o.jsonl"
    write_jsonl(orders, [{"doc_id": "a", "text": ORDER}])
    kept, dropped = split_all(str(orders), str(tmp_path / "k.jsonl"))
    assert (kept, dropped) == (0, 1)  # default behaviour unchanged
    rep = rescue_dropped(str(tmp_path / "k.jsonl.dropped.jsonl"), str(tmp_path / "r.jsonl"), EvalLabeler(llm=FakeClient(GOOD)))
    assert rep.rescued == 1 and rep.rescued_ids == ["a"]
    rec = list(read_jsonl(tmp_path / "r.jsonl"))[0]
    assert rec["rescued_by"] == "non-qwen-labeler" and rec["spans"]["facts"][0] in ORDER


def test_qwen_labeler_is_refused():
    with pytest.raises(ValueError):
        EvalLabeler(model="Qwen/Qwen3-32B", backend="openai").client()
