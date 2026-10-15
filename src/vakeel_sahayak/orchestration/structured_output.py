"""Schema-constrained decoding helper for plans and tool calls (plan §3.3).

Every plan, tool call and structured draft is generated against a JSON schema (vLLM structured outputs on Ada, so every
call parses), then validated here: JSON is extracted from the reply (code fences, a stray `<think>` block and chatter
are tolerated), checked against the schema (pydantic validation for model classes, `models.json_schema.validate` for
dict schemas), and on failure the prompt is re-sent with a REPAIR note listing the problems, up to `retries` times.
Tools still validate argument values (plan §3.3); this layer only guarantees shape.

`structured_call` returns the value with its token counts and attempt count; `constrained_generate` returns the value.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from vakeel_sahayak.models.base import LLMClient, approx_tokens, strip_thinking
from vakeel_sahayak.models.json_schema import schema_of, validate
from vakeel_sahayak.models.prompting import add_repair

_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


class StructuredOutputError(ValueError):
    """No valid reply after every repair attempt.

    Attributes:
        attempts: how many generations were tried
        errors: the problems with the last reply
        last_raw: the last reply (may be long)
    """

    def __init__(self, message: str, attempts: int, errors: list[str], last_raw: str) -> None:
        """Keep the diagnostics."""
        super().__init__(message)
        self.attempts = attempts
        self.errors = errors
        self.last_raw = last_raw


@dataclass
class StructuredResult:
    """A validated structured reply with its cost."""

    value: Any
    raw: str
    attempts: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    errors: list[list[str]] = field(default_factory=list)  # problems of each failed attempt

    @property
    def total_tokens(self) -> int:
        """Prompt plus completion tokens over all attempts."""
        return self.prompt_tokens + self.completion_tokens

    @property
    def repaired(self) -> bool:
        """True when the first reply failed and a repair succeeded."""
        return self.attempts > 1


def _trailing_commas(text: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", text)


def extract_json(text: str) -> Any:
    """Decode the JSON value in a model reply.

    Tries, in order: the whole reply; the contents of code fences; the first balanced object or array (raw_decode from
    each '{' or '['); each of those again with trailing commas removed.

    Args:
        text: the reply

    Returns:
        The decoded value.

    Raises:
        ValueError: when no JSON value can be found.
    """
    text = strip_thinking(text or "").strip()
    candidates = [text, *(m.group(1).strip() for m in _FENCE.finditer(text))]
    for cand in candidates:
        for variant in (cand, _trailing_commas(cand)):
            try:
                return json.loads(variant)
            except ValueError:
                pass
    decoder = json.JSONDecoder()
    for variant in (text, _trailing_commas(text)):
        for i, ch in enumerate(variant):
            if ch in "{[":
                try:
                    value, _ = decoder.raw_decode(variant, i)
                    return value
                except ValueError:
                    continue
    raise ValueError("no JSON value found in the reply")


def _is_model(schema: Any) -> bool:
    return isinstance(schema, type) and issubclass(schema, BaseModel)


def validate_output(value: Any, schema: Any) -> tuple[Any, list[str]]:
    """Validate a decoded value.

    Args:
        value: the decoded JSON
        schema: pydantic model class or JSON-schema dict

    Returns:
        (validated value, problems); problems is empty on success (the value is then a model instance for model schemas).
    """
    if _is_model(schema):
        try:
            return schema.model_validate(value), []
        except ValidationError as exc:
            return None, [f"{'.'.join(map(str, e['loc'])) or '$'}: {e['msg']}" for e in exc.errors()[:12]]
    problems = validate(value, schema_of(schema))
    return (value if not problems else None), problems


def _count(client: Any, text: str) -> int:
    try:
        return int(client.count_tokens(text))
    except Exception:  # noqa: BLE001 - a fake or broken tokenizer must not break the call
        return approx_tokens(text)


def structured_call(
    client: LLMClient,
    prompt: str,
    schema: Any,
    *,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    retries: int = 2,
) -> StructuredResult:
    """Generate, validate and repair until the reply fits the schema.

    Args:
        client: any LLMClient (or an object with the same `generate`)
        prompt: the full prompt (ideally in the `models.prompting` layout)
        schema: pydantic model class or JSON-schema dict
        max_tokens: completion limit per attempt
        temperature: sampling temperature (0.0: deterministic)
        retries: repair attempts after the first try

    Returns:
        StructuredResult.

    Raises:
        StructuredOutputError: no valid reply after `retries` repairs.
        ModelUnavailable: the backend cannot run (propagated; callers decide how to degrade).
    """
    json_schema = schema_of(schema)
    attempt_prompt = prompt
    errors: list[list[str]] = []
    raw = ""
    p_tok = c_tok = 0
    for attempt in range(1, retries + 2):
        if hasattr(client, "complete"):
            done = client.complete(attempt_prompt, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)
            raw, p_tok, c_tok = done.text, p_tok + done.prompt_tokens, c_tok + done.completion_tokens
        else:
            raw = client.generate(attempt_prompt, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)
            p_tok, c_tok = p_tok + _count(client, attempt_prompt), c_tok + _count(client, raw)
        try:
            decoded = extract_json(raw)
        except ValueError as exc:
            problems = [str(exc)]
        else:
            value, problems = validate_output(decoded, schema)
            if not problems:
                return StructuredResult(value=value, raw=raw, attempts=attempt, prompt_tokens=p_tok, completion_tokens=c_tok, errors=errors)
        errors.append(problems)
        attempt_prompt = add_repair(prompt, problems, raw)
    raise StructuredOutputError(
        f"no schema-valid reply after {retries + 1} attempts: {'; '.join(errors[-1][:4])}", retries + 1, errors[-1], raw
    )


def constrained_generate(
    client: LLMClient,
    prompt: str,
    schema: type[BaseModel] | dict,
    max_tokens: int = 2048,
    *,
    temperature: float = 0.0,
    retries: int = 2,
) -> Any:
    """Generate a plan or tool call with JSON-schema-constrained decoding (vLLM structured outputs) so every call parses; tools still validate argument values (plan §3.3).

    Args:
        client: see behaviour
        prompt: see behaviour
        schema: JSON schema to enforce: a pydantic model class (returns an instance) or a JSON-schema dict (returns the JSON value)
        max_tokens: see behaviour
        temperature: sampling temperature
        retries: repair attempts after the first try

    Returns:
        A validated model instance.
    """
    return structured_call(client, prompt, schema, max_tokens=max_tokens, temperature=temperature, retries=retries).value
