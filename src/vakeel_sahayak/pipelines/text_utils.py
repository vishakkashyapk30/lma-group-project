"""Small text helpers shared by the order pipelines and the chunker (plan §5.2).

Paragraph blocks, sentences, a token estimate, date normalisation and JSONL reading and writing. Pure Python, no models.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

# A numbered paragraph starts a line with '12.' or '12)' followed by text (not a bare number or a decimal).
_NUMBERED_START = re.compile(r"^\s*\(?\d{1,3}[.)]\s+(?=\S)", re.MULTILINE)
# The same marker in the middle of a line, right after a sentence end ('... custody. 2. The applicant ...'); accepted only
# when its number follows the previous paragraph number, so 'Rs. 5. The' or 'Section 2. Next' do not split.
_INLINE_NUMBER = re.compile(r"(?<=[.!?:;\"')\]])[ \t]+(?=\(?\d{1,3}[.)]\s+[A-Z(\"'])")
_LEADING_NUMBER = re.compile(r"^\(?(\d{1,3})[.)]\s")
_BLANK_LINES = re.compile(r"\n\s*\n+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")
# Abbreviations whose full stop does not end a sentence.
_ABBREVIATIONS = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Shri|Smt|Sh|Hon|Addl|Adv|Co|Ltd|No|Nos|Sec|Secs|Art|Cr|P|S|U|Vs|v|Ors|Anr|St|Jr|Sr|Dy)\.$|(?:^|\s)(?:सं|क्र|क्रं)\.$", re.IGNORECASE
)
_WORD = re.compile(r"\S+")

_MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"), ("may",), ("june", "jun"),
            ("july", "jul"), ("august", "aug"), ("september", "sep", "sept"), ("october", "oct"),
            ("november", "nov"), ("december", "dec"),
        ],
        start=1,
    )
    for m in names
}  # fmt: skip
_DMY_NUMERIC = re.compile(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$")
_DMY_TEXT = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?[\s,.-]+([A-Za-z]{3,9})[\s,.-]+(\d{4})$")
_MDY_TEXT = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})$")


def count_tokens(text: str) -> int:
    """Token estimate used for chunk sizes: whitespace-separated words (plan §5.2: up to 400 tokens).

    Args:
        text: any text

    Returns:
        Number of words.
    """
    return len(_WORD.findall(text))


def split_sentences(text: str) -> list[str]:
    """Split at sentence ends, keeping abbreviations such as 'Mr.' and 'Cr.P.C.' inside the sentence.

    Args:
        text: a paragraph

    Returns:
        Non-empty sentences in order.
    """
    out: list[str] = []
    start = 0
    for m in _SENTENCE_END.finditer(text):
        head = text[start : m.start()].rstrip()
        if _ABBREVIATIONS.search(head) or re.search(r"\b[A-Z]\.$", head):
            continue
        out.append(text[start : m.start()].strip())
        start = m.end()
    out.append(text[start:].strip())
    return [s for s in out if s]


def _paragraph_starts(text: str) -> list[int]:
    """Offsets of numbered-paragraph markers: at line starts, or inline after a sentence end when numbered in sequence."""
    line_starts = {m.start() for m in _NUMBERED_START.finditer(text)}
    candidates = sorted(line_starts | {m.end() for m in _INLINE_NUMBER.finditer(text)})
    starts: list[int] = []
    last: int | None = None
    for offset in candidates:
        number = _LEADING_NUMBER.match(text[offset:].lstrip())
        value = int(number.group(1)) if number else None
        if offset in line_starts or (value is not None and last is not None and value == last + 1):
            starts.append(offset)
            last = value
    return starts


def paragraph_number(block: str) -> int | None:
    """The source paragraph number a block starts with ('14. The court...' gives 14), or None."""
    m = _LEADING_NUMBER.match(block.lstrip())
    return int(m.group(1)) if m and int(m.group(1)) > 0 else None


def paragraph_blocks(text: str) -> list[str]:
    """Split an order into paragraph blocks: at numbered paragraphs, else at blank lines, else at single newlines.

    Args:
        text: whole order or one part of it

    Returns:
        Non-empty blocks in order (leading numbers are kept in the text).
    """
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    starts = _paragraph_starts(text)
    if starts:
        cuts = ([0] if starts[0] > 0 else []) + starts
        segments = [text[a:b] for a, b in zip(cuts, [*cuts[1:], len(text)], strict=True)]
    else:
        segments = [text]
    blocks: list[str] = []
    for segment in segments:
        for chunk in _BLANK_LINES.split(segment):
            blocks.extend(_split_at_sentence_newlines(chunk))
    return [re.sub(r"\s*\n\s*", " ", b).strip() for b in blocks if b.strip()]


def _split_at_sentence_newlines(text: str) -> list[str]:
    """Split a block at line breaks that follow a sentence end and precede a capital or number (not after 'Mr.' or 'P.S.')."""
    lines = text.split("\n")
    blocks: list[str] = [lines[0]]
    for line in lines[1:]:
        previous = blocks[-1].rstrip()
        starts_new = (
            bool(line.strip())
            and bool(re.search(r"[.!?:]$", previous))
            and bool(re.match(r"\s*[\"'(\[]?[A-Z0-9]", line))
            and not _ABBREVIATIONS.search(previous)
            and not re.search(r"\b[A-Z]\.$", previous)
        )
        blocks.append(line) if starts_new else blocks.__setitem__(-1, f"{blocks[-1]}\n{line}")
    return blocks


def normalise_date(value: Any) -> str | None:
    """Turn a date written in a common Indian court-record form into ISO 'YYYY-MM-DD'.

    Accepts ISO dates and date-times, 'dd-mm-yyyy', 'dd.mm.yyyy', 'dd/mm/yyyy', '12th March, 2023' and 'March 12, 2023'.

    Args:
        value: string, date, or anything else (gives None)

    Returns:
        ISO date, or None when the value is not a recognisable real date.
    """
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        return None
    s = value.strip()
    parts: tuple[int, int, int] | None = None
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        parts = (int(s[0:4]), int(s[5:7]), int(s[8:10]))
    elif m := _DMY_NUMERIC.match(s):
        parts = (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    elif m := _DMY_TEXT.match(s):
        mo = _MONTHS.get(m.group(2).lower())
        parts = (int(m.group(3)), mo, int(m.group(1))) if mo else None
    elif m := _MDY_TEXT.match(s):
        mo = _MONTHS.get(m.group(1).lower())
        parts = (int(m.group(3)), mo, int(m.group(2))) if mo else None
    if not parts:
        return None
    try:
        return date(*parts).isoformat()
    except ValueError:
        return None


def read_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield the JSON objects of a JSONL file, skipping blank and malformed lines.

    Args:
        path: file to read (UTF-8); a missing file gives nothing

    Returns:
        Iterator of dicts.
    """
    p = Path(path)
    if not p.is_file():
        return
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> int:
    """Write dicts as JSONL (UTF-8, non-ASCII kept), creating parent folders.

    Args:
        path: output file
        rows: objects to write

    Returns:
        Number of rows written.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            n += 1
    return n
