"""orchestration/structured_output.constrained_generate (plan §3.3 'Well-formed calls').

Plans and tool calls are generated with JSON-schema-constrained decoding so every call parses: the client receives the
pydantic JSON schema (its title is the class name, which ScriptedLLM dispatches on), the output is validated into the
model, and invalid output raises after the configured retries.
"""

from __future__ import annotations

import inspect
import json

import pytest

from tests.fakes.models import ScriptedLLM, Seq
from vakeel_sahayak.orchestration.structured_output import constrained_generate
from vakeel_sahayak.schemas.enums import Factor
from vakeel_sahayak.schemas.retrieval_plan import BudgetLeft, PlanStep, RetrievalPlan

PLAN = RetrievalPlan(
    factor=Factor.PARITY_WITH_CO_ACCUSED,
    round=1,
    budget_left=BudgetLeft(store_calls=6, tokens=9000),
    steps=[PlanStep(slot="authority", tool="search_reasoning", args={"factor": "parity_with_co_accused", "k": 10})],
)
# ASSUMPTION: one retry after an invalid completion, so at most two LLM calls.
MAX_CALLS = 2


def test_signature():
    """constrained_generate(client, prompt, schema, max_tokens=2048)."""
    sig = inspect.signature(constrained_generate)
    assert list(sig.parameters) == ["client", "prompt", "schema", "max_tokens"]
    assert sig.parameters["max_tokens"].default == 2048


def test_returns_validated_model_instance():
    """A valid JSON completion becomes an instance of the requested model with all fields intact."""
    llm = ScriptedLLM(by_schema={"RetrievalPlan": PLAN})
    out = constrained_generate(llm, "plan parity", RetrievalPlan)
    assert isinstance(out, RetrievalPlan)
    assert out == PLAN
    assert out.factor is Factor.PARITY_WITH_CO_ACCUSED
    assert out.steps[0].args["k"] == 10


@pytest.mark.parametrize(
    "model,value",
    [
        (RetrievalPlan, PLAN),
        (PlanStep, PlanStep(slot="s1", tool="date_calc", args={"from": "2024-08-20"})),
        (BudgetLeft, BudgetLeft(store_calls=0, tokens=0)),
    ],
)
def test_passes_pydantic_json_schema_with_title_to_client(model, value):
    """The client gets json_schema == model.model_json_schema(), whose title is the class name."""
    llm = ScriptedLLM(by_schema={model.__name__: value})
    constrained_generate(llm, "go", model)
    call = llm.calls[0]
    assert call.json_schema == model.model_json_schema()
    assert call.schema_title == model.__name__
    assert call.json_schema["title"] == model.__name__


def test_prompt_and_max_tokens_reach_the_client():
    """The caller's prompt is sent as is on the first call and max_tokens is forwarded."""
    llm = ScriptedLLM(by_schema={"RetrievalPlan": PLAN})
    constrained_generate(llm, "UNIQUE-PROMPT-TEXT", RetrievalPlan, max_tokens=321)
    assert "UNIQUE-PROMPT-TEXT" in llm.calls[0].prompt
    assert llm.calls[0].max_tokens == 321


def test_valid_first_try_makes_exactly_one_call():
    """No retry when the first completion validates."""
    llm = ScriptedLLM(by_schema={"RetrievalPlan": PLAN})
    constrained_generate(llm, "p", RetrievalPlan)
    assert len(llm.calls) == 1


def test_one_retry_recovers_from_invalid_json():
    """Garbage on the first call and valid JSON on the second returns the model after exactly two calls."""
    llm = ScriptedLLM(by_schema={"RetrievalPlan": Seq("this is not json {", PLAN)})
    out = constrained_generate(llm, "p", RetrievalPlan)
    assert out == PLAN
    assert len(llm.calls) == 2
    assert all(c.json_schema["title"] == "RetrievalPlan" for c in llm.calls), "the retry stays constrained"


def test_one_retry_recovers_from_schema_violation():
    """Syntactically valid JSON that violates the schema (missing required field) is retried too."""
    invalid = json.dumps({"round": 1})  # no factor, no budget_left
    llm = ScriptedLLM(by_schema={"RetrievalPlan": Seq(invalid, PLAN)})
    assert constrained_generate(llm, "p", RetrievalPlan) == PLAN
    assert len(llm.calls) == 2


def test_raises_on_invalid_json_after_retries():
    """Persistently invalid JSON raises a ValueError (JSONDecodeError / ValidationError) after the retry, not later."""
    llm = ScriptedLLM(by_schema={"RetrievalPlan": "not json at all"})
    with pytest.raises(ValueError):
        constrained_generate(llm, "p", RetrievalPlan)
    assert 1 <= len(llm.calls) <= MAX_CALLS


def test_exactly_one_retry_is_made_before_raising():
    """After the first failure there is exactly one more attempt (two calls in total)."""
    llm = ScriptedLLM(by_schema={"RetrievalPlan": "{"})
    with pytest.raises(ValueError):
        constrained_generate(llm, "p", RetrievalPlan)
    assert len(llm.calls) == MAX_CALLS


def test_raises_on_wrong_type_even_if_json_is_well_formed():
    """Well-formed JSON of the wrong shape (a list, or an enum value outside Factor) is rejected."""
    for bad in ('["a", "b"]', json.dumps({"factor": "not_a_factor", "budget_left": {"store_calls": 1, "tokens": 1}})):
        llm = ScriptedLLM(by_schema={"RetrievalPlan": bad})
        with pytest.raises(ValueError):
            constrained_generate(llm, "p", RetrievalPlan)
