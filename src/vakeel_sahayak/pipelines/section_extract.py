"""Regex section extraction and section-family expansion through the concordance (plan §5.2).

Recognised forms (acts: IPC, BNS, CrPC, BNSS, NDPS, UAPA, PMLA, POCSO, abbreviated or in full):
'Section 420 IPC', 'Sections 420, 406 and 34 of the Indian Penal Code, 1860', 'u/s 439 Cr.P.C.', 'S. 483 BNSS',
'420/406 IPC', '318(4) of the BNS, 2023', 'Section 37 of the NDPS Act', 'IPC 420', 'IPC Sections 420, 406',
'Section 302 r/w 34 IPC'. Sections without a recognised act are skipped, never guessed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from vakeel_sahayak.pipelines.concordance.refs import make_ref, normalise_section

if TYPE_CHECKING:
    from vakeel_sahayak.stores.law_concordance import ConcordanceStore

_ACTS: list[tuple[str, str]] = [
    ("BNSS", r"B\.?\s?N\.?\s?S\.?\s?S\.?|Bharatiya\s+Nagarik\s+Suraksha\s+Sanhita"),
    ("BNS", r"B\.?\s?N\.?\s?S\.?|Bharatiya\s+Nyaya\s+Sanhita"),
    ("IPC", r"I\.?\s?P\.?\s?C\.?|Indian\s+Penal\s+Code"),
    ("CrPC", r"Cr\.?\s?P\.?\s?C\.?|Code\s+of\s+Criminal\s+Procedure"),
    ("NDPS", r"N\.?\s?D\.?\s?P\.?\s?S\.?|Narcotic\s+Drugs\s+and\s+Psychotropic\s+Substances"),
    ("UAPA", r"U\.?\s?A\.?\s?\(?P\.?\)?\s?A\.?|Unlawful\s+Activities\s*\(?Prevention\)?"),
    ("PMLA", r"P\.?\s?M\.?\s?L\.?\s?A\.?|Prevention\s+of\s+Money[\s-]+Laundering"),
    ("POCSO", r"POCSO|Protection\s+of\s+Children\s+from\s+Sexual\s+Offences"),
]
_ACT_ALT = "|".join(f"(?P<{code}>{pat})" for code, pat in _ACTS)
# 'the', optional 'Act', an optional year after the name: 'the Indian Penal Code, 1860'.
_ACT_BARE = rf"(?:the\s+)?(?:{_ACT_ALT})(?:\s+Act)?(?![A-Za-z])"
_ACT = rf"(?:the\s+)?(?:{_ACT_ALT})(?:\s+Act)?(?:\s*[,(]?\s*(?:18|19|20)\d\d\)?)?(?![A-Za-z])"
_TOKEN = r"\d{1,3}[A-Za-z]{0,2}(?:\s?\([0-9A-Za-z]{1,4}\))*(?![\d])"
_SEP = r"\s*(?:,|/|&|and|or|to|r/w|r\.w\.|read\s+with|along\s*with|alongwith|read\s+together\s+with|-)\s*(?:sections?\s+|secs?\.?\s*|s\.\s*)?"
_LIST = rf"{_TOKEN}(?:{_SEP}{_TOKEN})*"
_KEYWORD = r"(?:sections?|secs?\.?|ss\.|s\.|u/s\.?|u/ss\.?|under\s+sections?|under|धारा|धाराएँ|धाराओं)"
_GAP = r"(?:\s*,?\s*(?:of|under|in|to|r/w|read\s+with)?\s*(?:the\s+)?)"

# 1. 'Section(s) <list> [of the] <ACT>'
_KEYED_THEN_ACT = re.compile(rf"(?<![A-Za-z]){_KEYWORD}\s*(?P<list>{_LIST}){_GAP}{_ACT}", re.IGNORECASE)
# 2. '<ACT> [Section(s)] <list>'
_ACT_THEN_LIST = re.compile(rf"(?<![A-Za-z]){_ACT_BARE}[\s,:-]*(?:{_KEYWORD}\s*)?(?P<list>{_LIST})", re.IGNORECASE)
# 3. bare '<list> <ACT>' with at least two sections, or a clause: '420/406 IPC', '318(4) BNS'
_BARE_THEN_ACT = re.compile(rf"(?<![\w(])(?P<list>{_TOKEN}(?:{_SEP}{_TOKEN})+|\d{{1,3}}(?!(?:st|nd|rd|th)\b)[A-Za-z]{{1,2}}(?:\s?\([0-9A-Za-z]{{1,4}}\))*|\d{{1,3}}(?:\s?\([0-9A-Za-z]{{1,4}}\))+)\s*(?:of\s+(?:the\s+)?)?{_ACT}", re.IGNORECASE)
_TOKEN_RE = re.compile(_TOKEN)


def _act_of(match: re.Match[str]) -> str | None:
    """The canonical act code of the act group that matched."""
    for code, _ in _ACTS:
        if match.group(code):
            return code
    return None


def extract_sections(text: str) -> list[str]:
    """Regex-extract sections such as 'IPC 420', '318(4) BNS'.

    Args:
        text: see behaviour

    Returns:
        Normalised refs ('IPC 420', 'BNS 318(4)'), first occurrence order, no duplicates.
    """
    found: list[tuple[int, int, str]] = []
    for pattern in (_KEYED_THEN_ACT, _ACT_THEN_LIST, _BARE_THEN_ACT):
        for m in pattern.finditer(text):
            code = _act_of(m)
            if not code:
                continue
            base = m.start("list")
            for tok in _TOKEN_RE.finditer(m.group("list")):
                found.append((base + tok.start(), 0, make_ref(code, normalise_section(tok.group(0)))))
    seen: dict[str, int] = {}
    for pos, _, ref in sorted(found):
        seen.setdefault(ref, pos)
    return list(seen)


# Procedural bail provisions say what kind of application it is, not what the accused is charged with.
PROCEDURAL_BAIL_REFS = frozenset(
    {"CrPC 167", "CrPC 436", "CrPC 436A", "CrPC 437", "CrPC 438", "CrPC 439", "BNSS 187", "BNSS 478", "BNSS 479", "BNSS 480", "BNSS 482", "BNSS 483"}
)


def charged_sections(sections: list[str]) -> list[str]:
    """The offences among extracted references: procedural bail provisions (CrPC 436-439, BNSS 478-483, ...) are dropped.

    Args:
        sections: references from `extract_sections`

    Returns:
        References minus the procedural provisions, order kept.
    """
    return [s for s in sections if s.split("(")[0] not in PROCEDURAL_BAIL_REFS]


def expand_family(
    sections: list[str], concordance_path: str | None = None, *, store: ConcordanceStore | None = None
) -> list[str]:
    """Expand through the concordance to a section family.

    Args:
        sections: references such as 'IPC 420'
        concordance_path: concordance SQLite file or its folder; None uses the configured store (offline seed if absent)
        store: an already open ConcordanceStore (takes precedence; lets callers open it once)

    Returns:
        Family refs: each input kept, plus its counterparts in the other act and sub-clauses; sorted, no duplicates.
    """
    if store is None:
        from vakeel_sahayak.stores.law_concordance import ConcordanceStore

        store = ConcordanceStore()
        store.open(concordance_path)
    family: set[str] = set()
    for ref in sections:
        family.add(ref)
        try:
            family.update(store.family(ref))
        except ValueError:  # not a full reference; keep as written
            continue
    return sorted(family)
