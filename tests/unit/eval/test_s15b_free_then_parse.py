"""S15b (output_format='free_then_parse'): the structured-call layer lets the model write free text first; the default path is unchanged."""

from __future__ import annotations

import json

from pydantic import BaseModel

from vakeel_sahayak.eval.runners.systems import system_runner
from vakeel_sahayak.orchestration import structured_output as so
from vakeel_sahayak.orchestration.switches import IMPLEMENTED_VARIANTS, Switches, assert_variant_implemented


class Answer(BaseModel):
    value: int = 0


class FakeClient:
    """Records what it was asked and answers with chatter around a fenced JSON object."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def generate(self, prompt, max_tokens=1, temperature=0.0, json_schema=None):
        self.calls.append({"prompt": prompt, "json_schema": json_schema})
        return self.replies.pop(0)


def test_default_path_sends_the_schema_and_the_prompt_unchanged():
    c = FakeClient([json.dumps({"value": 3})])
    assert so.structured_call(c, "PROMPT", Answer).value == Answer(value=3)
    assert c.calls[0]["prompt"] == "PROMPT" and c.calls[0]["json_schema"] is not None and not so.free_then_parse_active()


def test_free_then_parse_drops_the_constraint_adds_the_note_and_parses_the_tail():
    c = FakeClient(["Let me think: the custody is long.\n```json\n{\"value\": 7}\n```"])
    with so.output_format("free_then_parse"):
        assert so.free_then_parse_active()
        out = so.structured_call(c, "PROMPT", Answer)
    assert out.value == Answer(value=7) and out.attempts == 1
    assert c.calls[0]["json_schema"] is None and c.calls[0]["prompt"] == "PROMPT" + so.FREE_NOTE
    assert not so.free_then_parse_active()  # the scope restored the default


def test_an_unparseable_free_reply_costs_a_repair_attempt():
    c = FakeClient(["no json here at all", json.dumps({"value": 1})])
    with so.output_format("free_then_parse"):
        out = so.structured_call(c, "PROMPT", Answer)
    assert out.attempts == 2 and out.repaired and c.calls[1]["json_schema"] is None and "PROMPT" in c.calls[1]["prompt"]


def test_other_formats_leave_the_layer_alone_and_scopes_nest():
    for mode in (None, "answer_only", "reasoning_first"):
        with so.output_format(mode):
            assert not so.free_then_parse_active()
    with so.output_format("free_then_parse"):
        with so.output_format(None):
            assert not so.free_then_parse_active()
        assert so.free_then_parse_active()


def test_the_registry_and_the_runner_know_s15b():
    assert "S15b" in IMPLEMENTED_VARIANTS
    assert_variant_implemented("S15b")
    runner, switches = system_runner("S15b")
    assert switches == Switches(output_format="free_then_parse") and callable(runner)
    seen = {}

    def inner(case, ctx):
        seen["free"] = so.free_then_parse_active()
        return {"brief": {}}

    from types import SimpleNamespace

    from vakeel_sahayak.eval.runners.systems import _in_free_format

    ctx = SimpleNamespace(case_id="c", log=None)
    assert _in_free_format(inner)({}, ctx) == {"brief": {}} and seen["free"] is True and not so.free_then_parse_active()
    assert ctx.eval_record["variant_signals"]["output_format"]["variant"] == "S15b"  # the record the driver saves carries the counters
    # Full and every other variant run outside the scope
    full_runner, full_switches = system_runner("full")
    assert full_switches.output_format == "answer_only"
