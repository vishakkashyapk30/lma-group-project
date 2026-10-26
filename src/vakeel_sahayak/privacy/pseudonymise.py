"""Rule and regex pseudonymisation after OCR, before text leaves the laptop (plan §16, §12).

Names become stable per-case aliases (Accused-1, Co-accused-1, Complainant-1, IO-1, Witness-1, Person-1). Detection is
rule based (titles, role words, 'S/o'), plus emails, phone numbers and ID numbers. Presidio and InLegalNER plug in
later through `register_detector`: a detector takes text and returns NameSpan objects, and its spans are merged with
the rules' spans. The alias map is local only: it is never written to the event log and never sent to Ada.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_ROLE_PREFIX = {
    "accused": "Accused",
    "co_accused": "Co-accused",
    "complainant": "Complainant",
    "io": "IO",
    "witness": "Witness",
    "person": "Person",
}
_ROLE_WORDS = {
    "co-accused": "co_accused", "co accused": "co_accused", "coaccused": "co_accused",
    "accused": "accused", "applicant": "accused", "petitioner": "accused",
    "complainant": "complainant", "informant": "complainant", "victim": "complainant",
    "investigating officer": "io", "i.o.": "io", "io": "io",
    "witness": "witness",
    "आरोपी": "accused", "अभियुक्त": "accused", "शिकायतकर्ता": "complainant", "गवाह": "witness",
}  # fmt: skip
_NAME = r"(?:(?:Mohd|Md)\.\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}"
_PERSON2 = r"(?:(?:Mohd|Md)\.\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}"  # two or more words: 'against State' is not a name
_HI_STOP = (
    "को|ने|से|का|की|के|में|पर|और|है|हैं|था|थी|थे|ही|भी|तो|यह|वह|ने|द्वारा|हेतु|एवं|तथा|के|लिए|कि|जो|जिसे|जिसने|उपस्थित"
)
_HI_NAME = rf"(?!(?:{_HI_STOP})(?![\u0900-\u097F]))[\u0900-\u097F]{{2,}}"
_HI_NAME3 = rf"{_HI_NAME}(?:[ \t]+{_HI_NAME}){{0,2}}"
_HI_NAME2 = rf"{_HI_NAME}(?:[ \t]+{_HI_NAME}){{1,2}}"
_POLICE = r"(?:Sub-Inspector|Inspector|Insp\.?|ASI|SI|SHO|DSP|ACP|DCP|Constable|Const\.?|Head Constable|HC)"
_TITLE = r"(?:Shri|Sri|Smt\.?|Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Km\.?|Kumari|Late)"
_NOT_NAME_WORD = (  # words of a High Court caption that start a title-case run but are not part of a name
    "Aged|Age|Years?|Caste|District|Distt|Police|Station|Village|Tahsil|Tehsil|Thana|Through|Versus|Page|State|Court|High|Hon|Honble|Resident|Presently|"
    "Occupation|Address|Applicant|Petitioner|Respondent|Accused|Appellant|Complainant|Chhattisgarh|Madhya|Pradesh|Uttar|Rajasthan|Gujarat|Bihar|Jharkhand|"
    "Himachal|Punjab|Haryana|Delhi|Karnataka|Kerala|Orissa|Odisha|Bombay|Madras|Calcutta|Allahabad|Patna|Gauhati|Lucknow|Bench|Nagpur|Indore|Gwalior|Jabalpur|Bilaspur"
)
_REL_MARK = r"(?:W/o|S/o|D/o|R/o|W/O|S/O|D/O|R/O|(?i:wife of|son of|daughter of)(?![a-z])|\balias\b|@)"
_REL_MARK_PERSON = r"(?:W/o|S/o|D/o|W/O|S/O|D/O|\s@\s)"  # markers that follow a person (not an address)
_CAPW = rf"(?!(?:{_NOT_NAME_WORD.upper()}|OCC|OCCUPATION|WORKING|PS|AGE|AGED|LATE|SHRI|SRI|SMT|MRS|MR|MS|DR|KUMARI|INFORMANT|SON|DAUGHTER|WIFE|HUSBAND)\b)[A-Z]{{3,}}"  # a capitals word that may belong to a name
_NAME_CAP = rf"{_CAPW}(?:[ \t]+{_CAPW}){{0,3}}"
_PATTERNS: list[tuple[re.Pattern[str], str | None]] = [  # most specific role first: the first span for a name wins
    (re.compile(rf"\b(?i:Investigating Officer|I\.O\.|IO)\b[\s,:-]*(?:{_TITLE}\s+)?({_NAME})"), "io"),
    (re.compile(rf"\b{_POLICE}\s+({_NAME})"), "io"),
    (re.compile(rf"\b(?i:S/o|D/o|W/o|son of|daughter of|wife of)\s*(?:{_TITLE}\s+){{0,2}}((?:[A-Z][a-z]+){{2}}(?![A-Za-z])|{_NAME})"), "person"),
    # a High Court caption names the party BEFORE the relation marker: 'Sadhna Kushwaha, W/o Late Rakesh Kushwaha', 'RAM SINGH S/O ...'; the name may be glued to the word before it ('ChhattisgarhSadhna Kushwaha')
    (re.compile(rf"(?<![A-Z])(?!(?:{_NOT_NAME_WORD})\b)(?:Late\s+)?((?:(?:Mohd|Md)\.?\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,2}})\s*,?\s*(?={_REL_MARK})"), "person"),
    (re.compile(rf"(?<![A-Za-z])(?!(?:{_NOT_NAME_WORD})\b)([A-Z][a-z]{{3,}})\s*,?\s*(?={_REL_MARK_PERSON})"), "person"),  # one word: 'Nitin S/o Rakesh'
    (re.compile(rf"(?<![A-Za-z])({_NAME_CAP})\s*,?\s*(?={_REL_MARK})"), "person"),
    (re.compile(rf"(?<![A-Za-z])(?!(?:{_NOT_NAME_WORD})\b)((?:[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+){{0,2}})|{_NAME_CAP})[ \t]*,?[ \t]*(?=(?i:aged?)\b[ \t.:]*(?:(?i:about)[ \t]*)?\d)"), "person"),  # 'AJMAL SHAH,AGED 19 YEARS'
    (re.compile(rf"(?:(?i:[SDW]/o)\.?|\b(?i:son of|daughter of|wife of)(?![a-z]))[ \t]*(?:(?:Late|LATE|SHRI|SRI|SMT\.?|Shri|Sri|Smt\.?|Mrs?\.?|MRS?\.?)[ \t]+){{0,2}}({_NAME_CAP})"), "person"),  # 'S/O PARVAT SINGH LODHI'
    (re.compile(rf"(?:\b(?i:alias)|@)\s*(?:{_TITLE}\s+)?({_NAME}|{_NAME_CAP})"), "person"),
    (re.compile(rf"\b(?i:co-accused|accused|complainant|informant|witness|surety)\b(?:\s+(?:is|was|are|were))?[\s,:-]+(?:{_TITLE}\s+)?({_NAME})"), None),
    (re.compile(rf"\b(?i:against|versus|vs?\.)\s+(?:{_TITLE}\s+)?({_PERSON2}|{_HI_NAME2})"), None),
    (re.compile(rf"(?<![\u0900-\u097F])({_HI_NAME2})(?=['\u2019]s\b)"), None),
    (re.compile(r"(?<![\w'])(?!(?:The|This|That|State|Hon|Honourable|Learned)\b)((?:(?:Mohd|Md)\.\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?=['\u2019]s\b)"), None),
    (re.compile(rf"\b{_TITLE}\s+({_NAME})"), None),
    (re.compile(rf"\b(?i:justice)\s+({_NAME})"), None),  # 'Justice Rajesh Kumar' (title-case judge)
    # 'JUSTICE RATNAKER BHENGRA' in capitals, also when a line break was lost and the name is glued to the next heading word ('SHARANORAL')
    (re.compile(r"\bJUSTICE[ \t]+(?!ORAL|ORDER|JUDGMENT|CAV)([A-Z]{2,}?(?:[ .]+[A-Z]{2,}?){0,3}?)(?=ORAL|CAV|JUDGMENT|ORDER|[ \t]*(?:[\n,]|$))", re.MULTILINE), None),
    (re.compile(rf"(?:श्री|श्रीमती|सुश्री|कुमारी|आरोपी|अभियुक्त|शिकायतकर्ता|गवाह|(?i:accused|complainant|witness|surety))[ \t,:-]+({_HI_NAME3})"), None),
]
_PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)"), "[PHONE]"),
    (re.compile(r"(?<!\d)(?<![A-Z]{4})\d{4}\s?\d{4}\s?\d{4}(?!\d)"), "[ID-NUMBER]"),  # not the 12 digits of a court-order id such as HPHC010225332022
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[ID-NUMBER]"),
]
_ROLE_CONTEXT = 80  # characters either side of a name searched for a role word


@dataclass(frozen=True)
class NameSpan:
    """A detected personal name: [start, end) in the text and the role it plays."""

    start: int
    end: int
    role: str = "person"

    def text_of(self, text: str) -> str:
        """The name as written."""
        return text[self.start : self.end]


NameDetector = Callable[[str], list[NameSpan]]
_DETECTORS: list[NameDetector] = []


def register_detector(detector: NameDetector) -> None:
    """Add a name detector (for example a Presidio or InLegalNER wrapper); its spans join the rule-based ones."""
    _DETECTORS.append(detector)


def clear_detectors() -> None:
    """Remove all registered detectors."""
    _DETECTORS.clear()


def normalise_role(role: str) -> str:
    """Map a role word ('co-accused', 'Investigating Officer') to a key of the alias prefixes."""
    low = role.strip().lower().replace("_", " ")
    key = _ROLE_WORDS.get(low) or _ROLE_WORDS.get(low.replace("-", " "))
    return key or (low.replace(" ", "_") if low.replace(" ", "_") in _ROLE_PREFIX else "person")


def _key(name: str) -> str:
    """Case- and spacing-insensitive identity of a name."""
    return " ".join(name.split()).casefold()


class PseudonymMap:
    """Alias <-> real-name map. Stored on the laptop only; never sent to Ada."""

    def __init__(self) -> None:
        """Create an empty map."""
        self._alias_by_key: dict[str, str] = {}
        self._names: dict[str, str] = {}  # alias -> first-seen spelling of the real name
        self._counts: dict[str, int] = {}

    def alias_for(self, name: str, role: str) -> str:
        """Stable alias: the same name always gets the same alias, whatever the role of later mentions.

        Args:
            name: real name as written
            role: accused, co_accused, complainant, io, witness, or anything else for 'Person'

        Returns:
            Alias.
        """
        key = _key(name)
        if key in self._alias_by_key:
            return self._alias_by_key[key]
        prefix = _ROLE_PREFIX[normalise_role(role)]
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        alias = f"{prefix}-{self._counts[prefix]}"
        self._alias_by_key[key] = alias
        self._names[alias] = " ".join(name.split())
        return alias

    def known_names(self) -> list[str]:
        """Real names held in the map, longest first. Local use only (the boundary check)."""
        return sorted(self._names.values(), key=len, reverse=True)

    def aliases(self) -> list[str]:
        """The aliases issued so far."""
        return list(self._names)

    def apply(self, text: str) -> str:
        """Replace every known name in `text` with its alias (longest names first, whole words, any case)."""
        for name in self.known_names():
            alias = self._alias_by_key[_key(name)]
            pattern = r"(?<!\w)" + r"\s+".join(re.escape(p) for p in name.split()) + r"(?!\w)"
            text = re.sub(pattern, alias, text, flags=re.IGNORECASE)
        return text

    def restore(self, text: str) -> str:
        """Fill real names back in on counsel's machine only (plan §8.2 cause title).

        Args:
            text: see behaviour

        Returns:
            Text with aliases replaced by real names.
        """
        for alias in sorted(self._names, key=len, reverse=True):
            text = re.sub(rf"(?<![\w-]){re.escape(alias)}(?![\w])", lambda _m, a=alias: self._names[a], text)
        return text

    def to_dict(self) -> dict[str, dict[str, str] | dict[str, int]]:
        """JSON-able form for local persistence."""
        return {"names": dict(self._names), "counts": dict(self._counts)}

    @classmethod
    def from_dict(cls, data: dict) -> PseudonymMap:
        """Rebuild a map from `to_dict` output."""
        out = cls()
        out._names = dict(data.get("names", {}))
        out._counts = dict(data.get("counts", {}))
        out._alias_by_key = {_key(n): a for a, n in out._names.items()}
        return out


def _map_path(case_id: str, cases_dir: str | None) -> Path:
    """Local file holding a case's alias map."""
    from vakeel_sahayak.config import load_config
    from vakeel_sahayak.schemas.ids import check_case_id

    return Path(cases_dir or load_config().paths.cases_dir) / check_case_id(case_id) / "pseudonyms.json"


def load_map(case_id: str, cases_dir: str | None = None) -> PseudonymMap:
    """Load a case's alias map from the laptop (empty if none yet)."""
    path = _map_path(case_id, cases_dir)
    return PseudonymMap.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else PseudonymMap()


def save_map(case_id: str, mapping: PseudonymMap, cases_dir: str | None = None) -> Path:
    """Write a case's alias map next to its raw files (laptop only)."""
    path = _map_path(case_id, cases_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def _role_near(text: str, start: int, end: int) -> str:
    """Role of the nearest role word within the context window, else 'person'."""
    window_start = max(0, start - _ROLE_CONTEXT)
    best: tuple[int, str] | None = None
    for word, role in sorted(_ROLE_WORDS.items(), key=lambda kv: -len(kv[0])):
        for m in re.finditer(
            rf"(?<![\w-]){re.escape(word)}(?![\w-])", text[window_start : end + _ROLE_CONTEXT], re.IGNORECASE
        ):
            pos = window_start + m.start()
            dist = min(abs(pos - start), abs(pos - end))
            if best is None or dist < best[0]:
                best = (dist, role)
    return best[1] if best else "person"


_NOT_A_PERSON = re.compile(
    r"(?i)^(?:the\s+)?state(?:\s+of\b.*)?$|^nos?\.?$|^(?:hon'?ble\s+)?(?:mr\.?\s+)?(?:justice|judge|court|magistrate)$|^(?:union\s+of\s+india|vs?\.?|versus|against|for\s+(?:the\s+)?(?:petitioners?|appellants?|respondents?|applicants?|state|accused))$"
)  # 'The State' (a party of every bail order), a bare 'Vs', 'For Petitioner' are not people


_ALIAS_AT = re.compile(r"(?:Co-accused|Accused|Complainant|IO|Witness|Person)-\d+\b", re.IGNORECASE)  # text that is already an alias is not a name


_EDGE_STOP = frozenset(
    "aged age years year resident residing petitioner petitioners respondent applicant accused appellant son daughter wife for at present and another anr "
    "ors vs versus the state represented police station of through by in no caste occupation".split()
)  # words of a caption that a title-case run picks up at its ends without being part of the name ('Anil Gupta For', 'Amrit Tiwari Aged', 'At Present')


def _trim_edges(text: str, start: int, end: int) -> tuple[int, int]:
    """Shrink [start, end) so it neither starts nor ends on a caption word; (start, start) when nothing but such words is left."""
    words = [(m.start() + start, m.end() + start) for m in re.finditer(r"\S+", text[start:end])]
    while words and text[words[-1][0] : words[-1][1]].strip(".,;:").casefold() in _EDGE_STOP:
        words.pop()
    while words and text[words[0][0] : words[0][1]].strip(".,;:").casefold() in _EDGE_STOP:
        words.pop(0)
    return (words[0][0], words[-1][1]) if words else (start, start)


def detect_names(text: str) -> list[NameSpan]:
    """Rule-based name spans (titles, police ranks, relations, role words) plus any registered detectors' spans."""
    spans: list[NameSpan] = []
    seen: set[tuple[int, int]] = set()
    for pattern, fixed_role in _PATTERNS:
        for m in pattern.finditer(text):
            if _NOT_A_PERSON.match(" ".join(m.group(1).split())):  # 'State Of Chhattisgarh' is judged whole, before caption words are trimmed off its ends
                continue
            s, e = _trim_edges(text, *m.span(1))
            if e > s and (s, e) not in seen and not _NOT_A_PERSON.match(" ".join(text[s:e].split())) and not _ALIAS_AT.match(text, s):
                seen.add((s, e))
                spans.append(NameSpan(s, e, fixed_role or _role_near(text, s, e)))
    for detector in _DETECTORS:
        spans.extend(detector(text))
    return spans


def pseudonymise_text(text: str, case_id: str, mapping: PseudonymMap | None = None) -> tuple[str, PseudonymMap]:
    """Replace names with roles (Accused-1, Co-accused-1, Complainant-1, IO-1) (plan §4.4).

    Args:
        text: see behaviour
        case_id: see behaviour (kept for the caller's bookkeeping; aliases are per map)
        mapping: existing alias map for the case

    Returns:
        Pseudonymised text and the (local-only) map.
    """
    mapping = mapping if mapping is not None else PseudonymMap()
    spans = sorted(detect_names(text), key=lambda s: s.start)
    for span in spans:
        mapping.alias_for(span.text_of(text), span.role)
    for span in reversed(spans):  # a name glued to the next word ('SHARANORAL') gets a space so the whole-word replacement can find it
        if span.end < len(text) and text[span.end].isalnum() and text[span.end - 1].isalnum():
            text = text[: span.end] + " " + text[span.end :]
    text = _split_glued_before(text, mapping)
    out = mapping.apply(text)
    out = _sweep_name_tokens(out, mapping)
    for pattern, token in _PII:
        out = pattern.sub(token, out)
    return out, mapping


def _split_glued_before(text: str, mapping: PseudonymMap) -> str:
    """Put a space before a learned name written glued to a lowercase word ('ChhattisgarhSadhna Kushwaha'), so the whole-word replacement can find it.

    Only a capitalised spelling of the name that follows a lowercase letter and starts a word of at least three letters (four for a one-word name) is split, so a short single name
    inside a longer word is never cut, and the rest of the text is untouched."""
    for name in mapping.known_names():
        words = name.split()
        if len(words[0]) < (3 if len(words) > 1 else 4):
            continue
        tail = re.escape(words[0][1:]) + "".join(r"\s+" + re.escape(w) for w in words[1:])
        text = re.sub(rf"(?<=[a-z\d])(?=[{re.escape(words[0][0].upper())}](?i:{tail})(?!\w))", " ", text)
    return text


_COMMON_NAME_TOKENS = frozenset(
    "state court india indian high police station district village shri smt late kumar kumari devi singh begum bai the and for with "
    "bail order case accused applicant petitioner respondent complainant person".split()
)  # tokens too common in legal text (or too generic) to be removed on their own


def leaked_name_tokens(text: str, mapping: PseudonymMap) -> list[str]:
    """Consistency check: the tokens (three letters or more) of every learned name that still appear in `text`, whole word, any case."""
    out: list[str] = []
    for name in mapping.known_names():
        for tok in re.findall(r"[^\W\d_]{3,}", name):
            if tok.casefold() not in {t.casefold() for t in out} and re.search(rf"(?<!\w){re.escape(tok)}(?!\w)", text, re.IGNORECASE):
                out.append(tok)
    return out


def _sweep_name_tokens(text: str, mapping: PseudonymMap) -> str:
    """Second sweep: a learned name written only in part ('Kushwaha' after 'Sadhna Kushwaha' was replaced as a whole) still points to the person.

    A token of a learned name that survives replacement is replaced by that name's alias when it is capitalised in the text (so a lowercase common
    word is left alone), is not a title, place or common name particle, and is not a token of a legal term (it appears in no lowercase form in the text).
    A repeated alias made this way ('Person-5 Person-5') collapses to one."""
    for name in mapping.known_names():
        alias = mapping._alias_by_key[_key(name)]  # noqa: SLF001
        for tok in re.findall(r"[^\W\d_]{4,}", name):
            if tok.casefold() in _COMMON_NAME_TOKENS or re.search(rf"(?<!\w){re.escape(tok.lower())}(?!\w)", text):
                continue
            text = re.sub(rf"(?<![\w-])(?-i:{re.escape(tok)}|{re.escape(tok.upper())})(?![\w-])", alias, text)
        text = re.sub(rf"({re.escape(alias)})(?:\s+\1)+(?![\w-])", r"\1", text)
    return text
