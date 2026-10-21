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

One deliberate exception exists, for evaluation only: variant S10 / A8c (`Switches.abhiyojak_isolation=False`) removes the isolation
to measure what it buys. `build_open_context` is that arm. It refuses to run unless the switch is off, so the default guard stays in
force everywhere else, and the agent labels every event of the arm (`isolation_off`). It adds one key, `vakeel_view`, to the allow-listed
context: Vakeel's decision notes, the brief's open issues, Sutradhar's per-factor reasons and the replies so far. No other key, no
raw working state. Paper: Wynn, Satija and Hadfield, "Talk Isn't Always Cheap: Understanding Failure Modes in Multi-Agent Debate",
arXiv 2025 (ICML 2025 MAS workshop), https://arxiv.org/abs/2509.05396 (agents flip from right to wrong after reading a peer's
reasoning); we took the idea of widening what the critic reads, not the debate protocol; their flip is measured on answers, ours on
objections (see `abhiyojak.agent.AbhiyojakAgent.critic_signals`).
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


NOTE_TOOLS: frozenset[str] = frozenset({
    "draft", "check", "repair", "flag", "qualify", "warn", "label", "reply", "reretrieve", "authority_excluded", "authority_flags",
    "unchecked", "self_critique",
})  # fmt: skip  # Vakeel's decision events that read as notes (S10 only)
MAX_NOTES = 40
NOTE_CHARS = 300


def _note(claim: Any, tool: Any, text: Any) -> dict[str, Any]:
    return {"claim": None if claim is None else str(claim), "tool": None if tool is None else str(tool), "text": str(text or "")[:NOTE_CHARS]}


def vakeel_view(state: CaseGraphState, log: Any = None, case_id: str | None = None) -> dict[str, Any]:
    """What Abhiyojak sees of Vakeel's side when the isolation is off (S10 only): decision notes, open issues, factor reasons, replies.

    Notes come from the state's `vakeel_notes` / `vakeel_plan` attributes when a caller attached them, and from Vakeel's own decision events
    in the case log (`NOTE_TOOLS`, text only). Nothing is read from Vakeel's objects: only what Vakeel already wrote down.
    """
    from vakeel_sahayak.schemas.enums import EventKind

    notes: list[dict[str, Any]] = []
    for attr in ("vakeel_notes", "vakeel_plan"):
        value = getattr(state, attr, None)
        if value:
            for item in value if isinstance(value, (list, tuple)) else [value]:
                notes.append(_note(None, attr, item))
    if log is not None and case_id:
        try:
            events = log.read(case_id)
        except Exception:  # noqa: BLE001 - a log that cannot be read gives the arm no notes, never a crash
            events = []
        for e in events:
            out = e.outputs or {}
            kind = str(out.get("type") or e.tool or "")
            if getattr(e.actor, "value", e.actor) == "VAKEEL" and e.kind == EventKind.AGENT_MESSAGE and kind in NOTE_TOOLS and out.get("text"):
                notes.append(_note(out.get("claim") or out.get("ground"), kind, out["text"]))
    brief = state.brief
    return {
        "notes": notes[-MAX_NOTES:],
        "open_issues": [f"{i.type.value}: {i.item}"[:NOTE_CHARS] for i in (brief.open_issues if brief is not None else [])],
        "plan": [{"factor": p.factor.value, "stance": p.stance.value, "reason": str(p.reason or "")[:NOTE_CHARS]} for p in state.evidence_packs],
        "replies": [
            {"objection": o.id, "against": o.against, "text": o.reply.text[:NOTE_CHARS]}
            for o in (state.sparring.objections if state.sparring is not None else []) if o.reply is not None
        ],
    }  # fmt: skip


def build_open_context(state: CaseGraphState, switches: Any, *, log: Any = None, case_id: str | None = None) -> dict[str, Any]:
    """The isolated context plus `vakeel_view`: the no-isolation arm S10 / A8c, reachable only with `abhiyojak_isolation=False`.

    Raises:
        ContextIsolationError: the switch is on its default (isolation on), so this arm may not be used.
    """
    if getattr(switches, "abhiyojak_isolation", True):
        raise ContextIsolationError("build_open_context is the no-isolation arm (S10 / A8c): it needs Switches.abhiyojak_isolation=False")
    context = build_context(state)
    context["vakeel_view"] = vakeel_view(state, log, case_id or getattr(state, "case_id", None))
    return context


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
