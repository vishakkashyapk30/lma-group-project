"""Regex extraction of Indian citations (INSC neutral, SCC, AIR, SCC OnLine, Cri LJ, 'X v. State of Y') from reasoning paragraphs (plan §5.3)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_YEAR = r"(?:19|20)\d{2}"
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("neutral", re.compile(rf"\b({_YEAR})\s+INSC\s+(\d{{1,5}})\b")),
    ("scc_online", re.compile(rf"\b({_YEAR})\s+SCC\s+On\s?Line\s+([A-Za-z][A-Za-z.]{{0,12}}(?:\s[A-Z][a-z]+)?)\s+(\d{{1,6}})\b", re.IGNORECASE)),
    ("scc", re.compile(rf"(?:\(({_YEAR})\)|\b({_YEAR})\s*\()\s*(\d{{1,3}})\)?\s+SCC\s+(\d{{1,5}})\b")),
    ("air", re.compile(rf"\bAIR\s+({_YEAR})\s+([A-Z][A-Za-z]{{1,6}}(?:\s?\([A-Za-z]+\))?)\s+(\d{{1,5}})\b")),
    ("crilj", re.compile(rf"\(?\b({_YEAR})\)?\s+(?:Cri\.?\s?L\.?\s?J\.?|CriLJ|Crl\.?\s?L\.?\s?J\.?)\s+(\d{{1,5}})\b", re.IGNORECASE)),
]
_WORD_TOKEN = r"(?:[A-Z]\.|[A-Z][\w&'’-]*)"
_NAME = rf"{_WORD_TOKEN}(?:\s+(?:of|the|and|&|{_WORD_TOKEN})){{0,6}}"
_STATE = r"State\s+of\s+[A-Z][a-z]+(?:\s+(?:and\s+)?[A-Z][a-z]+)?|State\b(?:\s+\(NCT\s+of\s+Delhi\))?|Union\s+of\s+India|Central\s+Bureau\s+of\s+Investigation|CBI|NIA|NCB"
_CASE_NAME = re.compile(
    rf"\b((?:{_STATE}|{_NAME})\s+(?:v\.?|vs\.?|versus)\s+(?:{_STATE}|{_NAME})(?:\s+(?:and|&)\s+(?:Ors|Anr|Others|Another)\.?)?)(?:\s*[,(]\s*\(?({_YEAR})\)?\)?)?"
)
_TITLE_WORDS = {"The", "This", "That", "In", "It", "As", "Hon", "Mr", "Mrs", "Shri", "Learned", "Section", "Court", "Bail", "On", "We", "I", "He", "She", "And", "But", "However", "Thus", "Also", "See", "Cf", "Vide", "Where", "Reliance", "Relying"}


@dataclass(frozen=True)
class ParsedCitation:
    """A citation split into its kind and a normalised key (plan §5.3)."""

    kind: str  # neutral | scc | scc_online | air | crilj | case_name
    key: str  # lower-case normalised key; for case names the 'p1 v p2' text
    year: int | None = None


def _clean_name(name: str) -> str:
    """Drop leading sentence words ('In Sanjay Chandra v. CBI' -> 'Sanjay Chandra v. CBI')."""
    words = name.split()
    while words and words[0] in _TITLE_WORDS and not re.match(r"^(?:v\.?|vs\.?)$", words[0]):
        words.pop(0)
    return " ".join(words)


def extract_citations(text: str) -> list[str]:
    """Find raw citation strings.

    Recognises neutral citations ('2023 INSC 123'), SCC ('(2014) 8 SCC 273'), AIR ('AIR 1978 SC 597'), SCC OnLine
    ('2022 SCC OnLine Del 1234'), Cri LJ ('2010 Cri LJ 1234') and case names ('X v. State of Y', 'State of Y v. X').

    Args:
        text: see behaviour

    Returns:
        Citation strings as written, in order of appearance, no exact duplicates.
    """
    found: list[tuple[int, str]] = []
    for _, pattern in _PATTERNS:
        found.extend((m.start(), m.group(0).strip()) for m in pattern.finditer(text))
    for m in _CASE_NAME.finditer(text):
        name = _clean_name(m.group(1))
        if " v" in f" {name}" and len(name.split()) >= 3:
            found.append((m.start(), name if not m.group(2) else f"{name} ({m.group(2)})"))
    seen: set[str] = set()
    out: list[str] = []
    for _, raw in sorted(found):
        if raw not in seen:
            seen.add(raw)
            out.append(raw)
    return out


def parse_citation(raw: str) -> ParsedCitation | None:
    """Classify one raw citation and build its normalised key.

    Args:
        raw: a string from `extract_citations`, or a citation taken from metadata

    Returns:
        ParsedCitation, or None when the string is none of the known formats.
    """
    s = raw.strip()
    if m := _PATTERNS[0][1].search(s):
        return ParsedCitation("neutral", f"{m.group(1)} insc {int(m.group(2))}", int(m.group(1)))
    if m := _PATTERNS[1][1].search(s):
        court = re.sub(r"[^a-z]", "", m.group(2).lower())
        return ParsedCitation("scc_online", f"{m.group(1)} scc online {court} {int(m.group(3))}", int(m.group(1)))
    if m := _PATTERNS[2][1].search(s):
        year = int(m.group(1) or m.group(2))
        return ParsedCitation("scc", f"{year} {int(m.group(3))} scc {int(m.group(4))}", year)
    if m := _PATTERNS[3][1].search(s):
        court = re.sub(r"[^a-z]", "", m.group(2).lower())
        return ParsedCitation("air", f"air {m.group(1)} {court} {int(m.group(3))}", int(m.group(1)))
    if m := _PATTERNS[4][1].search(s):
        return ParsedCitation("crilj", f"{m.group(1)} crilj {int(m.group(2))}", int(m.group(1)))
    if m := _CASE_NAME.search(s):
        year = int(m.group(2)) if m.group(2) else None
        return ParsedCitation("case_name", re.sub(r"\s+", " ", _clean_name(m.group(1))).lower(), year)
    return None
