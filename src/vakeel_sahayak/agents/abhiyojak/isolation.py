"""Context isolation: what Abhiyojak may see (plan §9).

Abhiyojak's input is built from an allow-list and nothing else: the drafted grounds (with the authorities they cite),
the approved dossier as citable facts (A1: the raw facts text), and its own three stores (`advocacy.objections`, the
refusal reasoning of `caselaw.reasoning`, `law.statutes`). It never sees Vakeel's plan, notes or working state, nor
Sutradhar's plan or evidence packs, so it cannot simply agree with them.

The isolation is structural, in three layers:

1. every agent method reads the graph state only through `build_context`, which copies the allow-listed parts out of
   it (the state's `plans`, `evidence_packs`, `brief.open_issues`, ... are never read);
2. `build_context` takes no other input, and rejects any extra keyword or mapping key that is not on the allow-list;
3. `assert_allowed` is the runtime guard: it walks a payload (a context, a prompt's case data, a mapping handed in) and
   raises `ContextIsolationError` on any key that names Vakeel's or Sutradhar's private material.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from vakeel_sahayak.agents.vakeel.facts import facts_of, text_fact
from vakeel_sahayak.orchestration.state import CaseGraphState

VISIBLE_STORES: list[str] = ["advocacy.objections", "caselaw.reasoning", "law.statutes"]
ALLOWED_KEYS: tuple[str, ...] = ("case_id", "grounds", "dossier", "sections", "as_of", "stores")
# Keys that name another agent's private material (matched on the normalised key; any prefix or suffix counts).
FORBIDDEN_KEYS: tuple[str, ...] = (
    "plan", "plans", "retrieval_plan", "notes", "scratch", "scratchpad", "working_state", "work", "reasoning_trace",
    "vakeel_plan", "vakeel_notes", "vakeel_state", "vakeel_private", "sutradhar_plan", "sutradhar_notes",
    "evidence_packs", "factor_decisions", "private",
)  # fmt: skip
_FORBIDDEN = {k.lower() for k in FORBIDDEN_KEYS}
_PRIVATE_PREFIX = re.compile(r"^_|^(?:vakeel|sutradhar)_(?:plan|notes?|state|work|private|scratch)", re.IGNORECASE)


class ContextIsolationError(ValueError):
    """Something of Vakeel's (or Sutradhar's) private material was about to reach Abhiyojak."""


def forbidden_keys_in(payload: Any, path: str = "") -> list[str]:
    """Paths of every key in a nested payload that names private material of another agent."""
    found: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            name = str(key)
            here = f"{path}.{name}" if path else name
            if name.lower() in _FORBIDDEN or _PRIVATE_PREFIX.match(name):
                found.append(here)
            found += forbidden_keys_in(value, here)
    elif isinstance(payload, (list, tuple)):
        for i, value in enumerate(payload):
            found += forbidden_keys_in(value, f"{path}[{i}]")
    return found


def assert_allowed(payload: Any) -> None:
    """The runtime guard: raise `ContextIsolationError` when a payload carries a key of Vakeel's or Sutradhar's private material.

    Args:
        payload: a mapping, list or scalar (nested)

    Raises:
        ContextIsolationError: naming the offending paths.
    """
    bad = forbidden_keys_in(payload)
    if bad:
        raise ContextIsolationError("Abhiyojak never sees Vakeel's or Sutradhar's plan, notes or working state; refused keys: " + ", ".join(bad[:10]))


def _ground_view(g: Any) -> dict[str, Any]:
    """A drafted ground as Abhiyojak may read it: id, factor, stance, argument, the authorities it cites, its check."""
    data = g if isinstance(g, Mapping) else g.model_dump(mode="json")
    auths = [
        {"doc_id": a.get("doc_id"), "para": a.get("para"), "citation": a.get("citation")}
        for a in (data.get("authorities") or [])
        if isinstance(a, Mapping)
    ]
    factor = data.get("factor")
    stance = data.get("stance")
    return {
        "id": data.get("id"),
        "factor": getattr(factor, "value", factor),
        "stance": getattr(stance, "value", stance),
        "argument": data.get("argument") or "",
        "authorities": auths,
        "check": getattr(data.get("check"), "value", data.get("check")),
    }


def _dossier_view(dossier: Any, facts_text: str | None) -> dict[str, dict[str, Any]]:
    """The dossier as citable facts by field (A1: the raw facts text as the one fact `facts_text`); each carries its raw value."""
    if isinstance(dossier, Mapping):
        return {str(k): dict(v) if isinstance(v, Mapping) else {"field": str(k), "text": str(v)} for k, v in dossier.items()}
    if dossier is None:
        return {name: f.payload() for name, f in text_fact(facts_text).items()}
    dumped = dossier.fields.model_dump(mode="json")
    return {name: {**f.payload(), "value": (dumped.get(name) or {}).get("value")} for name, f in facts_of(dossier).items()}


def _sections_view(dossier: Any) -> list[dict[str, Any]]:
    """The charged sections of the dossier (code, section, bailable, maximum punishment): what `get_statute` is asked for."""
    if dossier is None or isinstance(dossier, Mapping):
        return []
    tracked = dossier.fields.sections
    return [
        {"code": sv.code, "section": sv.section, "bailable": sv.bailable, "max_punishment": sv.max_punishment}
        for sv in (tracked.value or [])
        if sv.code and sv.section
    ]


def build_context(state: CaseGraphState | Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    """Only drafted grounds with cited material and the dossier; never Vakeel's plan or notes.

    Args:
        state: the graph state (read only through the allow-list) or a mapping with the allow-listed keys; a mapping
            that carries any key outside `ALLOWED_KEYS` is refused
        **extra: nothing is accepted here: a keyword is refused (it exists so the refusal is explicit, not a TypeError)

    Returns:
        Prompt context: `case_id`, `grounds`, `dossier` (field -> fact), `sections` (the charged sections), `as_of` and `stores`.

    Raises:
        ContextIsolationError: for private keys or any key outside the allow-list.
    """
    if extra:
        assert_allowed(extra)
        raise ContextIsolationError("build_context takes only the state; refused keys: " + ", ".join(sorted(extra)))
    if isinstance(state, Mapping):
        assert_allowed(state)
        stray = [str(k) for k in state if str(k) not in ALLOWED_KEYS and str(k) != "facts_text"]
        if stray:
            raise ContextIsolationError("not on Abhiyojak's allow-list: " + ", ".join(stray))
        raw_grounds = state.get("grounds") or []
        context = {
            "case_id": state.get("case_id"),
            "grounds": [_ground_view(g) for g in raw_grounds],
            "dossier": _dossier_view(state.get("dossier"), state.get("facts_text")),
            "sections": _sections_view(state.get("dossier")) or [dict(x) for x in state.get("sections") or []],
            "as_of": state.get("as_of") or getattr(state.get("dossier"), "as_of", None),
            "stores": list(VISIBLE_STORES),
        }
    else:
        brief = state.brief
        dossier = state.dossier
        if dossier is None:
            try:
                dossier = state.case_state().dossier()  # the approved dossier of the case log, as Vakeel reads it
            except Exception:  # noqa: BLE001 - a case with no log yet has no dossier
                dossier = None
        context = {
            "case_id": state.case_id,
            "grounds": [_ground_view(g) for g in (brief.grounds if brief is not None else [])],
            "dossier": _dossier_view(dossier, state.facts_text),
            "sections": _sections_view(dossier),
            "as_of": getattr(dossier, "as_of", None) or state.as_of,
            "stores": list(VISIBLE_STORES),
        }
    assert_allowed(context)
    return context
