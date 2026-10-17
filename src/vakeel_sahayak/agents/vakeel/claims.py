"""Claim text: sentences with `[F:field]` / `[A:doc#para]` markers, the "per counsel" label and the notes Vakeel adds (plan §8.1).

A claim (a ground's argument or a reply) is a run of sentences. Each sentence carries the markers of what supports it.
Vakeel adds two kinds of sentence itself and never asks the model for them: the label on a USER_STATED fact
(`PER_COUNSEL`, inserted into the sentence) and *notes* (a qualification of a CHANGED or DISTINGUISHED precedent, a
warning on an overruled one), which start with `Qualification:` or `Warning:`. A note says something about a
precedent's reach, not about what the paragraph holds, so it is not run through the NLI check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from vakeel_sahayak.agents.vakeel.facts import PER_COUNSEL
from vakeel_sahayak.tools.drafting.claims import parse_ref

MARKER = re.compile(r"\[\s*(F|A)\s*:\s*([^\]]+?)\s*\]")
_MOVE_BACK = re.compile(r"([.!?])\s*((?:\[\s*(?:F|A)\s*:[^\]]+\]\s*)+)")
NOTE_PREFIXES = ("Qualification:", "Warning:")
_LABEL = re.compile(r"\s*\(\s*" + re.escape(PER_COUNSEL) + r"\s*\)", re.IGNORECASE)


def _tidy(text: str) -> str:
    """Spaces collapsed, none left before punctuation where a marker was taken out."""
    return re.sub(r"\s+([.,;:!?])", r"\1", re.sub(r"\s+", " ", text)).strip(" ,;")


@dataclass
class Sentence:
    """One sentence of a claim: its text (markers included) and what it cites."""

    text: str
    facts: list[str] = field(default_factory=list)
    auths: list[tuple[str, int]] = field(default_factory=list)
    bad_refs: list[str] = field(default_factory=list)  # markers that do not parse ('[A:nonsense]')
    inherited: bool = False  # no marker in the whole claim: the authorities the model listed stand for the references

    @property
    def is_note(self) -> bool:
        """A qualification or warning Vakeel wrote itself (not checked against a source)."""
        return self.text.lstrip().startswith(NOTE_PREFIXES)

    @property
    def cited(self) -> bool:
        return bool(self.facts or self.auths)

    @property
    def plain(self) -> str:
        """The text without markers and without the per-counsel label."""
        return _tidy(_LABEL.sub("", MARKER.sub("", self.text)))

    @property
    def readable(self) -> str:
        """The text without markers but with the per-counsel label (what counsel reads on the card)."""
        return _tidy(MARKER.sub("", self.text))

    def check_refs(self) -> list[str]:
        """The references as `check_claim` takes them: 'F:field' and 'A:doc#para'."""
        return [f"F:{f}" for f in self.facts] + [f"A:{d}#{p}" for d, p in self.auths]

    def refs(self) -> list[str]:
        """The markers in the sentence as '[F:field]' / '[A:doc#para]' strings, in order, without repeats."""
        out: list[str] = []
        for kind, body in MARKER.findall(self.text):
            ref = f"[{kind}:{body.strip()}]"
            if ref not in out:
                out.append(ref)
        return out


def strip_label(text: str) -> str:
    """The text without the per-counsel label (a provenance note, not a claim to check)."""
    return _LABEL.sub("", text)


def split_claim(text: str, default_auths: list[tuple[str, int]] | None = None) -> list[Sentence]:
    """Split a claim into sentences with their markers (a marker standing alone belongs to the sentence before it).

    Args:
        text: the claim
        default_auths: authorities the model listed beside the text; when the text carries no marker at all they are the
            references of every sentence (the check then reads them as `refs`, plan §8.1)
    """
    from vakeel_sahayak.pipelines.text_utils import split_sentences

    text = _MOVE_BACK.sub(lambda m: " " + m.group(2).strip() + m.group(1), (text or "").strip())
    out: list[Sentence] = []
    for raw in split_sentences(text) or ([text] if text.strip() else []):
        raw = raw.strip()
        has_words = bool(re.search(r"\w", MARKER.sub("", raw)))
        if not has_words and out:
            out[-1].text += " " + raw
            _read_refs(out[-1])
            continue
        if raw:
            s = Sentence(raw)
            _read_refs(s)
            out.append(s)
    if default_auths and out and not MARKER.search(text):
        for s in out:
            if not s.is_note:
                s.auths, s.inherited = list(default_auths), True
    return out


def _read_refs(s: Sentence) -> None:
    s.facts, s.auths, s.bad_refs = [], [], []
    for kind, body in MARKER.findall(s.text):
        ref = f"[{kind}:{body.strip()}]"
        try:
            k, name, para = parse_ref(ref)
        except ValueError:
            s.bad_refs.append(ref)
            continue
        if k == "F" and name not in s.facts:
            s.facts.append(name)
        elif k == "A" and (name, int(para or 0)) not in s.auths:
            s.auths.append((name, int(para or 0)))


def join_claim(sentences: list[Sentence]) -> str:
    """The claim text again, one space between sentences."""
    return " ".join(s.text.strip() for s in sentences if s.text.strip())


def as_sentence(text: str) -> Sentence:
    """A single Sentence from text (markers read)."""
    s = Sentence(text.strip())
    _read_refs(s)
    return s


def add_label(s: Sentence, user_fields: set[str]) -> bool:
    """Put the per-counsel label into a sentence that cites a USER_STATED field (before its first marker). True when added."""
    if not (set(s.facts) & user_fields) or PER_COUNSEL in s.text.lower():
        return False
    m = MARKER.search(s.text)
    head, tail = (s.text[: m.start()].rstrip(" ,;"), s.text[m.start():]) if m else (s.text.rstrip(), "")
    ended = re.search(r"[.!?]$", head)
    head = head[:-1] if ended and not tail else head
    s.text = f"{head} ({PER_COUNSEL})" + (f" {tail}" if tail else ("." if ended else ""))
    return True


def note(prefix: str, body: str, auths: list[tuple[str, int]]) -> Sentence:
    """A note sentence ('Qualification: ...' / 'Warning: ...') that names the authority it is about by its marker."""
    marks = " ".join(f"[A:{d}#{p}]" for d, p in auths)
    s = Sentence(f"{prefix} {body.rstrip('.')} {marks}.".replace("  ", " ").strip())
    _read_refs(s)
    return s
