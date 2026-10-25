"""Writes `specs/rights_scenarios.yaml`: the 500 T4 scenario specs, with designed answers derived from the bare-act rule text (plan §15.2).

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
N_SCENARIOS = 500

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


def designed_default_bail(inputs: dict[str, Any]) -> str:
    """BNSS s.187(3): ELIGIBLE / NOT_YET / WINDOW_CLOSED / CHECK."""
    kind, years, floor = parse_max_punishment(inputs["max_punishment"])
    if kind == "unknown":
        return "CHECK"
    if kind == "years" and years == 10 and not floor:
        return "CHECK"  # 'may extend to ten years': unsettled
    limit = 90 if kind in ("death", "life") or (years or 0) > 10 or (years == 10 and floor) else 60
    if inputs.get("charge_sheet"):
        return "WINDOW_CLOSED"
    return "ELIGIBLE" if int(inputs["day"]) > limit else "NOT_YET"


def undertrial_thresholds(years: float) -> tuple[int, int]:
    """(one-third, one-half) of `years` as whole days, a year being 365 days, rounded up."""
    return math.ceil(years * 365 / 3), math.ceil(years * 365 / 2)


def designed_undertrial(inputs: dict[str, Any]) -> str:
    """BNSS s.479: ELIGIBLE / NOT_YET / NOT_APPLICABLE / CHECK."""
    kind, years, _ = parse_max_punishment(inputs["max_punishment"])
    if kind in ("death", "life"):
        return "NOT_APPLICABLE"
    if kind == "unknown":
        return "CHECK"
    third, half = undertrial_thresholds(years or 0)
    days, first = int(inputs["custody_days"]), inputs.get("first_time")
    if first is None:
        return "ELIGIBLE" if days >= half else "CHECK"
    return "ELIGIBLE" if days >= (third if first else half) else "NOT_YET"


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


EVALUATORS = {
    "default_bail": designed_default_bail,
    "undertrial_limit": designed_undertrial,
    "notice_of_appearance": designed_notice,
    "production_24h": designed_production,
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


def write_scenarios(seed: int = SEED) -> list[dict[str, Any]]:
    """The 500 scenario specs in a fixed order (deterministic for a seed)."""
    rng = random.Random(seed)
    specs = _default_bail(rng) + _undertrial(rng) + _notice(rng) + _production(rng)
    assert len(specs) == N_SCENARIOS, len(specs)
    return specs


def dump(path: str | Path = SPEC_PATH, seed: int = SEED) -> int:
    """Write the YAML spec file; returns the scenario count."""
    specs = write_scenarios(seed)
    header = (
        "# T4 rights-scenario specs (plan §15.2): 500 scenarios, designed answers derived from the bare-act rule text by\n"
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
