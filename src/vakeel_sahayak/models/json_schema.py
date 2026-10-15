"""JSON-schema helpers for schema-constrained calls (plan §3.3): schema extraction, validation, and a conservative filler.

`validate` implements the subset of JSON Schema that pydantic emits (type, enum, const, properties, required,
additionalProperties, items, prefixItems, anyOf/oneOf/allOf, $ref/$defs, string/number/array bounds, pattern and the
`date` format). `fill` and `coerce` build an instance that validates by construction, copying values from the evidence
it is given and never inventing content: unknown strings stay empty, unknown lists stay empty, and an enum with no
evidence takes its most conservative value (UNSUPPORTED, NEEDS_REVIEW, MISSING, CHECK, UNKNOWN, ...). The offline LLM
uses them, and the structured-output loop uses `validate` for dict schemas.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

# Enum values preferred, in this order, when there is no evidence for a choice: the answer that sends the item to counsel.
CONSERVATIVE_ENUM_ORDER: tuple[str, ...] = (
    "UNSUPPORTED", "NEEDS_REVIEW", "MISSING", "UNANSWERED", "CHECK", "UNKNOWN", "NOT_APPLICABLE", "not_applicable",
    "OTHER", "CHANGED", "WEAK",
)  # fmt: skip
GLOBAL_KEYS: frozenset[str] = frozenset({"case_id", "factor", "as_of", "before", "court", "trigger", "gate"})
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_KEY = re.compile(r"(^|_)(date|as_of|before|on)$")


def schema_of(schema: Any) -> dict[str, Any]:
    """The JSON schema of a pydantic model class (or instance), or the dict itself.

    Args:
        schema: a BaseModel subclass, a BaseModel instance, or a JSON-schema dict

    Returns:
        A JSON-schema dict.

    Raises:
        TypeError: for anything else.
    """
    if isinstance(schema, dict):
        return schema
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return schema.model_json_schema()
    if isinstance(schema, BaseModel):
        return type(schema).model_json_schema()
    raise TypeError(f"expected a pydantic model class or a JSON-schema dict, got {type(schema).__name__}")


def _resolve(node: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    """Follow local `$ref`s ('#/$defs/Name' or '#/definitions/Name'); merge sibling keywords over the target."""
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 32:
        ref = node["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise ValueError(f"only local $refs are supported, got {ref!r}")
        target: Any = root
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        node = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
        seen += 1
    return node


def _type_ok(value: Any, kind: str) -> bool:
    if kind == "null":
        return value is None
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    if kind == "array":
        return isinstance(value, list)
    if kind == "object":
        return isinstance(value, dict)
    return True


def validate(instance: Any, schema: dict[str, Any], root: dict[str, Any] | None = None, path: str = "$") -> list[str]:
    """Validate an instance; returns 'path: problem' strings (empty when valid).

    Args:
        instance: the decoded JSON value
        schema: the schema node to validate against
        root: the root schema (for $refs); defaults to `schema`
        path: where `instance` sits, for messages

    Returns:
        Problems, at most a few per node.
    """
    root = schema if root is None else root
    if schema is True or schema == {}:
        return []
    if schema is False:
        return [f"{path}: no value is allowed here"]
    node = _resolve(schema, root)
    errs: list[str] = []
    if "const" in node and instance != node["const"]:
        return [f"{path}: must be {node['const']!r}"]
    if "enum" in node and instance not in node["enum"]:
        return [f"{path}: must be one of {node['enum']!r}"]
    if "anyOf" in node or "oneOf" in node:
        branches = node.get("anyOf") or node.get("oneOf") or []
        results = [validate(instance, b, root, path) for b in branches]
        if not any(not r for r in results):
            best = min(results, key=len) if results else [f"{path}: no branch matches"]
            return best[:3]
    for sub in node.get("allOf", []):
        errs += validate(instance, sub, root, path)
    kinds = node.get("type")
    if kinds is not None:
        kinds_list = kinds if isinstance(kinds, list) else [kinds]
        if not any(_type_ok(instance, k) for k in kinds_list):
            return [f"{path}: expected {'/'.join(kinds_list)}, got {type(instance).__name__}"]
    if isinstance(instance, str):
        if "minLength" in node and len(instance) < node["minLength"]:
            errs.append(f"{path}: shorter than {node['minLength']}")
        if "maxLength" in node and len(instance) > node["maxLength"]:
            errs.append(f"{path}: longer than {node['maxLength']}")
        if "pattern" in node and not re.search(node["pattern"], instance):
            errs.append(f"{path}: does not match {node['pattern']!r}")
        if node.get("format") == "date" and not _is_date(instance):
            errs.append(f"{path}: not a date (YYYY-MM-DD)")
        if node.get("format") == "date-time" and not _is_datetime(instance):
            errs.append(f"{path}: not an ISO date-time")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in node and instance < node["minimum"]:
            errs.append(f"{path}: below {node['minimum']}")
        if "maximum" in node and instance > node["maximum"]:
            errs.append(f"{path}: above {node['maximum']}")
        if "exclusiveMinimum" in node and instance <= node["exclusiveMinimum"]:
            errs.append(f"{path}: not above {node['exclusiveMinimum']}")
        if "exclusiveMaximum" in node and instance >= node["exclusiveMaximum"]:
            errs.append(f"{path}: not below {node['exclusiveMaximum']}")
    if isinstance(instance, list):
        if "minItems" in node and len(instance) < node["minItems"]:
            errs.append(f"{path}: fewer than {node['minItems']} items")
        if "maxItems" in node and len(instance) > node["maxItems"]:
            errs.append(f"{path}: more than {node['maxItems']} items")
        prefix = node.get("prefixItems") or []
        for i, item in enumerate(instance):
            sub = prefix[i] if i < len(prefix) else node.get("items")
            if sub is not None:
                errs += validate(item, sub, root, f"{path}[{i}]")
    if isinstance(instance, dict):
        props = node.get("properties") or {}
        for key in node.get("required", []):
            if key not in instance:
                errs.append(f"{path}: missing required '{key}'")
        extra = node.get("additionalProperties", True)
        for key, value in instance.items():
            if key in props:
                errs += validate(value, props[key], root, f"{path}.{key}")
            elif extra is False:
                errs.append(f"{path}: unexpected key '{key}'")
            elif isinstance(extra, dict):
                errs += validate(value, extra, root, f"{path}.{key}")
    return errs


def is_valid(instance: Any, schema: dict[str, Any], root: dict[str, Any] | None = None) -> bool:
    """True when `validate` finds no problem."""
    return not validate(instance, schema, root)


def _is_date(text: str) -> bool:
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return len(text) == 10


def _is_datetime(text: str) -> bool:
    try:
        datetime.fromisoformat(text)
    except ValueError:
        return False
    return True


def _index(data: Any, out: dict[str, Any] | None = None) -> dict[str, Any]:
    """First value of each key anywhere in the evidence, depth first, in insertion order (deterministic)."""
    out = {} if out is None else out
    if isinstance(data, dict):
        for k, v in data.items():
            out.setdefault(str(k), v)
        for v in data.values():
            _index(v, out)
    elif isinstance(data, list):
        for v in data:
            _index(v, out)
    return out


def _first_iso_date(data: Any) -> str | None:
    """The first ISO date anywhere in the evidence (strings only)."""
    if isinstance(data, str):
        for m in _ISO_DATE.finditer(data):
            if _is_date(m.group(0)):
                return m.group(0)
        return None
    if isinstance(data, dict):
        data = list(data.values())
    if isinstance(data, list):
        for v in data:
            found = _first_iso_date(v)
            if found:
                return found
    return None


class _Filler:
    """Builds schema-valid values from evidence (see the module docstring)."""

    def __init__(self, root: dict[str, Any], evidence: Any) -> None:
        self.root = root
        self.evidence = evidence
        self.index = _index(evidence)
        self.any_date = _first_iso_date(evidence)

    def ok(self, value: Any, node: dict[str, Any]) -> bool:
        return not validate(value, node, self.root)

    def value(self, node: Any, local: Any, key: str | None, depth: int = 0) -> Any:
        """A value for `node`, preferring the evidence `local` (the value under the same key)."""
        if node is True or node == {} or node is None:
            return local
        node = _resolve(node, self.root)
        if local is not None and self.ok(local, node):
            return local
        if local is not None and isinstance(local, (dict, list)):
            coerced = self.coerce(local, node, key, depth)
            if self.ok(coerced, node):
                return coerced
        if key in GLOBAL_KEYS and local is None and key in self.index and self.ok(self.index[key], node):
            return self.index[key]
        return self.default(node, key, depth)

    def default(self, node: dict[str, Any], key: str | None, depth: int) -> Any:
        """A conservative value with no evidence."""
        node = _resolve(node, self.root)
        if "const" in node:
            return node["const"]
        if "default" in node and self.ok(node["default"], node):
            return node["default"]
        if "enum" in node:
            return self.pick_enum(node["enum"])
        branches = node.get("anyOf") or node.get("oneOf")
        if branches:
            for b in branches:
                if _resolve(b, self.root).get("type") == "null":
                    return None
            return self.default(branches[0], key, depth + 1)
        if node.get("allOf"):
            merged: dict[str, Any] = {}
            for b in node["allOf"]:
                merged.update(_resolve(b, self.root))
            return self.default(merged, key, depth + 1)
        kind = node.get("type")
        if isinstance(kind, list):
            kind = "null" if "null" in kind else kind[0]
        if kind == "object" or (kind is None and "properties" in node):
            return self.obj({}, node, depth)
        if kind == "array":
            item = node.get("items", {})
            return [self.default(item, None, depth + 1) for _ in range(int(node.get("minItems", 0)))]
        if kind == "string":
            if node.get("format") == "date" or (key and _DATE_KEY.search(key)):
                if self.any_date:
                    return self.any_date
            if node.get("format") == "date-time" and self.any_date:
                return self.any_date + "T00:00:00+00:00"
            return "-" * int(node.get("minLength", 0))
        if kind in ("integer", "number"):
            if "minimum" in node:
                val = node["minimum"]
            elif "exclusiveMinimum" in node:
                val = node["exclusiveMinimum"] + 1
            else:
                val = 0
            if "maximum" in node and val > node["maximum"]:
                val = node["maximum"]
            return int(val) if kind == "integer" else float(val)
        if kind == "boolean":
            return False
        return None

    @staticmethod
    def pick_enum(values: list[Any]) -> Any:
        for pref in CONSERVATIVE_ENUM_ORDER:
            if pref in values:
                return pref
        return values[0] if values else None

    def obj(self, local: dict[str, Any], node: dict[str, Any], depth: int) -> dict[str, Any]:
        """An object: required keys always, optional keys only when the evidence has them."""
        props = node.get("properties") or {}
        required = list(node.get("required", []))
        out: dict[str, Any] = {}
        for key, sub in props.items():
            if key in local:
                val = self.value(sub, local[key], key, depth + 1)
                if not isinstance(sub, dict) or self.ok(val, _resolve(sub, self.root)):
                    out[key] = val
                    continue
            if key in required:
                out[key] = self.value(sub, None, key, depth + 1)
        extra = node.get("additionalProperties", True)
        if isinstance(extra, dict) and not props:
            for key, val in local.items():
                cand = self.value(extra, val, key, depth + 1)
                if self.ok(cand, extra):
                    out[key] = cand
        return out

    def coerce(self, local: Any, node: Any, key: str | None, depth: int = 0) -> Any:
        """Keep what is valid in `local`, fix or drop the rest, fill what is required."""
        if depth > 40:
            return self.default(_resolve(node, self.root), key, depth)
        node = _resolve(node, self.root)
        if local is not None and self.ok(local, node):
            return local
        branches = node.get("anyOf") or node.get("oneOf")
        if branches:
            for b in branches:
                cand = self.coerce(local, b, key, depth + 1)
                if self.ok(cand, _resolve(b, self.root)):
                    return cand
            return self.default(node, key, depth)
        kind = node.get("type")
        if isinstance(local, dict) and (kind == "object" or (kind is None and "properties" in node)):
            return self.obj(local, node, depth)
        if isinstance(local, list) and kind == "array":
            item = node.get("items", {})
            items = []
            for v in local:
                cand = self.coerce(v, item, None, depth + 1)
                if self.ok(cand, _resolve(item, self.root) if isinstance(item, dict) else item):
                    items.append(cand)
            if "maxItems" in node:
                items = items[: node["maxItems"]]
            while len(items) < int(node.get("minItems", 0)):
                items.append(self.default(item, None, depth + 1))
            return items
        if kind == "string" and isinstance(local, (int, float)) and not isinstance(local, bool):
            cand = str(local)
            if self.ok(cand, node):
                return cand
        if kind == "integer" and isinstance(local, str) and local.strip().lstrip("-").isdigit():
            return int(local)
        if kind == "number" and isinstance(local, str):
            try:
                return float(local)
            except ValueError:
                pass
        return self.default(node, key, depth)


def fill(schema: dict[str, Any], evidence: Any = None) -> Any:
    """A schema-valid instance built only from `evidence` (conservative defaults elsewhere).

    Args:
        schema: JSON schema (root)
        evidence: decoded JSON evidence; a dict whose keys match the schema's property names is copied where valid

    Returns:
        A value that validates against `schema`.
    """
    filler = _Filler(schema, evidence)
    local = evidence if isinstance(evidence, dict) else {}
    node = _resolve(schema, schema)
    if node.get("type") == "object" or "properties" in node:
        return filler.obj(local, node, 0)
    return filler.value(node, evidence, None)


def coerce(instance: Any, schema: dict[str, Any], evidence: Any = None) -> Any:
    """Repair `instance` against `schema`: keep valid parts, drop or default invalid ones, fill missing required keys.

    Args:
        instance: a decoded JSON value (for example a handler's output)
        schema: JSON schema (root)
        evidence: further evidence for missing identifier keys (case_id, factor, as_of, ...)

    Returns:
        A value that validates against `schema`.
    """
    filler = _Filler(schema, [instance, evidence] if evidence is not None else instance)
    return filler.coerce(instance, schema, None)
