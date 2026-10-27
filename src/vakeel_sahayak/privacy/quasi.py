"""Quasi-identifiers and dates on the wire to an external model (plan §16): detection, consistent aliases, one per-case date shift.

Names are replaced at intake (`privacy.pseudonymise`). A name scrubber alone leaves a client re-identifiable: an FIR number with its police
station finds the case on a public portal, and a village, a vehicle number or an account number points to one person. This module covers
those categories. It works on the text that leaves the laptop for a hosted model, not on the local copy:

* **Where it runs.** `WireCodec.encode` is applied by the hosted model clients (`models.openai.adapters`, `models.sarvam.adapters`) to every
  message of a `CLIENT_TEXT` call, right before the privacy gate (`models.sarvam.policy.authorize`) checks it; `WireCodec.decode` turns the
  reply back. The case shelf, the dossier, the Rights Radar and every date tool keep the real values, so nothing local changes, and the
  offline stand-ins never see this module (default runs stay byte-identical).
* **Quasi-identifiers** (`CATEGORIES`): FIR numbers and case or crime numbers (the number is replaced, the year is kept: the year carries the
  legal regime, IPC or BNS, and alone it identifies nobody), police-station names, villages, mohallas, roads and other localities, residence
  addresses after `R/o`, house numbers, PIN codes, vehicle registration numbers, bank account numbers, IFSC codes, UPI handles, Aadhaar
  (also masked forms), PAN, passport, voter-ID and driving-licence numbers, emails, mobile and landline numbers, exact dates of birth,
  and ages (replaced by an alias that carries the age band, so the model still knows a client is, say, 18 to 25). Each distinct value gets one
  alias per case (`[FIR-1]`, `[PS-1]`, `[PLACE-2]`, `[AGE-1 18-25]`), held in the case's `PseudonymMap`, so the same value always reads the
  same and the reply can be restored.
* **What stays.** Section numbers, act names, court names, districts, states and tahsils (coarse places that the court name already
  gives away), and the year of an FIR. Judges' names are handled by the name rules as before.
* **Dates are shifted, never masked.** Custody days, s.479 BNSS, the 60/90-day default-bail clock and limitation all need dates. Every date in
  the outbound text (`16.02.2024`, `16/02/2024`, `16-02-24`, `2024-02-16`, `16th February, 2024`, `16-Feb-2024`, `February 16, 2024`,
  `2nd day of March 2023`) is moved by ONE per-case number of days (`PseudonymMap.date_shift_days`, a negative multiple of 7 between
  -182 and -28, so every interval and every weekday is preserved) and written back in its own format. The reply is shifted back: first by
  an exact table of the strings this call sent, then arithmetically for dates the model computed (an interval it added to a shifted date
  comes back right). Dates are never shifted in the local copy, so the date arithmetic of the dossier and Rights Radar runs on real dates.
  Limitation (documented in docs/handoff/privacy-hardening-2026-10-27.md): a fixed legal date the model brings from its own knowledge (BNSS in
  force from 1 July 2024) is not shifted on the way out, so the model may misplace a shifted date relative to it; regime decisions are made
  locally by the dossier and the Rights Radar, never by the hosted model.

`find_quasi` is the check the boundary uses (`privacy.boundary.assert_pseudonymised(..., wire=True)`): it lists the categories still present.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Callable
from typing import Any

# ------------------------------------------------------------------------------------------------ dates
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
_MON = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_DATE_BODY = (
    r"(?P<dmy>(?<![\d./])(?P<d1>\d{1,2})(?P<s1>[./-])(?P<m1>\d{1,2})(?P=s1)(?P<y1>(?:19|20)\d{2})(?![\d/]|\.\d(?!\.\s?[A-Z])))"  # a range '09.04.2025-10.04.2025' and a list number glued after it ('02.07.2024.2.The') still count
    r"|(?P<dmy2>(?<![\d./-])(?P<d4>\d{1,2})(?P<s4>[.-])(?P<m4>\d{1,2})(?P=s4)(?P<y4>\d{2})(?![\d/-]|\.\d))"
    r"|(?P<iso>(?<![\d-])(?P<y2>(?:19|20)\d{2})-(?P<m2>\d{2})-(?P<d2>\d{2})(?![\d-]))"
    rf"|(?P<dmon>(?<!\d)(?P<d3>\d{{1,2}})(?P<o3>st|nd|rd|th)?(?P<g3>\s*(?:day\s+of\s+)?|[\s-]+)(?P<mon3>{_MON})(?![a-z])(?P<dot3>\.?)(?P<g3b>[\s,-]+)(?P<y3>(?:19|20)\d{{2}})(?!\d))"
    rf"|(?P<mond>(?<![A-Za-z])(?P<mon5>{_MON})(?![a-z])(?P<dot5>\.?)(?P<g5>\s+)(?P<d5>\d{{1,2}})(?P<o5>st|nd|rd|th)?(?P<g5b>,?\s*)(?P<y5>(?:19|20)\d{{2}})(?!\d))"
)
DATE_RE = re.compile(_DATE_BODY, re.IGNORECASE)
SHIFT_RANGE = (-182, -28)  # days; negative multiples of 7 (weekday kept)


def _month_of(token: str) -> int:
    low = token.lower().rstrip(".")
    for i, name in enumerate(_MONTHS):
        if name.startswith(low[:3]):
            return i + 1
    raise ValueError(token)


def _style_month(orig: str, month: int) -> str:
    name = _MONTHS[month - 1]
    full = len(orig) > 4 or orig.lower() in ("june", "july")
    out = name if full else ("sept" if month == 9 and orig.lower() == "sept" else name[:3])
    if orig.isupper():
        return out.upper()
    return out.capitalize() if orig[:1].isupper() else out


def _ordinal(day: int, orig: str) -> str:
    suf = "th" if 11 <= day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return suf.upper() if orig.isupper() else suf


def _num(value: int, orig: str) -> str:
    return f"{value:02d}" if len(orig) == 2 else str(value)


def _parts(m: re.Match[str]) -> tuple[str, int, int, int]:
    """(form, day, month, year) of a date match."""
    if m.group("dmy"):
        return "dmy", int(m.group("d1")), int(m.group("m1")), int(m.group("y1"))
    if m.group("dmy2"):
        yy = int(m.group("y4"))
        return "dmy2", int(m.group("d4")), int(m.group("m4")), (1900 + yy) if yy > 50 else (2000 + yy)
    if m.group("iso"):
        return "iso", int(m.group("d2")), int(m.group("m2")), int(m.group("y2"))
    if m.group("dmon"):
        return "dmon", int(m.group("d3")), _month_of(m.group("mon3")), int(m.group("y3"))
    return "mond", int(m.group("d5")), _month_of(m.group("mon5")), int(m.group("y5"))


_GROUPS = {"dmy": ("d1", "m1", "y1", None, None), "dmy2": ("d4", "m4", "y4", None, None), "iso": ("d2", "m2", "y2", None, None),
           "dmon": ("d3", None, "y3", "mon3", "o3"), "mond": ("d5", None, "y5", "mon5", "o5")}  # fmt: skip


def shift_date_match(m: re.Match[str], days: int) -> str:
    """The matched date moved by `days`, written in the same format (separators, zero padding, month style, ordinal); unchanged when invalid."""
    try:
        form, d, mo, y = _parts(m)
        new = _dt.date(y, mo, d) + _dt.timedelta(days=days)
    except ValueError:
        return m.group(0)
    gd, gm, gy, gmon, gord = _GROUPS[form]
    base = m.start()
    text = m.group(0)
    edits: list[tuple[int, int, str]] = [(m.start(gd) - base, m.end(gd) - base, _num(new.day, m.group(gd)))]
    if gm:
        edits.append((m.start(gm) - base, m.end(gm) - base, _num(new.month, m.group(gm))))
    if gmon:
        edits.append((m.start(gmon) - base, m.end(gmon) - base, _style_month(m.group(gmon), new.month)))
    if gord and m.group(gord):
        edits.append((m.start(gord) - base, m.end(gord) - base, _ordinal(new.day, m.group(gord))))
    year = f"{new.year % 100:02d}" if len(m.group(gy)) == 2 else str(new.year)
    edits.append((m.start(gy) - base, m.end(gy) - base, year))
    for s, e, rep in sorted(edits, reverse=True):
        text = text[:s] + rep + text[e:]
    return text


def shift_dates(text: str, days: int, table: dict[str, str] | None = None) -> str:
    """Every date of `text` moved by `days`; `table` (when given) records shifted string -> original string."""

    def one(m: re.Match[str]) -> str:
        out = shift_date_match(m, days)
        if table is not None and out != m.group(0):
            table.setdefault(out, m.group(0))
        return out

    return DATE_RE.sub(one, text)


def unshift_dates(text: str, days: int, table: dict[str, str] | None = None) -> str:
    """The inverse of `shift_dates`: exact strings of `table` first, else the date moved back by `days`."""

    def one(m: re.Match[str]) -> str:
        if table and m.group(0) in table:
            return table[m.group(0)]
        return shift_date_match(m, -days)

    return DATE_RE.sub(one, text)


def deterministic_shift(key: str) -> int:
    """A shift computed from `key`: only for public-source evaluation cases (reproducible runs, cache hits); production cases draw a random one."""
    import hashlib

    lo, hi = SHIFT_RANGE[0] // 7, SHIFT_RANGE[1] // 7
    n = int(hashlib.sha256(f"vs-date-shift|{key}".encode()).hexdigest(), 16)
    return (lo + n % (hi - lo + 1)) * 7


def random_shift() -> int:
    """A random shift for a production case (drawn once, stored in its PseudonymMap)."""
    import secrets

    lo, hi = SHIFT_RANGE[0] // 7, SHIFT_RANGE[1] // 7
    return (lo + secrets.randbelow(hi - lo + 1)) * 7


# ------------------------------------------------------------------------------------------------ quasi-identifiers
_W = r"[A-Z][A-Za-z]+"  # one capitalised word of a place name (capitals included: 'KALER')
_PLACE_STOP = (
    "District|Distt|Dist|Tahsil|Tehsil|Taluka|Mandal|Police|Thana|Post|PS|P|Under|In|Of|And|At|On|For|The|Village|Vill|Aged|Age|Case|Crime|"
    "Registered|Dated|Dt|Sector|State|Through|Petitioner|Respondent|Applicant|Accused|Complainant|Versus|Vs|Also|Presently|Resident|"
    "Officer|Officers|Incharge|SHO|SI|Act|Staff|Personnel|Records?|Diary|Limits|Jurisdiction|CaseNo|Person|Witness|IO|Co"
)  # caption and police words that are never the name of a place (also the alias words 'Person-1', 'Accused-2')
_GLUE = r"(?:\b|(?<=R/O)|(?<=R/o)|(?<=of)|(?<=OF)|(?<=[a-z])(?=[A-Z]))"  # a label glued to the word before it by OCR ('R/OMOHALLA', 'ofVillage', 'atD.No.')
_PLACE_RUN = rf"(?!(?i:{_PLACE_STOP})\b){_W}(?:[ \t]+(?!(?i:{_PLACE_STOP})\b){_W}){{0,2}}"
_PS_WORD = rf"(?!(?i:{_PLACE_STOP.replace('Town|City|', '')})\b){_W}"  # a word of a station name written before 'Police Station' ('Karwar Town Police Station')
_GLUED_TAIL = re.compile(r"(?<=[a-z])(?:District|Distt|Dist|Tahsil|Tehsil|Thana|Mandal|Police|Post|State|Under|Registered)[A-Za-z]*$")
_STATE_CODES = "AN|AP|AR|AS|BR|CG|CH|DD|DL|DN|GA|GJ|HP|HR|JH|JK|KA|KL|LA|LD|MH|ML|MN|MP|MZ|NL|OD|OR|PB|PY|RJ|SK|TN|TR|TS|UK|UP|WB"
_DATE_PLAIN = DATE_RE.pattern.replace("?P<", "?:<").replace("(?P=s1)", r"[./-]").replace("(?P=s4)", r"[.-]")
_DATE_PLAIN = re.sub(r"\(\?:<\w+>", "(?:", _DATE_PLAIN)
_CASE_LABEL = (
    r"(?:Crime|Cr\.?|C\.\s?R\.?|Case|P\.?\s?S\.?\s+Case|G\.?\s?R\.?|Crl\.?\s*M\.?\s*[CP]\.?|Crl\.?\s*(?:A|Rev|Misc|M|Appeal|Revision)\.?|B\.?\s?A\.?|"
    r"BAIL\s*APPL(?:ICATION)?\.?|Bail\s+Appl(?:ication)?\.?|M\.?\s*Cr\.?\s*C\.?|CRM-M|CRR|Cr\.?\s*Misc\.?|Sessions\s+(?:Case|Trial)|S\.\s?C\.?|S\.\s?T\.?|"
    r"Spl\.?\s*(?:Case|Trial)|Special\s+(?:Case|Trial)|Complaint\s+Case|C\.\s?C\.?|Application|Petition|Appeal|Revision|Trial|Suit|"
    r"Cr\.?\s*M\.?\s*P\.?|Cr\.?\s*R\.?\s*P\.?|Cr\.?\s*A\.?|A\.?\s*B\.?\s*A\.?|W\.?\s*P\.?(?:\s*\(\s*Crl\.?\s*\))?|"
    r"(?:[A-Z][A-Za-z]{0,4}\.\s?(?:\(\s?[A-Z][a-z]*\.?\s?\)\s?)?){2,5})"
)

# (category, pattern with group 'v' = the value to replace, key function (match -> identity of the value), band function or None)
_Q: list[tuple[str, re.Pattern[str]]] = [
    ("DOB", re.compile(rf"(?i:\bD\.?\s?O\.?\s?B\.?|\bdate\s+of\s+birth|\bborn\s+on)\s*(?:is\s*)?[:.\-]?\s*(?P<v>{_DATE_PLAIN})")),
    ("UPI", re.compile(r"(?<![\w.])(?P<v>[\w.-]{2,64}@(?:ybl|ibl|axl|apl|upi|paytm|okaxis|oksbi|okhdfcbank|okicici|icici|sbi|hdfcbank|axisbank|kotak|airtel|"
                       r"jio|fbl|pnb|barodampay|boi|cnrb|ubi|idfcbank|yesbank|aubank|indus|federal|rbl|dbs|freecharge|ikwik|waicici|wahdfcbank|waaxis|wasbi))(?![\w.@])", re.IGNORECASE)),
    ("EMAIL", re.compile(r"(?P<v>[\w.+-]+@[\w-]+\.[\w.-]*\w)")),
    ("VEHICLE", re.compile(rf"\b(?P<v>(?:{_STATE_CODES})[ -]?\d{{1,2}}[ -]?[A-Z]{{1,3}}[ -]?\d{{4}}|\d{{2}}[ -]?BH[ -]?\d{{4}}[ -]?[A-Z]{{1,2}})\b")),
    ("DL", re.compile(rf"\b(?P<v>(?:{_STATE_CODES})[ -]?\d{{2}}[ -]?(?:19|20)\d{{2}}[ -]?\d{{7}})\b|(?i:driving\s+licen[cs]e|\bD\.\s?L\.?)\s*(?i:No|Number)\.?\s*[:.\-]?\s*(?P<v2>[A-Z0-9][A-Z0-9 /-]{{6,20}}[0-9])")),
    ("IFSC", re.compile(r"\b(?P<v>[A-Z]{4}0[A-Z0-9]{6})\b")),
    ("PAN", re.compile(r"\b(?P<v>[A-Z]{5}\d{4}[A-Z])\b")),
    ("VOTER-ID", re.compile(r"\b(?P<v>[A-Z]{3}\d{7})\b")),
    ("PASSPORT", re.compile(r"\b(?P<v>[A-Z]\d{7})\b|(?i:passport)\s*(?i:No|Number)?\.?\s*[:.\-]?\s*(?P<v2>[A-Z]\d{7})")),
    ("ACCOUNT", re.compile(r"(?i:\bA/c|\bAccount|\bAcct?\.?)\s*(?i:No|Number|Nos)?\.?\s*[:.#\-]?\s*(?P<v>\d[\d -]{7,22}\d)(?!\d)")),
    ("AADHAAR", re.compile(r"(?<![\da-f]{2})(?<!\d)(?<![A-Z]{4})(?P<v>\d{4}\s?\d{4}\s?\d{4})(?![\da-f])|(?P<v2>\b[Xx*]{4}[\s-]?[Xx*]{4}[\s-]?\d{4})\b")),
    ("PHONE", re.compile(r"(?<![\da-f]{2})(?<!\d)(?P<v>(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5})(?![\da-f])|(?<![\w-])(?P<v2>0\d{2,4}-\d{6,8})(?![\w-])")),
    ("FIR", re.compile(r"\b(?:F\.?\s?I\.?\s?R\.?|First\s+Information\s+Report)(?:[\s\]\[]*(?i:No|Number|Nos)\.?)?[\s\]\[:.#-]*(?P<v>\d{1,6})(?:[\s\]\[]*(?:/|-|of)[\s\]\[]*(?P<y>(?:19|20)\d{2}))?(?!\d)")),
    ("CASE", re.compile(rf"(?<![\w])(?i:{_CASE_LABEL})\s*(?i:No|Nos|Number)\.?\s*[:.#\-]?\s*(?P<v>\d{{1,7}})(?:\s*(?:/|-|of)\s*(?P<y>(?:19|20)\d{{2}}))?(?!\d)")),
    ("HOUSE", re.compile(rf"{_GLUE}(?i:H\.?\s?No|House\s+No|Flat\s+No|Plot\s+No|Quarter\s+No|Qr\.?\s*No|Door\s+No|D\.\s?No|Khasra\s+No|Khata\s+No|Gali\s+No|Ward\s+No)\.?\s*[:.\-]?\s*(?P<v>[\w/-]*\d[\w/-]*)")),
    ("PIN", re.compile(r"(?:\b(?i:PIN(?:\s*code)?|pincode|postal\s+code)\s*[:.\-\u2013]?\s*|(?<=[A-Za-z])\s?[-\u2013]\s?)(?P<v>[1-9]\d{2}\s?\d{3})(?!\d)")),
    ("PS", re.compile(rf"(?:\bP\.\s?S\.?|\bPS\b|(?i:\bpolice\s+station|\bthana)(?![a-z]))[\s.:,\u2013\-\]\['()]*(?P<v>{_PLACE_RUN})")),
    ("PS", re.compile(rf"(?<![\w-])(?P<v>(?!(?:The|Said|Concerned|Local|Nearest|Same|This|That|Respective|Jurisdictional|In|At|Of|To|From|Before|Any|Other|Every|Such|Their|His|Her|A|An|Our|Town|City|Rural|Urban)\b){_PS_WORD}(?:[ \t]+{_PS_WORD}){{0,2}})[ \t]+(?i:police[ \t]+station|thana)\b")),
    ("PS", re.compile(r"थाना\s*[:\-]?\s*(?P<v>[\u0900-\u097F]{2,}(?:\s[\u0900-\u097F]{2,})?)")),
    ("PLACE", re.compile(rf"(?:{_GLUE}(?i:village|vill\.?|vil\.|gram|mohalla|mohallah|mohulla|mauza|mouza|mouja|tola|basti|colony|post\s+office|locality)(?![A-Za-z])|\bP\.\s?O\.?)[\s.:,\u2013\-]*(?:(?i:of)\s+)?(?P<v>{_PLACE_RUN})")),
    ("PLACE", re.compile(rf"(?<![\w-])(?P<v>(?!(?:The|Main|Old|New|National|State|Said|This|That|Same|Of|In|At|And|Near)\b){_W}(?:[ \t]+(?!(?:{_PLACE_STOP})\b){_W})?)[ \t]+(?:Road|Marg|Street|Lane|Gali|Galli|Colony|Chowk|Bazar|Bazaar|Mohalla|Layout|Enclave|Vihar|Puram|Para|Tola|Basti)\b")),
    # the name before the label, as Kerala and Karnataka addresses write it: 'PANATHADY VILLAGE', 'NJARAKKATTU HOUSE', 'KANNARA POST', 'Rose Villa'
    ("PLACE", re.compile(rf"(?<![\w-])(?P<v>(?!(?i:the|said|same|this|that|our|his|her|their|of|in|at|to|from|police|court|high|district|state|post|and|one|any)\b){_W}(?:[ \t]+(?!(?i:{_PLACE_STOP})\b){_W})?)[ \t]+(?:VILLAGE|Village|HOUSE|House|MANZIL|Manzil|BHAVAN|Bhavan|NIVAS|Nivas|VILLA|Villa|POST|Post)\b(?![ \t]+(?i:office|no\b|number))")),
    ("PLACE", re.compile(r"(?:गांव|ग्राम|मोहल्ला)\s*[:\-]?\s*(?P<v>[\u0900-\u097F]{2,}(?:\s[\u0900-\u097F]{2,})?)")),
    ("ADDRESS", re.compile(rf"(?:\bR/[oO]\b|(?i:\bresident\s+of|\bresiding\s+at|\bpermanent\s+address)\b)[\s.:,\u2013\-]*(?:(?i:of)\s+)?(?P<v>(?!(?i:village|vill|mohalla|gram|at\s+present|the\s+same|house|h\.\s?no|flat|plot)\b)(?:[\w/-]*\d[\w/-]*,?\s*)?{_PLACE_RUN})")),
    ("AGE", re.compile(r"(?:\b(?i:aged?|age(?=\s*[:.\-'\]\[]))[\s.:,'\-\]\[]*(?:(?i:about|around|approx\.?(?:imately)?|abt\.?)[\s.:\-\]\[]*)?(?P<v>\d{1,3})(?=\s*(?i:years?|yrs?\.?|y\b)|[\s,)\]]|$)|(?<![\d.])(?P<v2>\d{1,3})\s*(?i:years?|yrs?)\s*(?i:old|of\s+age)\b|(?:उम्र|आयु)\s*(?:लगभग\s*)?(?P<v3>\d{1,3})\s*(?:वर्ष|साल))")),
]  # fmt: skip
CATEGORIES = tuple(dict.fromkeys(c for c, _ in _Q))
ALIAS_RE = re.compile(r"\[(?:" + "|".join(re.escape(c) for c in CATEGORIES) + r")-\d+(?: [^\]\n]{1,20})?\]")


def age_band(age: int) -> str:
    """The band an age alias carries (legal cues such as a juvenile or an elderly accused survive, the exact age does not)."""
    if age < 18:
        return "under-18"
    for hi, label in ((25, "18-25"), (35, "26-35"), (50, "36-50"), (64, "51-64")):
        if age <= hi:
            return label
    return "65-plus"


def _value(m: re.Match[str]) -> tuple[str | None, int, int]:
    for g in ("v", "v2", "v3"):
        if g in m.re.groupindex and m.group(g) is not None:
            return g, m.start(g), m.end(g)
    return None, -1, -1


def _norm(category: str, value: str, m: re.Match[str]) -> str:
    """Identity of a value: the value exactly as written (so a reply is restored to the very same string; two spellings of one station
    get two aliases), an FIR or case number keyed with its year (FIR 12/2023 and FIR 12/2024 are different FIRs)."""
    if category in ("FIR", "CASE") and "y" in m.re.groupindex and m.group("y"):
        return f"{value}/{m.group('y')}"
    return value


def _trim(category: str, value: str) -> str:
    """Cut a place name glued to the next caption word ('ChittoorDistrict' -> 'Chittoor')."""
    if category in ("PS", "PLACE", "ADDRESS"):
        return _GLUED_TAIL.sub("", value)
    return value


def _valid(category: str, value: str) -> bool:
    if category == "ACCOUNT":
        return 9 <= len(re.sub(r"\D", "", value)) <= 18
    if category == "AGE":
        return 0 < int(value) < 120
    if category in ("PS", "PLACE", "ADDRESS"):
        return len(value.strip()) >= 3
    return bool(value.strip())


def _matches(text: str, category: str, pattern: re.Pattern[str]):  # noqa: ANN202
    """(start, end, value, match) of every value of one pattern in `text` (after trimming and validation); never inside an alias already written."""
    aliases = [(a.start(), a.end()) for a in ALIAS_RE.finditer(text)] if "[" in text else []
    for m in pattern.finditer(text):
        g, s, e = _value(m)
        if g is None or any(a < e and s < b for a, b in aliases):
            continue
        value = _trim(category, text[s:e])
        if not _valid(category, value):
            continue
        yield s, s + len(value), value, m


def find_quasi(text: str) -> list[str]:
    """Categories of quasi-identifiers still written in `text` (aliases such as `[FIR-1]` do not count). The boundary's check."""
    found: list[str] = []
    for category, pattern in _Q:
        if category in found:
            continue
        for _s, _e, value, _m in _matches(text, category, pattern):
            if not ALIAS_RE.fullmatch(value.strip()):
                found.append(category)
                break
    return found


def mask_quasi(text: str, alias_for: Callable[[str, str, str, str], str]) -> str:
    """`text` with every quasi-identifier replaced by `alias_for(category, key, value, label)`; patterns run in order, each on the output of the last."""
    for category, pattern in _Q:
        spans = list(_matches(text, category, pattern))
        for s, e, value, m in reversed(spans):
            label = age_band(int(value)) if category == "AGE" else ""
            text = text[:s] + alias_for(category, _norm(category, value, m), value, label) + text[e:]
    return text


# ------------------------------------------------------------------------------------------------ the codec
class WireCodec:
    """One outbound call: `encode` the text for the hosted model, `decode` its reply. Aliases come from (and are learned into) the case's map."""

    def __init__(self, mapping: Any, days: int) -> None:
        """`mapping` is the case's PseudonymMap; `days` its date shift."""
        self.mapping = mapping
        self.days = int(days)
        self.dates: dict[str, str] = {}  # shifted string -> original string, for an exact round trip

    def encode_text(self, text: str) -> str:
        """Quasi-identifiers to aliases, then every date shifted."""
        text = mask_quasi(text, self.mapping.quasi_alias)
        return shift_dates(text, self.days, self.dates)

    def decode_text(self, text: str) -> str:
        """Dates shifted back, aliases back to the values they stand for."""
        text = unshift_dates(text, self.days, self.dates)
        return ALIAS_RE.sub(lambda m: self.mapping.quasi_original(m.group(0)) or m.group(0), text)

    def encode(self, value: Any) -> Any:
        """`encode_text` on every string of a nested value (chat messages)."""
        if isinstance(value, str):
            return self.encode_text(value)
        if isinstance(value, dict):
            return {k: self.encode(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.encode(v) for v in value]
        return value


def learn_quasi(text: str, mapping: Any) -> None:
    """Register the quasi-identifiers of `text` in the map without changing the text (intake), so every later call uses the same aliases."""
    mask_quasi(text, mapping.quasi_alias)
