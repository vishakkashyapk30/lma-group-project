"""Writes `specs/rights_scenarios.yaml`: the T4 scenario specs (500 original ones plus the HA-03 additions), with designed answers derived from the bare-act rule text (plan §15.2).

Independence. The designed answer of every scenario is computed HERE, from the rule texts in `configs/rights_rules.yaml` (BNSS s.187(3) default
bail, BNSS s.479 undertrial limit, BNSS s.35(3) notice of appearance, Art. 22(2) production within 24 hours), by a small evaluator written for this
file. Nothing in this module imports the Rights Radar (`vakeel_sahayak.rights`), so a bug in the Radar cannot validate itself. The Radar is only
compared against the finished spec in `tests/unit/testsets/test_t4_radar_crosscheck.py`, which reports disagreements instead of hiding them.

Readings made explicit (a reading is not a fact; docs/evaluation-plan.md 2.7 'Rights Radar accuracy'):

* default bail: the limit is 90 days for death, life, a term over ten years or 'ten years or more' and 60 days for a smaller term; day 1 is the first
  remand; the right arises on day limit+1. A bare 'may extend to ten years' is the unsettled case, so the designed answer is CHECK. A charge sheet filed
  on or before the as-of date closes the window (WINDOW_CLOSED). No application date is modelled.
* undertrial limit: one-half of the maximum term, one-third for a first-time offender, a year counted as 365 days and the threshold rounded up to a
  whole day (7 years: 852 and 1,278 days). Death and life: NOT_APPLICABLE. When the antecedents are unknown the answer is ELIGIBLE at or above one-half
  (both thresholds are met), CHECK between the thresholds; the below-one-third case with unknown antecedents is left out of the set.
* notice of appearance: for a maximum term of seven years or less the norm engages; an arrest memo that records reasons is OK, none is FLAG, an unknown
  file is UNKNOWN; above seven years the norm is not engaged (OK).
* HA-03 corrections (docs/qa/rights-verification.md), added after the check of the rule texts against the bare acts. The original 500 scenarios keep
  their ids and inputs; their designed answers change only where the corrected reading says so (unknown antecedents past one-half: CHECK, because
  s.479(2) is unknown too; life imprisonment: NOT_APPLICABLE only for a case clearly begun on or after 1 July 2024, else CHECK). The additions
  (`dbs-`, `uts-`, `ac-`, `sb-` ids) cover:
  - default bail under UAPA s.43D(2) (90 days, extendable to 180) and NDPS s.36A(4) (180 days for s.19, 24, 27A and commercial quantity, extendable to one
    year): up to the base limit NOT_YET; between the base limit and the extended maximum CHECK (was the period extended?); after it ELIGIBLE. An NDPS
    section whose quantity is not on record is NOT_YET up to its ordinary 60/90 days and CHECK up to one year. Quantity is read from the section's last clause:
    (c) commercial, (A) small, (b) intermediate (the doc's NDPS s.21(c) and s.20(b)(ii)(A) examples; the mapping is a person task to confirm);
  - undertrial limit with another pending case (`other_pending` true: CHECK instead of ELIGIBLE; absent or null with known antecedents: no case on record);
  - Antil category: C only for NDPS, PMLA, UAPA and the Companies Act; any other special act is read by punishment (Arms Act s.25: A);
  - statutory bar: NDPS s.19, 24, 27A and clause (c) BAR_APPLIES, clause (A) NOT_APPLICABLE, other NDPS CHECK; UAPA CHECK (the sections of Chapters IV and VI
    are not in the store); PMLA BAR_APPLIES; no special act NOT_APPLICABLE.
* production in 24 hours: elapsed time of 24 hours or less is OK, more is FLAG; travel time is not modelled (no scenario has any).

CLI: `python -m vakeel_sahayak.testsets.rights_spec_writer [--out PATH]` rewrites the spec file deterministically.
"""

from __future__ import annotations

import argparse
import math
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

SEED = 20260424
SPEC_PATH = Path(__file__).resolve().parent / "specs" / "rights_scenarios.yaml"
N_ORIGINAL = 500  # the scenarios written before HA-03; they keep their ids and inputs

_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
          "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty": 20}  # fmt: skip
_YEARS = re.compile(r"(\d+|" + "|".join(_WORDS) + r")\s*years?", re.IGNORECASE)
_FLOOR = re.compile(r"or\s+more|not\s+less\s+than|at\s+least|more\s+than|exceeding", re.IGNORECASE)


def parse_max_punishment(text: str) -> tuple[str, float | None, bool]:
    """('death' | 'life' | 'years' | 'unknown', years, floor wording) for a maximum-punishment phrase, read from the rule text."""
    low = text.lower()
    if "death" in low:
        return "death", None, False
    if "life" in low:
        return "life", None, False
    m = _YEARS.search(low)
    if not m:
        return "unknown", None, False
    n = m.group(1)
    return "years", float(_WORDS.get(n, n)), bool(_FLOOR.search(low))


_SECTION = re.compile(r"^\s*(.*?)\s*(\d+[A-Za-z]{0,2})\s*((?:\([^)]*\)\s*)*)$")


def section_parts(text: str) -> tuple[str, str, str]:
    """(act in capitals without 'Act' and spaces, section number, sub-clauses) of a charged-section string such as 'NDPS 21(c)'."""
    m = _SECTION.match(text)
    if not m:
        return "".join(re.sub(r"\bact\b", "", text, flags=re.IGNORECASE).upper().split()), "", ""
    return "".join(re.sub(r"\bact\b", "", m.group(1), flags=re.IGNORECASE).upper().split()), m.group(2).upper(), "".join(m.group(3).split())


def ndps_quantity(number: str, clause: str) -> str | None:
    """'small' (A), 'intermediate' (B) or 'commercial' (C) from the last clause of an NDPS section; None if the section carries no quantity clause."""
    groups = [g.strip().lower() for g in re.findall(r"\(([^)]*)\)", clause)]
    if not groups or groups[-1] not in ("a", "b", "c") or (number == "20" and len(groups) < 3):
        return None
    return {"a": "small", "b": "intermediate", "c": "commercial"}[groups[-1]]


def special_limit(sections: list[str]) -> tuple[int, int, bool] | None:
    """(base days, extended maximum days, certain) for default bail under UAPA s.43D(2) and NDPS s.36A(4); None for an ordinary case.

    UAPA: 90 days, extendable to 180. NDPS: 180 days, extendable to one year, for s.19, 24, 27A and commercial quantity (certain); an NDPS section with no
    quantity clause may be commercial (not certain); small and intermediate quantity keep the ordinary limit.
    """
    found: list[tuple[int, int, bool]] = []
    for text in sections:
        act, number, clause = section_parts(text)
        if act == "UAPA":
            found.append((90, 180, True))
        elif act == "NDPS":
            qty = ndps_quantity(number, clause)
            if number in ("19", "24", "27A") or qty == "commercial":
                found.append((180, 365, True))
            elif qty is None:
                found.append((180, 365, False))
    sure = [f for f in found if f[2]]
    return max(sure or found, default=None)


def designed_default_bail(inputs: dict[str, Any]) -> str:
    """BNSS s.187(3), UAPA s.43D(2), NDPS s.36A(4): ELIGIBLE / NOT_YET / WINDOW_CLOSED / CHECK."""
    kind, years, floor = parse_max_punishment(inputs["max_punishment"])
    special = special_limit(inputs.get("sections") or [])
    day = int(inputs["day"])
    if special and special[2]:
        limit, extended = special[0], special[1]
    else:
        if kind == "unknown":
            return "CHECK"
        if kind == "years" and years == 10 and not floor:
            return "CHECK"  # 'may extend to ten years': unsettled
        limit = 90 if kind in ("death", "life") or (years or 0) > 10 or (years == 10 and floor) else 60
        extended = special[1] if special else None  # an NDPS section of unknown quantity: the limit may be 180 days
    if inputs.get("charge_sheet"):
        return "WINDOW_CLOSED"
    if day <= limit:
        return "NOT_YET"
    return "CHECK" if extended and day <= extended else "ELIGIBLE"


def undertrial_thresholds(years: float) -> tuple[int, int]:
    """(one-third, one-half) of `years` as whole days, a year being 365 days, rounded up."""
    return math.ceil(years * 365 / 3), math.ceil(years * 365 / 2)


BNSS_DATE = "2024-07-01"


def begun_after_bnss(inputs: dict[str, Any]) -> bool | None:
    """True if the case clearly began on or after 1 July 2024; False for an IPC/CrPC section or an earlier FIR, arrest or first remand; None if unknown."""
    acts = [section_parts(t)[0] for t in inputs.get("sections") or []]
    if any(a in ("IPC", "CRPC") for a in acts):
        return False
    dates = [inputs[k] for k in ("fir_date", "arrest_date", "first_remand") if inputs.get(k)]
    if any(d < BNSS_DATE for d in dates):
        return False
    return True if (any(a in ("BNS", "BNSS") for a in acts) or dates) else None


def designed_undertrial(inputs: dict[str, Any]) -> str:
    """BNSS s.479, with s.479(2) (other pending cases) and the unsettled pre-BNSS life-imprisonment case: ELIGIBLE / NOT_YET / NOT_APPLICABLE / CHECK."""
    kind, years, _ = parse_max_punishment(inputs["max_punishment"])
    if kind == "death":
        return "NOT_APPLICABLE"
    if kind == "life":
        return "NOT_APPLICABLE" if begun_after_bnss(inputs) is True else "CHECK"
    if kind == "unknown":
        return "CHECK"
    third, half = undertrial_thresholds(years or 0)
    days, first, pending = int(inputs["custody_days"]), inputs.get("first_time"), inputs.get("other_pending")
    if first is None:  # antecedents unknown, so other pending cases are unknown too unless the file says none
        return "ELIGIBLE" if days >= half and pending is False else "CHECK"
    if days < (third if first else half):
        return "NOT_YET"
    return "CHECK" if pending else "ELIGIBLE"


def designed_notice(inputs: dict[str, Any]) -> str:
    """BNSS s.35(3): OK / FLAG / UNKNOWN."""
    kind, years, _ = parse_max_punishment(inputs["max_punishment"])
    if kind == "unknown":
        return "UNKNOWN"
    if kind in ("death", "life") or (years or 0) > 7:
        return "OK"
    memo = inputs.get("arrest_memo")
    return "UNKNOWN" if memo is None else "OK" if memo else "FLAG"


def designed_production(inputs: dict[str, Any]) -> str:
    """Art. 22(2): OK within 24 hours of arrest, FLAG after."""
    t0 = datetime.fromisoformat(f"{inputs['arrest_date']}T{inputs['arrest_time']}")
    t1 = datetime.fromisoformat(f"{inputs['production_date']}T{inputs['production_time']}")
    return "OK" if (t1 - t0) <= timedelta(hours=24) else "FLAG"


STRINGENT_BAIL_ACTS = {"NDPS", "PMLA", "UAPA", "COMPANIES"}  # Antil category C: NDPS s.37, PMLA s.45, UAPA s.43D(5), Companies Act s.212(6)
ECONOMIC = {"IPC406", "IPC409", "IPC420", "IPC467", "IPC468", "IPC471", "BNS316", "BNS318", "BNS336", "BNS338", "BNS340"}


def designed_antil(inputs: dict[str, Any]) -> str:
    """Antil (2022): C only for acts with stringent bail provisions; else B above seven years, CHECK for a section often argued as economic, else A."""
    parts = [section_parts(t) for t in inputs["sections"]]
    if any(act in STRINGENT_BAIL_ACTS for act, _, _ in parts):
        return "C"
    kind, years, _ = parse_max_punishment(inputs["max_punishment"])
    if kind == "unknown":
        return "CHECK"
    if kind in ("death", "life") or (years or 0) > 7:
        return "B"
    return "CHECK" if any(f"{act}{number}" in ECONOMIC for act, number, _ in parts) else "A"


def designed_statutory_bar(inputs: dict[str, Any]) -> str:
    """NDPS s.37(1)(b) (s.19, 24, 27A, commercial quantity), UAPA s.43D(5) (Chapters IV and VI: not known, so CHECK), PMLA s.45."""
    verdicts = []
    for text in inputs["sections"]:
        act, number, clause = section_parts(text)
        if act == "PMLA":
            verdicts.append("BAR_APPLIES")
        elif act == "UAPA":
            verdicts.append("CHECK")
        elif act == "NDPS":
            qty = ndps_quantity(number, clause)
            verdicts.append("BAR_APPLIES" if number in ("19", "24", "27A") or qty == "commercial" else "NOT_APPLICABLE" if qty == "small" else "CHECK")
    if "BAR_APPLIES" in verdicts:
        return "BAR_APPLIES"
    if "CHECK" in verdicts:
        return "CHECK"
    return "NOT_APPLICABLE"


EVALUATORS = {
    "default_bail": designed_default_bail,
    "undertrial_limit": designed_undertrial,
    "notice_of_appearance": designed_notice,
    "production_24h": designed_production,
    "antil_category": designed_antil,
    "statutory_bar": designed_statutory_bar,
}

_P60 = ["3 years", "5 years", "7 years", "may extend to seven years", "2 years"]
_P90 = ["10 years or more", "not less than ten years", "14 years", "20 years", "imprisonment for life", "life", "death"]
_P10 = ["may extend to ten years"]
_LIFE = ["life", "imprisonment for life", "death"]


def _iso(d: date) -> str:
    return d.isoformat()


def _spec(sid: str, rule: str, inputs: dict[str, Any], note: str) -> dict[str, Any]:
    return {"id": sid, "rule": rule, "inputs": inputs, "designed_answer": EVALUATORS[rule](inputs), "note": note}


def _default_bail(rng: random.Random) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def remand() -> str:
        return _iso(date(2024, 7, 5) + timedelta(days=rng.randrange(0, 450)))

    def add(pun: str, day: int, cs_day: int | None, note: str) -> None:
        fr = remand()
        cs = _iso(date.fromisoformat(fr) + timedelta(days=cs_day - 1)) if cs_day else None
        out.append(_spec(f"db-{len(out) + 1:03d}", "default_bail",
                         {"first_remand": fr, "day": day, "max_punishment": pun, "charge_sheet": cs}, note))

    for day in (1, 30, 45, 58, 59, 60, 61, 62, 75, 120):
        for _ in range(5):
            add(rng.choice(_P60), day, None, f"60-day limit, day {day}, no charge sheet")
    for day in (1, 60, 61, 75, 88, 89, 90, 91, 92, 120):
        for _ in range(5):
            add(rng.choice(_P90), day, None, f"90-day limit, day {day}, no charge sheet")
    for i in range(20):
        add(_P10[0], (59, 60, 61, 89, 90, 91, 100)[i % 7], None, "'may extend to ten years' is unsettled")
    for i in range(80):
        if i % 2 == 0:
            pun, cs_day = rng.choice(_P60), rng.choice((40, 59, 60, 61, 62, 70))
        else:
            pun, cs_day = rng.choice(_P90), rng.choice((80, 89, 90, 91, 92, 100))
        add(pun, cs_day + rng.choice((0, 5, 20)), cs_day, f"charge sheet filed on day {cs_day}")
    return out


def _undertrial(rng: random.Random) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def add(pun: str, days: int, first: bool | None, note: str) -> None:
        as_of = date(2025, 6, 1) + timedelta(days=rng.randrange(0, 480))
        out.append(_spec(f"ut-{len(out) + 1:03d}", "undertrial_limit",
                         {"custody_days": days, "max_punishment": pun, "first_time": first, "as_of": _iso(as_of),
                          "arrest_date": _iso(as_of - timedelta(days=days))}, note))

    pool = (3, 5, 7, 10, 14)
    for y in pool:
        third, half = undertrial_thresholds(y)
        for first, thr, name in ((True, third, "one-third, first-time"), (False, half, "one-half, repeat")):
            for off in (-1, 0, 1):
                add(f"{y} years", thr + off, first, f"{name} threshold {thr} {off:+d}")
        for off in (-1, 0, 1):
            add(f"{y} years", half + off, True, f"first-time offender around one-half ({half})")
            add(f"{y} years", third + off, False, f"repeat offender around one-third ({third})")
        for days, name in ((third, "one-third"), (half - 1, "just under one-half"), (half, "one-half"), (half + 1, "just over one-half")):
            add(f"{y} years", days, None, f"antecedents unknown at {name}")
    for i in range(12):
        add(_LIFE[i % 3], (1000, 3000, 5000)[i % 3 if i < 9 else 0], bool(i % 2), "death or life: not applicable")
    while len(out) < 200:
        y = rng.choice((2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 15))
        third, half = undertrial_thresholds(y)
        first = rng.random() < 0.5
        add(f"{y} years", max(1, int(rng.uniform(0.5, 1.3) * (third if first else half))), first, "random custody around the applicable threshold")
    return out


def _notice(rng: random.Random) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    pool = ["1 year", "3 years", "5 years", "7 years", "seven years", "8 years", "9 years", "10 years", "14 years", "life"]

    def add(pun: str, memo: bool | None) -> None:
        d = date(2024, 7, 5) + timedelta(days=rng.randrange(0, 450))
        out.append(_spec(f"na-{len(out) + 1:03d}", "notice_of_appearance",
                         {"max_punishment": pun, "arrest_memo": memo, "arrest_date": _iso(d)}, f"{pun}, arrest memo {memo}"))

    for pun in pool:
        for memo in (True, False, None):
            add(pun, memo)
    while len(out) < 50:
        add(rng.choice(pool), rng.choice((True, False, None)))
    return out


def _production(rng: random.Random) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    offsets = (60, 600, 1380, 1439, 1440, 1441, 1470, 1800, 2820, 4000)  # minutes after arrest: 23:59, 24:00 and 24:01 straddle the line
    for off in offsets:
        for _ in range(5):
            t0 = datetime(2024, 7, 5, 0, 0) + timedelta(days=rng.randrange(0, 450), minutes=rng.randrange(0, 1440))
            t1 = t0 + timedelta(minutes=off)
            out.append(_spec(f"pr-{len(out) + 1:03d}", "production_24h",
                             {"arrest_date": _iso(t0.date()), "arrest_time": t0.strftime("%H:%M"),
                              "production_date": _iso(t1.date()), "production_time": t1.strftime("%H:%M")},
                             f"produced {off} minutes after arrest"))
    return out


def _ha03(rng: random.Random) -> list[dict[str, Any]]:
    """Scenarios added after the check of the rule texts against the bare acts (docs/qa/rights-verification.md); their own random stream keeps the original 500 unchanged."""
    out: list[dict[str, Any]] = []

    def remand() -> str:
        return _iso(date(2025, 1, 10) + timedelta(days=rng.randrange(0, 300)))

    def db(prefix: str, sections: list[str], pun: str, day: int, cs_day: int | None, note: str) -> None:
        fr = remand()
        cs = _iso(date.fromisoformat(fr) + timedelta(days=cs_day - 1)) if cs_day else None
        out.append(_spec(f"dbs-{len(out) + 1:03d}", "default_bail",
                         {"first_remand": fr, "day": day, "max_punishment": pun, "charge_sheet": cs, "sections": sections}, f"HA-03 {prefix}: {note}"))

    # the two reproduced wrong inputs first
    db("UAPA", ["UAPA 18"], "5 years", 62, None, "reproduced wrong input: UAPA, maximum 5 years, day 62: not yet (s.43D(2): 90 days)")
    db("NDPS", ["NDPS 21(c)"], "20 years", 100, None, "reproduced wrong input: NDPS s.21(c), maximum 20 years, day 100: not yet (s.36A(4): 180 days)")
    for day in (1, 60, 61, 62, 89, 90, 91, 120, 179, 180, 181, 200):
        db("UAPA", ["UAPA 18"], rng.choice(("5 years", "3 years", "7 years", "may extend to ten years", "life")), day, None, f"UAPA s.43D(2), day {day}")
    for day in (61, 90, 91, 100, 179, 180, 181, 300, 365, 366, 400):
        db("NDPS", [rng.choice(("NDPS 21(c)", "NDPS 22(c)", "NDPS 20(b)(ii)(C)"))], rng.choice(("20 years", "10 years or more")), day, None, f"NDPS commercial quantity, day {day}")
    for day in (100, 180, 181, 366):
        db("NDPS", [rng.choice(("NDPS 19", "NDPS 24", "NDPS 27A"))], rng.choice(("10 years", "20 years", "life")), day, None, f"NDPS s.19, 24 or 27A, day {day}")
    for day in (59, 60, 61, 91):
        db("NDPS", ["NDPS 20(b)(ii)(A)"], "1 year", day, None, f"NDPS small quantity keeps the ordinary 60 days, day {day}")
    for day in (59, 60, 61, 91, 92):
        db("NDPS", ["NDPS 22(b)"], rng.choice(("10 years or more", "may extend to ten years")), day, None, f"NDPS intermediate quantity: ordinary limit, day {day}")
    for day in (60, 61, 90, 91, 100, 181, 366):
        db("NDPS", ["NDPS 21"], "10 years or more", day, None, f"NDPS section with no quantity on record, day {day}")
    for day in (60, 61, 100):
        db("mixed", ["IPC 420", "NDPS 21(c)"], "7 years", day, None, f"IPC 420 with NDPS commercial quantity, day {day}")
    for day in (60, 61):
        db("control", ["BNS 318(4)"], "7 years", day, None, f"BNS only: unchanged 60-day limit, day {day}")
    for sections, pun, cs_day, day in ((["UAPA 18"], "5 years", 80, 85), (["UAPA 18"], "5 years", 100, 110), (["NDPS 21(c)"], "20 years", 150, 160), (["NDPS 21(c)"], "20 years", 200, 210)):
        db("charge sheet", sections, pun, day, cs_day, f"charge sheet on day {cs_day}")
    n_db = len(out)

    def ut(pun: str, days: int, first: bool | None, pending: bool | None, note: str, **extra: Any) -> None:
        as_of = date(2025, 12, 1) + timedelta(days=rng.randrange(0, 200))
        inputs = {"custody_days": days, "max_punishment": pun, "first_time": first, "as_of": _iso(as_of), "arrest_date": _iso(as_of - timedelta(days=days)),
                  "other_pending": pending, **extra}
        out.append(_spec(f"uts-{len(out) - n_db + 1:03d}", "undertrial_limit", inputs, f"HA-03 {note}"))

    third, half = undertrial_thresholds(3)
    ut("3 years", 600, False, True, "reproduced wrong input: BNS 303, maximum 3 years, 600 days, not first-time, other case pending: CHECK (s.479(2))", sections=["BNS 303"])
    for first, thr in ((True, third), (False, half)):
        for off in (-1, 0, 1):
            for pending in (True, False, None):
                ut("3 years", thr + off, first, pending, f"3 years, first-time {first}, other pending {pending}, threshold {thr} {off:+d}", sections=["BNS 303"])
    for days in (half - 1, half, half + 1):
        for pending in (True, False, None):
            ut("3 years", days, None, pending, f"antecedents unknown, other pending {pending}, at {days}", sections=["BNS 303"])
    ut("life", 3000, True, None, "life imprisonment, IPC section: a pre-BNSS case, CHECK", sections=["IPC 302"])
    ut("imprisonment for life", 3000, False, None, "life imprisonment, BNS section, arrest before 1 July 2024: CHECK", sections=["BNS 103"], fir_date="2023-05-01")
    ut("life", 300, True, None, "life imprisonment, BNS section: NOT_APPLICABLE (case begun after 1 July 2024)", sections=["BNS 103"], fir_date="2025-01-15")
    ut("death", 3000, True, None, "death: NOT_APPLICABLE whatever the era", sections=["IPC 302"])
    n_ut = len(out) - n_db

    def ac(sections: list[str], pun: str, note: str) -> None:
        out.append(_spec(f"ac-{len(out) - n_db - n_ut + 1:03d}", "antil_category", {"sections": sections, "max_punishment": pun}, f"HA-03 {note}"))

    ac(["Arms Act 25"], "3 years", "reproduced wrong input: Arms Act s.25, maximum 3 years: A, not C (no stringent bail provision)")
    for sections, pun in ((["NDPS 20(b)(ii)(A)"], "1 year"), (["NDPS 21(c)"], "20 years"), (["UAPA 18"], "5 years"), (["PMLA 4"], "7 years"),
                          (["Companies Act 447"], "10 years"), (["Arms Act 25"], "7 years"), (["Arms Act 27"], "life"), (["Excise Act 9"], "10 years"),
                          (["IT Act 66"], "3 years"), (["BNS 115(2)"], "1 year"), (["BNS 137(2)"], "7 years"), (["BNS 124(1)"], "10 years"), (["BNS 103"], "life"),
                          (["BNS 103"], "death"), (["BNS 318(4)"], "7 years"), (["IPC 420"], "7 years"), (["Arms Act 25", "BNS 115(2)"], "3 years"), (["BNS 303"], "")):
        ac(sections, pun, f"{sections[0]}, {pun or 'no punishment on record'}")

    def sb(sections: list[str], note: str) -> None:
        out.append(_spec(f"sb-{len(out) - n_db - n_ut - n_ac + 1:03d}", "statutory_bar", {"sections": sections, "max_punishment": "10 years"}, f"HA-03 {note}"))

    n_ac = len([r for r in out if r["rule"] == "antil_category"])
    sb(["NDPS 20(b)(ii)(A)"], "reproduced wrong input: NDPS s.20(b)(ii)(A) small quantity: s.37(1)(b) does not reach it")
    for sections in (["NDPS 19"], ["NDPS 24"], ["NDPS 27A"], ["NDPS 21(c)"], ["NDPS 22(c)"], ["NDPS 20(b)(ii)(C)"], ["NDPS 21(a)"], ["NDPS 22(b)"], ["NDPS 21"], ["NDPS 20(b)(ii)(B)"],
                     ["UAPA 18"], ["UAPA 43D"], ["PMLA 4"], ["PMLA 3"], ["BNS 318(4)"], ["IPC 420"], ["Arms Act 25"], ["IPC 420", "NDPS 21(c)"], ["NDPS 20(b)(ii)(A)", "NDPS 27A"],
                     ["NDPS 20(b)(ii)(A)", "UAPA 18"], ["BNS 103", "PMLA 4"]):
        sb(sections, f"{' + '.join(sections)}")
    return out


def write_scenarios(seed: int = SEED) -> list[dict[str, Any]]:
    """The scenario specs in a fixed order (deterministic for a seed): the original 500, then the HA-03 additions."""
    rng = random.Random(seed)
    original = _default_bail(rng) + _undertrial(rng) + _notice(rng) + _production(rng)
    assert len(original) == N_ORIGINAL, len(original)
    return original + _ha03(random.Random(seed + 1))


def dump(path: str | Path = SPEC_PATH, seed: int = SEED) -> int:
    """Write the YAML spec file; returns the scenario count."""
    specs = write_scenarios(seed)
    header = (
        "# T4 rights-scenario specs (plan §15.2): the original 500 scenarios plus the HA-03 additions, designed answers derived from the bare-act rule text by\n"
        "# vakeel_sahayak.testsets.rights_spec_writer (which does not import the Rights Radar). Regenerate with\n"
        "#   python -m vakeel_sahayak.testsets.rights_spec_writer\n"
        "# Each scenario: id, rule, inputs, designed_answer (a RightsStatus value), note.\n"
    )
    Path(path).write_text(header + yaml.safe_dump({"scenarios": specs}, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return len(specs)


def main(argv: list[str] | None = None) -> int:
    """CLI."""
    ap = argparse.ArgumentParser(description="Write the T4 scenario spec file")
    ap.add_argument("--out", default=str(SPEC_PATH))
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)
    print(f"wrote {dump(args.out, args.seed)} scenarios to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
