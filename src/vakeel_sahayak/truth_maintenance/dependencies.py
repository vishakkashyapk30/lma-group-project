"""Dependency records and value hashing (plan §10).

A claim (a ground of the brief) depends on dossier fields (with the hash of each value), timeline events, Rights Radar
entries and authority paragraphs, and on other claims it cites. `collect_dependencies` reads that off a claim's markers,
`build_index` turns a brief's records into a reverse index (what depends on X) that staleness propagation walks.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from vakeel_sahayak.schemas.bail_brief import Authority, BailBrief, DependsOn
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.store_rows import TimelineEvent

HASH_DIGITS = 4  # the plan's example is 'h:3f2a'
_FACT_TAG = re.compile(r"\[\s*F\s*:\s*([^\]]+?)\s*\]")
_AUTH_TAG = re.compile(r"\[\s*A\s*:\s*([^\]#\s]+)\s*#\s*(\d+)\s*\]")
_CLAIM_TAG = re.compile(r"\[\s*C\s*:\s*([^\]]+?)\s*\]")


def _plain(value: Any) -> Any:
    """Models to JSON-mode dicts, so the hash is over canonical JSON."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def hash_value(value: Any) -> str:
    """Stable short hash of a value, e.g. 'h:3f2a' (plan §10): 'h:' and 4 hex digits of SHA-256 over canonical JSON.

    Args:
        value: a dossier value (JSON-able or a pydantic model)

    Returns:
        Hash string; equal values always give equal hashes.
    """
    blob = json.dumps(_plain(value), sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))
    return "h:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:HASH_DIGITS]


def authority_key(doc_id: str, para: int | str) -> str:
    """'doc_id#para'."""
    return f"{doc_id}#{para}"


def authority_flags(authorities: list[Authority]) -> dict[str, str]:
    """Each authority paragraph with its transfer and good-law flags ('doc#para' -> 'transfer=...;good_law=...')."""
    out: dict[str, str] = {}
    for a in authorities:
        transfer = getattr(a.transfer, "value", a.transfer)
        out[authority_key(a.doc_id, a.para)] = f"transfer={transfer};good_law={a.good_law.value}"
    return out


def authority_flag_changes(old: list[Authority], new: list[Authority]) -> list[str]:
    """'doc#para' keys whose transfer or good-law flag differs between two lists (a paragraph on one side only counts)."""
    a, b = authority_flags(old), authority_flags(new)
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def field_value_hashes(facts: CaseDossier | None, names: list[str] | None = None, skip_empty: bool = False) -> dict[str, str]:
    """Hash of the value of each named dossier field (all fields by default); the field's JSON-mode value, status left out.

    Args:
        facts: the dossier
        names: fields to hash (default: every field)
        skip_empty: leave out a field whose value is None (it has no hash yet)
    """
    if facts is None:
        return {}
    dumped = facts.fields.model_dump(mode="json")
    return {
        n: hash_value(dumped[n].get("value")) for n in (dumped if names is None else names)
        if n in dumped and not (skip_empty and dumped[n].get("value") is None)
    }  # fmt: skip


def collect_dependencies(
    claim_text: str, facts: CaseDossier, rights: RightsReport, authorities: list[Authority], timeline: list[TimelineEvent] | None = None,
) -> DependsOn:
    """Build the depends_on record of a claim from its [F:field] and [A:doc#para] tags (plan §8.1, §10).

    Fields: each cited dossier field with the hash of its value. Events: the timeline events that date those fields (when a
    timeline is given). Rights: the Radar checks that use one of the cited fields. Authorities: the cited paragraphs that
    are in `authorities` (or, failing that, as tagged). Claims: `[C:Gn]` markers.

    Args:
        claim_text: the claim's sentences with their markers
        facts: the approved dossier
        rights: the RightsReport the claim was drafted against
        authorities: the authorities the claim may cite
        timeline: the case timeline, to find the events behind the cited fields

    Returns:
        DependsOn.
    """
    fields: list[str] = []
    for m in _FACT_TAG.finditer(claim_text or ""):
        if m.group(1) not in fields:
            fields.append(m.group(1))
    hashes = field_value_hashes(facts, fields)
    events: list[str] = []
    if timeline:
        from vakeel_sahayak.agents.vakeel.facts import EVENT_FIELDS
        from vakeel_sahayak.ingestion.events import field_of_label

        wanted = {lf for f in hashes for lf in EVENT_FIELDS.get(f, ())}
        events = [e.event_id for e in timeline if field_of_label(e.label) in wanted and e.event_id]
    checks: list[str] = []
    for c in (rights.checks if rights is not None else []):
        if set(c.uses) & set(hashes) and c.check.value not in checks:
            checks.append(c.check.value)
    keys: list[str] = []
    known = {authority_key(a.doc_id, a.para) for a in authorities}
    for m in _AUTH_TAG.finditer(claim_text or ""):
        k = authority_key(m.group(1), m.group(2))
        if (k in known or not known) and k not in keys:
            keys.append(k)
    claims = list(dict.fromkeys(m.group(1) for m in _CLAIM_TAG.finditer(claim_text or "")))
    return DependsOn(facts=hashes, events=events, rights=checks, authorities=keys, claims=claims)


@dataclass
class DependencyIndex:
    """Reverse index of a brief: for each field / event / Radar check / authority / claim, the claims that depend on it."""

    by_field: dict[str, list[str]] = field(default_factory=dict)
    by_event: dict[str, list[str]] = field(default_factory=dict)
    by_rights: dict[str, list[str]] = field(default_factory=dict)
    by_authority: dict[str, list[str]] = field(default_factory=dict)
    by_claim: dict[str, list[str]] = field(default_factory=dict)  # cited claim -> the claims that cite it

    def citing(self, claim_id: str) -> list[str]:
        """Claims that cite this claim."""
        return list(self.by_claim.get(claim_id, []))


def _add(index: dict[str, list[str]], key: str, claim_id: str) -> None:
    if claim_id not in index.setdefault(key, []):
        index[key].append(claim_id)


def build_index(brief: BailBrief) -> DependencyIndex:
    """The dependency index of a brief (one entry per ground, in order)."""
    idx = DependencyIndex()
    for g in brief.grounds:
        d = g.depends_on
        for f in d.facts:
            _add(idx.by_field, f, g.id)
        for e in d.events:
            _add(idx.by_event, e, g.id)
        for r in d.rights:
            _add(idx.by_rights, r, g.id)
        for a in dict.fromkeys([*d.authorities, *(authority_key(x.doc_id, x.para) for x in g.authorities)]):
            _add(idx.by_authority, a, g.id)
        for c in d.claims:
            _add(idx.by_claim, c, g.id)
    return idx
