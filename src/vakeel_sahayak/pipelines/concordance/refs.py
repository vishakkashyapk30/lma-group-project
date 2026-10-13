"""Parse and normalise statute references such as 'IPC 420', 'Section 318(4) of the BNS', 'CrPC 436A' (plan §5.4)."""

from __future__ import annotations

import re

CODE_ALIASES = {
    "IPC": "IPC",
    "BNS": "BNS",
    "CRPC": "CrPC",
    "CR.P.C": "CrPC",
    "CR.P.C.": "CrPC",
    "BNSS": "BNSS",
    "NDPS": "NDPS",
    "UAPA": "UAPA",
    "PMLA": "PMLA",
    "POCSO": "POCSO",
}
OLD_TO_NEW = {"IPC": "BNS", "CrPC": "BNSS"}
NEW_TO_OLD = {new: old for old, new in OLD_TO_NEW.items()}

_CODE_RE = re.compile(
    r"(?<![A-Za-z])(IPC|BNSS|BNS|Cr\.?\s?P\.?\s?C\.?|NDPS|UAPA|PMLA|POCSO)(?![A-Za-z])", re.IGNORECASE
)
_SECTION_RE = re.compile(r"(?<![\w(])(\d+[A-Za-z]{0,2}(?:\([0-9A-Za-z]+\))*(?:\s+proviso)?)(?![\w])")


def normalise_code(code: str) -> str:
    """Canonical act code: 'ipc' -> 'IPC', 'crpc' / 'Cr.P.C.' -> 'CrPC'.

    Raises:
        ValueError: for an act this module does not know.
    """
    key = re.sub(r"\s+", "", code).upper()
    if key not in CODE_ALIASES:
        raise ValueError(f"unknown act code {code!r}")
    return CODE_ALIASES[key]


_SECTION_HEAD = re.compile(r"^(\d+\s*[A-Za-z]{0,2})((?:\s*\([0-9A-Za-z]+\))*)(.*)$")


def normalise_section(section: str) -> str:
    """Canonical section: strip 's.', 'section' and spaces; upper-case trailing letters: 's. 436a' -> '436A'.

    Words after the number and clauses are kept ('437(1) proviso' stays '437(1) proviso').
    """
    text = re.sub(r"^(?:sections?|sec\.?|s\.)\s*", "", section.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    m = _SECTION_HEAD.match(text)
    if m:
        head, parens, tail = m.groups()
        tail = tail.strip()
        return head.replace(" ", "").upper() + parens.replace(" ", "") + (" " + tail if tail else "")
    head, sep, tail = text.partition("(")
    head = head.replace(" ", "").upper()
    return head + (sep + tail.replace(" ", "") if sep else "")


def make_ref(code: str, section: str) -> str:
    """Join a code and a section into the reference used as concordance keys: 'BNS 318(4)'."""
    return f"{normalise_code(code)} {normalise_section(section)}"


def parse_ref(text: str) -> tuple[str | None, str | None]:
    """Find the act code and section in free text; either may be None when absent.

    Args:
        text: for example 'IPC 420', '318(4) BNS', 'Section 436A of the CrPC'

    Returns:
        (canonical code or None, canonical section or None).
    """
    code_match = _CODE_RE.search(text)
    code = normalise_code(code_match.group(1)) if code_match else None
    rest = text[: code_match.start()] + " " + text[code_match.end() :] if code_match else text
    sec_match = _SECTION_RE.search(rest)
    return code, normalise_section(sec_match.group(1)) if sec_match else None


def split_ref(ref: str) -> tuple[str, str]:
    """Split a full reference such as 'BNS 318(4)' into (code, section); raises ValueError if either part is missing."""
    code, section = parse_ref(ref)
    if not code or not section:
        raise ValueError(f"not a full statute reference: {ref!r}")
    return code, section
