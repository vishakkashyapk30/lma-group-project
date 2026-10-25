"""Outbound boundary: only pseudonymised text may be sent to Ada (plan §16)."""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.privacy.pseudonymise import _NOT_A_PERSON, _PATTERNS, _PII, PseudonymMap

_BINARY_KEYS = re.compile(r"(?i)^(image|images|page_image|page_images|audio|pixels|raw_bytes|wav|png|jpg|jpeg)$")
_MEDIA_PATH = re.compile(
    r"(?i)\.(?:wav|mp3|m4a|ogg|opus|flac|aac|webm|png|jpe?g|tiff?|bmp|webp|heic)\s*$"
)  # a path to a client's audio or page image: the file itself never leaves the laptop
_DATA_URI = re.compile(r"^data:(image|audio)/", re.IGNORECASE)
_ALIAS_WORD = re.compile(r"(?:Accused|Co|Co-accused|Complainant|IO|Witness|Person)")


_ID_KEYS = re.compile(r"^(?:doc_ids?|chunk_ids?|para_ids?|ground_ids?|objection_ids?)$")
_ID_VALUE = re.compile(r"(?=[^\s]*[A-Za-z])[A-Za-z0-9_.:#-]{4,80}")  # an identifier made by the corpus or the case shelf: no spaces, with letters


class PrivacyBoundaryError(ValueError):
    """Raised when a payload bound for the cluster is not safe to send. The message never repeats the offending text."""


def _walk(value: Any, path: str):  # noqa: ANN202
    """Yield (path, key, leaf) for every leaf of a nested payload."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, path.rsplit(".", 1)[-1], value


def _find_problems(payload: dict, mapping: PseudonymMap | None, known_names: list[str] | None, *, generic_names: bool = True) -> list[str]:
    """List `path: reason` strings for everything in the payload that must not leave the laptop."""
    names = [*(known_names or []), *(mapping.known_names() if mapping else [])]
    name_res = [
        re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, n.split())) + r"(?!\w)", re.IGNORECASE) for n in names
    ]
    problems: list[str] = []
    for path, key, leaf in _walk(payload, ""):
        base_key = re.sub(r"\[\d+\]$", "", key)
        if isinstance(leaf, (bytes, bytearray, memoryview)):
            problems.append(f"{path}: binary data (page image or audio)")
        elif _BINARY_KEYS.match(base_key) and leaf not in (None, "", [], {}):
            problems.append(f"{path}: image or audio field")
        elif isinstance(leaf, str):
            if _MEDIA_PATH.search(leaf):
                problems.append(f"{path}: path to an audio or image file")
            if _DATA_URI.match(leaf):
                problems.append(f"{path}: embedded image or audio")
            if any(r.search(leaf) for r in name_res):
                problems.append(f"{path}: raw name from the alias map")
            is_id = bool(_ID_KEYS.match(base_key)) and _ID_VALUE.fullmatch(leaf) is not None  # 'JHHC010343052023' is a court-order id, not a 12-digit ID number
            if not is_id and any(p.search(leaf) for p, _ in _PII):
                problems.append(f"{path}: email, phone or ID number")
            if generic_names and any(p.search(leaf) for p, _ in _PATTERNS if not _only_aliases(p, leaf)):
                problems.append(f"{path}: un-pseudonymised personal name")
    return problems


def _only_aliases(pattern: re.Pattern[str], text: str) -> bool:
    """True when every capture of the name pattern in `text` is already an alias (for example 'Accused-1')."""
    return all(re.fullmatch(_ALIAS_WORD, m.group(1).strip()) or _NOT_A_PERSON.match(" ".join(m.group(1).split())) for m in pattern.finditer(text))


def assert_pseudonymised(
    payload: dict, mapping: PseudonymMap | None = None, known_names: list[str] | None = None
) -> None:
    """Raise if a payload bound for the cluster contains page images, audio or un-pseudonymised text.

    Checks, on every string in the (nested) payload: binary or image/audio fields; any real name held in `mapping` or
    `known_names`; emails, phone numbers and ID numbers; and, without any list, names still written after a title
    or role word ('Shri Rajesh Kumar', 'accused Rajesh Kumar').

    Args:
        payload: see behaviour
        mapping: the case's alias map, whose real names must not appear
        known_names: further real names to look for (for example from the dossier)

    Raises:
        PrivacyBoundaryError: listing where the problems are, never what they are.
    """
    problems = _find_problems(payload, mapping, known_names)
    if problems:
        raise PrivacyBoundaryError("payload is not safe to send to Ada: " + "; ".join(problems))


def assert_public_text(payload: Any, mapping: PseudonymMap | None = None, known_names: list[str] | None = None) -> None:
    """The check for public corpus text (published orders, statutes, objection-bank rows) sent beside the case data.

    Published orders legitimately name judges, counsel and parties, so the generic 'a name after a title or role word' patterns do not apply
    (the same rule as `agents.base.BaseAgent.guard_outbound(..., public=...)`). What still must not appear: binary or image/audio data, an
    email, phone or ID number, and any real name held in the case's alias map.

    Raises:
        PrivacyBoundaryError: listing where the problems are, never what they are.
    """
    problems = _find_problems({"corpus": payload}, mapping, known_names, generic_names=False)
    if problems:
        raise PrivacyBoundaryError("payload is not safe to send to Ada: " + "; ".join(problems))


def split_public_corpus(payload: Any) -> tuple[Any, list[Any]]:
    """Separate the `corpus` part of every prompt written by `models.prompting.render_prompt` from the rest of a payload.

    A prompt carries `INPUT (JSON)` with the private, pseudonymised `case` data and the public `corpus` data side by side. Returns the payload with each such prompt
    replaced by its case-side parts (system text, instructions, the data minus `corpus`, any repair note), and the list of corpus values taken out.
    Strings that do not use the layout, and prompts with no corpus, pass through whole, so everything not declared public keeps the full check."""
    from vakeel_sahayak.models.prompting import parse_prompt

    corpus: list[Any] = []

    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [walk(v) for v in value]
        if isinstance(value, str) and "### INPUT (JSON)" in value:
            parsed = parse_prompt(value)
            if parsed.task is not None and parsed.data.get("corpus"):
                corpus.append(parsed.data["corpus"])
                rest = {k: v for k, v in parsed.data.items() if k != "corpus"}
                return {"system": parsed.system, "task": parsed.task, "instructions": parsed.instructions, "schema": parsed.schema, "input": rest, "repair": parsed.repair}
        return value

    return walk(payload), corpus
