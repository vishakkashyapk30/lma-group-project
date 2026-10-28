"""Wire formats of the two hosted protocols: request bodies, replies, errors and the 400-driven mode changes.

- `openai_compat`: `POST <base_url><chat_path>` (default `/chat/completions`) with `messages`, `max_tokens` (or `max_completion_tokens`),
  `temperature`, `response_format` (`json_schema` non-strict, or `json_object`). Covers OpenRouter, Groq, Together, Mistral, a local vLLM,
  and Gemini's own OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai`).
- `gemini_native`: `POST <base_url>/<api_version>/models/<model>:generateContent` with `contents` (roles user/model), `systemInstruction`,
  `generationConfig` (`maxOutputTokens`, `temperature`, `responseMimeType: application/json`, `responseSchema` in Gemini's OpenAPI subset,
  `thinkingConfig`). Reply: `candidates[0].content.parts[].text` (parts marked `thought` are skipped), `usageMetadata`, `modelVersion`.
  Errors: `{"error": {"code", "message", "status", "details": [QuotaFailure{violations[].quotaId}, RetryInfo{retryDelay}]}}`.

**Modes** (what a model accepts): `system` = 'system' (a system instruction) or 'fold' (the system text is put at the top of the first user turn,
for models such as Gemma on the Gemini API that refuse system instructions); `structured` = 'schema' (the provider constrains the JSON to the
schema), 'json_mode' (JSON output only; the schema is also written into the prompt) or 'prompt' (the schema is only in the prompt); `thinking`
= 'on' (the configured thinking/reasoning options are sent) or 'off'. A 400 naming one of these features moves to the next weaker mode
(`adapt`); the caller's validation and repair loop (`orchestration.structured_output`) checks the JSON in every mode.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, replace
from email.utils import parsedate_to_datetime
from typing import Any

from vakeel_sahayak.models.hosted.errors import HostedError

STRUCTURED_ORDER = ("schema", "json_mode", "prompt")


@dataclass(frozen=True)
class Modes:
    """The request features in use (see the module doc)."""

    system: str = "system"
    structured: str = "schema"
    thinking: str = "on"

    @property
    def label(self) -> str:
        """Short form for the ledger and the manifest, e.g. 'system+schema', 'fold+prompt'."""
        return f"{self.system}+{self.structured}" + ("" if self.thinking == "on" else "+nothink")


@dataclass(frozen=True)
class Reply:
    """A parsed answer."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    finish: str | None = None
    served_model: str | None = None


def schema_prompt(schema: dict[str, Any]) -> str:
    """The instruction that carries the schema in the prompt (json_mode and prompt modes)."""
    return "Reply with one JSON object and nothing else. It must follow this JSON schema:\n" + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))


def _split_system(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    system = "\n\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "system")
    return system, [m for m in messages if m.get("role") != "system"]


def prepare_messages(messages: list[dict[str, str]], modes: Modes, json_schema: dict | None) -> list[dict[str, str]]:
    """Apply the system and structured modes to a message list (protocol-neutral): fold the system text, add the schema instruction."""
    msgs = [dict(m) for m in messages]
    if json_schema is not None and modes.structured in ("json_mode", "prompt"):
        if msgs and msgs[-1].get("role") == "user":
            msgs[-1]["content"] = str(msgs[-1].get("content", "")) + "\n\n" + schema_prompt(json_schema)
        else:
            msgs.append({"role": "user", "content": schema_prompt(json_schema)})
    if modes.system == "fold":
        system, rest = _split_system(msgs)
        if system:
            if rest and rest[0].get("role") == "user":
                rest[0] = {**rest[0], "content": f"Instructions:\n{system}\n\n{rest[0].get('content', '')}"}
            else:
                rest.insert(0, {"role": "user", "content": f"Instructions:\n{system}"})
        msgs = rest
    return msgs


# ------------------------------------------------------------------------------------------------ JSON schema -> Gemini schema


class _Unsupported(Exception):
    pass


_TYPES = {"string", "number", "integer", "boolean", "array", "object"}


def to_gemini_schema(schema: dict[str, Any]) -> dict[str, Any] | None:
    """`schema` in Gemini's OpenAPI subset (`responseSchema`), or None when it cannot be expressed (then JSON mode is used).

    Local `$ref`s are inlined (a recursive one is unsupported), `anyOf` with null becomes `nullable`, `title`/`default`/`additionalProperties`
    are dropped, an enum is kept for strings only, and an object without properties is unsupported (Gemini requires them)."""
    defs = dict(schema.get("$defs") or schema.get("definitions") or {})

    def conv(node: Any, depth: int, stack: frozenset[str]) -> dict[str, Any]:
        if not isinstance(node, dict) or depth > 16:
            raise _Unsupported
        if "$ref" in node:
            name = str(node["$ref"]).rsplit("/", 1)[-1]
            if name in stack or name not in defs:
                raise _Unsupported
            return conv({**defs[name], **{k: v for k, v in node.items() if k != "$ref"}}, depth + 1, stack | {name})
        for key in ("anyOf", "oneOf"):
            if key in node:
                opts = [o for o in node[key] if not (isinstance(o, dict) and o.get("type") == "null")]
                nullable = len(opts) < len(node[key])
                if len(opts) == 1:
                    out = conv({**opts[0], **({"description": node["description"]} if "description" in node else {})}, depth + 1, stack)
                else:
                    out = {"anyOf": [conv(o, depth + 1, stack) for o in opts]}
                if nullable:
                    out["nullable"] = True
                return out
        if "allOf" in node:
            parts = node["allOf"]
            if len(parts) != 1:
                raise _Unsupported
            return conv({**parts[0], **{k: v for k, v in node.items() if k != "allOf"}}, depth + 1, stack)
        t = node.get("type")
        nullable = False
        if isinstance(t, list):
            non_null = [x for x in t if x != "null"]
            nullable = len(non_null) < len(t)
            if len(non_null) != 1:
                raise _Unsupported
            t = non_null[0]
        enum = node.get("enum")
        if "const" in node:
            enum = [node["const"]]
        if t is None:
            if enum is not None and all(isinstance(e, str) for e in enum):
                t = "string"
            elif "properties" in node:
                t = "object"
            elif "items" in node:
                t = "array"
            else:
                raise _Unsupported
        if t not in _TYPES:
            raise _Unsupported
        out: dict[str, Any] = {"type": t.upper()}
        if node.get("description"):
            out["description"] = str(node["description"])[:500]
        if enum is not None and t == "string":
            out["enum"] = [str(e) for e in enum]
        if t == "object":
            props = node.get("properties") or {}
            if not props:
                raise _Unsupported
            out["properties"] = {k: conv(v, depth + 1, stack) for k, v in props.items()}
            req = [r for r in node.get("required") or [] if r in props]
            if req:
                out["required"] = req
            out["propertyOrdering"] = list(props)
        if t == "array":
            if "items" not in node:
                raise _Unsupported
            out["items"] = conv(node["items"], depth + 1, stack)
            for k in ("minItems", "maxItems"):
                if k in node:
                    out[k] = int(node[k])
        if t in ("number", "integer"):
            for k in ("minimum", "maximum"):
                if k in node:
                    out[k] = node[k]
        if nullable:
            out["nullable"] = True
        return out

    try:
        return conv(copy.deepcopy(schema), 0, frozenset())
    except (_Unsupported, KeyError, TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ bodies


def gemini_body(messages: list[dict[str, str]], *, max_tokens: int, temperature: float, json_schema: dict | None, modes: Modes, thinking: dict[str, Any], send_temperature: bool = True) -> dict[str, Any]:
    """generateContent request body."""
    msgs = prepare_messages(messages, modes, json_schema)
    system, rest = _split_system(msgs)
    contents = [{"role": "model" if m.get("role") == "assistant" else "user", "parts": [{"text": str(m.get("content", ""))}]} for m in rest]
    gen: dict[str, Any] = {"maxOutputTokens": int(max_tokens)}
    if send_temperature:
        gen["temperature"] = float(temperature)
    if json_schema is not None and modes.structured in ("schema", "json_mode"):
        gen["responseMimeType"] = "application/json"
        if modes.structured == "schema":
            converted = to_gemini_schema(json_schema)
            if converted is not None:
                gen["responseSchema"] = converted
    if modes.thinking == "on" and thinking:
        tc: dict[str, Any] = {}
        if thinking.get("budget") is not None:
            tc["thinkingBudget"] = int(thinking["budget"])
        if thinking.get("level"):
            tc["thinkingLevel"] = str(thinking["level"])
        if tc:
            gen["thinkingConfig"] = tc
    body: dict[str, Any] = {"contents": contents, "generationConfig": gen}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    return body


def openai_body(messages: list[dict[str, str]], *, model: str, max_tokens: int, temperature: float, json_schema: dict | None, modes: Modes, thinking: dict[str, Any],
                max_tokens_field: str = "max_tokens", send_temperature: bool = True) -> dict[str, Any]:  # fmt: skip
    """/chat/completions request body."""
    msgs = prepare_messages(messages, modes, json_schema)
    body: dict[str, Any] = {"model": model, "messages": msgs, max_tokens_field: int(max_tokens)}
    if send_temperature:
        body["temperature"] = float(temperature)
    if json_schema is not None:
        if modes.structured == "schema":
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "output", "strict": False, "schema": json_schema}}
        elif modes.structured == "json_mode":
            body["response_format"] = {"type": "json_object"}
    if modes.thinking == "on" and thinking:
        body.update({k: v for k, v in thinking.items() if k not in ("budget", "level")})
    return body


# ------------------------------------------------------------------------------------------------ replies


def parse_gemini(data: dict[str, Any]) -> Reply:
    """Read a generateContent answer (raises on a blocked prompt or an empty answer)."""
    fb = data.get("promptFeedback") or {}
    if fb.get("blockReason"):
        raise HostedError(f"the provider blocked the prompt ({fb.get('blockReason')})")
    cand = (data.get("candidates") or [{}])[0] or {}
    parts = ((cand.get("content") or {}).get("parts")) or []
    text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict) and not p.get("thought"))
    usage = data.get("usageMetadata") or {}
    finish = cand.get("finishReason")
    rep = Reply(text, int(usage.get("promptTokenCount", 0) or 0), int(usage.get("candidatesTokenCount", 0) or 0), int(usage.get("thoughtsTokenCount", 0) or 0),
                finish, data.get("modelVersion"))  # fmt: skip
    if not text.strip():
        if finish == "MAX_TOKENS":
            raise HostedError("the answer stopped at the token limit before any text (thinking may have used the budget); raise max_tokens or lower thinking")
        raise HostedError(f"the provider returned an empty answer (finishReason {finish})")
    return rep


def parse_openai(data: dict[str, Any]) -> Reply:
    """Read a chat-completions answer."""
    choice = (data.get("choices") or [{}])[0] or {}
    msg = choice.get("message") or {}
    usage = data.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    text = str(msg.get("content") or "")
    if not text.strip():
        if choice.get("finish_reason") == "length":
            raise HostedError("the answer stopped at the token limit before any text; raise max_tokens or lower the reasoning effort")
        raise HostedError("the provider returned an empty answer")
    return Reply(text, int(usage.get("prompt_tokens", 0) or 0), int(usage.get("completion_tokens", 0) or 0), int(details.get("reasoning_tokens", 0) or 0),
                 choice.get("finish_reason"), data.get("model"))  # fmt: skip


# ------------------------------------------------------------------------------------------------ errors


def _seconds(raw: Any) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)s?", s)
    if m:
        return float(m.group(1))
    try:
        import time

        return max(0.0, parsedate_to_datetime(s).timestamp() - time.time())
    except (TypeError, ValueError):
        return None


def error_info(status: int, headers: Any, payload: Any) -> tuple[str, str | None, float | None, bool]:
    """(message, code, retry_after seconds, per_day) of an error response, for both protocols."""
    err: dict[str, Any] = {}
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        payload = payload[0]
    if isinstance(payload, dict):
        e = payload.get("error")
        err = e if isinstance(e, dict) else {"message": str(e or "")}
    message = str(err.get("message") or "")[:300]
    code = err.get("status") or err.get("code") or err.get("type")
    retry = _seconds((headers or {}).get("retry-after")) if headers is not None else None
    per_day = False
    for d in err.get("details") or []:
        if not isinstance(d, dict):
            continue
        if str(d.get("@type", "")).endswith("RetryInfo") and retry is None:
            retry = _seconds(d.get("retryDelay"))
        for v in d.get("violations") or []:
            if "perday" in (str(v.get("quotaId", "")) + str(v.get("quotaMetric", ""))).lower().replace("_", "").replace("-", ""):
                per_day = True
    low = message.lower()
    if status == 429 and ("per day" in low or "perday" in low.replace(" ", "") or "daily" in low):
        per_day = True
    return message, (str(code) if code is not None else None), retry, per_day


def adapt(modes: Modes, error_text: str, has_schema: bool) -> Modes | None:
    """After a 400: the next weaker mode the error points to, or None when it cannot be worked around."""
    t = error_text.lower()
    if modes.system == "system" and any(w in t for w in ("developer instruction", "system instruction", "system_instruction", "systeminstruction", "system role", "system message")):
        return replace(modes, system="fold")
    if modes.thinking == "on" and any(w in t for w in ("thinking", "reasoning_effort", "reasoning effort", "thinkingconfig", "thinking_config")):
        return replace(modes, thinking="off")
    if has_schema and modes.structured != "prompt" and any(
        w in t for w in ("json mode", "response_mime_type", "responsemimetype", "mime type", "response_schema", "responseschema", "response_format", "json_schema", "schema", "json")
    ):
        if modes.structured == "json_mode" or any(w in t for w in ("json mode", "mime type", "response_mime_type", "responsemimetype", "json_object")):
            return replace(modes, structured="prompt")
        return replace(modes, structured=STRUCTURED_ORDER[STRUCTURED_ORDER.index(modes.structured) + 1])
    return None
