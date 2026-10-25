"""T3 change sets: 60 T1 cases x 3 changes (charge sheet filed; co-accused granted bail; time crosses a threshold) plus 60 no-op controls; 240 updates (plan §15.2).

Each of the 60 cases (drawn with a seed from the OPEN part of T1; the sealed blind slice is never used, and cases whose court text already says the
charge sheet was filed or a co-accused was granted bail are avoided) receives four updates: `charge_sheet_filed` (a new charge-sheet document),
`co_accused_bail` (a new order granting a co-accused bail), `time_crosses_threshold` (no document: the clock moves to day 61 of the 60-day default-bail
window, or to the one-third undertrial threshold of 852 days for a seven-year offence), and `noop` (the case's own facts document filed a second time).

Answers are by construction. The baseline dossier state before the change is built from the case's G3 values where they exist (sections, arrest date) and
constructed otherwise (`constructed` in each row names which); the change, the fields it alters, the ground it concerns and the rights entries it moves
are fixed by the construction. `expected.fields`, `expected.grounds` and `expected.rights_changed` are what the change directly alters; `reopened_factors`
adds every factor whose evidence reads a changed field or rights entry under the truth-maintenance dependency model of plan §10 (`FACTOR_FIELDS` and
`FACTOR_RIGHTS`, copied below from `agents/vakeel/facts.py` and checked against it in `tests/unit/testsets/test_t3_dependency_model.py`), which is
the set of grounds F2 must redraft; `unchanged_fields` are the dossier fields that must stay byte-identical. A no-op expects nothing at all.

Outputs in `out_dir`: `updates.jsonl`, `manifest.json`. CLI: `python -m vakeel_sahayak.testsets.t3_change_sets [--t1 DIR --out DIR]`.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from vakeel_sahayak.testsets.common import (
    TestSetManifest,
    faker_names,
    g3_fields,
    load_t1_cases,
    rows_to_file,
    sha256_file,
    write_manifest,
)

SEED = 20260425
N_CASES = 60
CHANGE_TYPES = ("charge_sheet_filed", "co_accused_bail", "time_crosses_threshold", "noop")
DOSSIER_FIELDS = ("fir", "offence_date", "sections", "arrest_date", "first_remand", "custody_days", "charge_sheet", "trial_stage",
                  "previous_bail", "co_accused_bail", "antecedents", "personal", "parties")  # fmt: skip
# plan §10 dependency model: which dossier fields and Radar entries each factor's evidence reads (copy of agents/vakeel/facts.py)
FACTOR_FIELDS: dict[str, tuple[str, ...]] = {
    "gravity_and_punishment": ("sections", "fir"),
    "custody_period": ("custody_days", "arrest_date", "first_remand", "sections"),
    "charge_sheet_filed": ("charge_sheet", "custody_days", "sections"),
    "trial_delay": ("trial_stage", "charge_sheet", "custody_days"),
    "parity_with_co_accused": ("co_accused_bail", "sections"),
    "antecedents": ("antecedents",),
    "flight_risk": ("personal",),
    "witness_tampering": ("trial_stage", "charge_sheet"),
    "weak_prima_facie": ("fir", "sections", "offence_date"),
    "health_age_family": ("personal",),
    "statutory_bar": ("sections",),
    "undertrial_period": ("custody_days", "arrest_date", "sections"),
}
FACTOR_RIGHTS: dict[str, tuple[str, ...]] = {
    "gravity_and_punishment": ("antil_category",),
    "custody_period": ("default_bail", "undertrial_limit"),
    "charge_sheet_filed": ("default_bail",),
    "trial_delay": ("undertrial_limit",),
    "statutory_bar": ("statutory_bar",),
    "undertrial_period": ("undertrial_limit",),
}
EXTRA_FIELD_FACTORS: dict[str, tuple[str, ...]] = {"previous_bail": ("antecedents", "parity_with_co_accused"), "personal": ("flight_risk", "health_age_family")}


def reopened_factors(fields: list[str], rights: list[str]) -> list[str]:
    """Factors whose evidence reads a changed dossier field or Radar entry (plan §10 step 2), in the order of `FACTOR_FIELDS`."""
    out = {fac for fac, used in FACTOR_FIELDS.items() if set(fields) & set(used)}
    out |= {fac for fac, used in FACTOR_RIGHTS.items() if set(rights) & set(used)}
    for name in fields:
        out |= set(EXTRA_FIELD_FACTORS.get(name, ()))
    return [f for f in FACTOR_FIELDS if f in out]


def _dmy(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def _pick_cases(cases: list[dict[str, Any]], rng: random.Random) -> tuple[list[dict[str, Any]], int]:
    """60 cases, preferring those whose court text does not already contradict a pre-change baseline; returns (cases, number relaxed)."""
    def clean(c: dict[str, Any]) -> bool:
        f = g3_fields(c)
        return not f.get("charge_sheet_filed") and f.get("co_accused_bail") not in ("granted", "bail_granted")

    pool = sorted(cases, key=lambda c: c["case_id"])
    rng.shuffle(pool)
    good = [c for c in pool if clean(c)]
    rest = [c for c in pool if not clean(c)]
    chosen = (good + rest)[:N_CASES]
    return chosen, max(0, N_CASES - len(good))


def _baseline(case: dict[str, Any], rng: random.Random) -> tuple[dict[str, Any], list[str]]:
    """The dossier values before any change, and the names of the values that were constructed rather than read from G3."""
    f = g3_fields(case)
    constructed: list[str] = []
    order_date = date.fromisoformat(case["date"]) if case.get("date") else date(2025, 3, 1)
    arrest = f.get("arrest_date")
    if not isinstance(arrest, str) or len(arrest) != 10:
        arrest = (order_date - timedelta(days=rng.randrange(40, 330))).isoformat()
        constructed.append("arrest_date")
    fr = f.get("first_remand")
    if not isinstance(fr, str) or len(fr) != 10:
        fr = (date.fromisoformat(arrest) + timedelta(days=1)).isoformat()
        constructed.append("first_remand")
    sections = f.get("sections")
    if not sections:
        sections = ["318(4) BNS"]
        constructed.append("sections")
    fir_no = f"{rng.randrange(20, 900)}/{date.fromisoformat(arrest).year}"
    constructed += ["fir", "charge_sheet", "co_accused_bail", "max_punishment", "first_time_offender"]
    return {
        "arrest_date": arrest, "first_remand": fr, "sections": list(sections), "fir": {"number": fir_no, "police_station": "PS-" + str(rng.randrange(1, 40))},
        "charge_sheet": {"filed": False, "date": None}, "co_accused_bail": [], "max_punishment": "7 years", "first_time_offender": True,
    }, constructed


def _charge_sheet_doc(base: dict[str, Any], accused: str, day: int) -> tuple[str, date]:
    filed = date.fromisoformat(base["first_remand"]) + timedelta(days=day - 1)
    return (
        f"IN THE COURT OF THE CHIEF JUDICIAL MAGISTRATE\nCharge sheet filing note dated {_dmy(filed)}\nFIR No. {base['fir']['number']}, "
        f"{base['fir']['police_station']}. The investigating officer has filed the charge sheet against the accused {accused} on {_dmy(filed)} "
        f"under Section {', '.join(base['sections'])}. The charge sheet is received and the case is registered for cognizance.\n"
    ), filed


def _co_accused_doc(base: dict[str, Any], accused: str, co: str, when: date) -> str:
    return (
        f"IN THE HIGH COURT\nOrder dated {_dmy(when)}\nFIR No. {base['fir']['number']}, {base['fir']['police_station']}. Bail application of {co} (co-accused "
        f"no. 2 with {accused}). Heard. Bail is granted to {co} on furnishing a personal bond, subject to the usual conditions. "
        f"The application of the co-accused is allowed.\n"
    )


def build_t3(t1_dir: str, out_dir: str) -> TestSetManifest:
    """Construct updates with the expected changed fields and grounds.

    Args:
        t1_dir: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.

    Raises:
        ValueError: fewer than 60 usable T1 cases.
    """
    cases = load_t1_cases(t1_dir)
    if len(cases) < N_CASES:
        raise ValueError(f"T3 needs {N_CASES} T1 cases, found {len(cases)}")
    rng = random.Random(SEED)
    chosen, relaxed = _pick_cases(cases, rng)
    names = faker_names(SEED, 2 * N_CASES)
    rows: list[dict[str, Any]] = []
    for n, case in enumerate(chosen):
        accused, co = names[2 * n], names[2 * n + 1]
        base, constructed = _baseline(case, rng)
        common = {"case_id": case["case_id"], "baseline": base, "constructed": constructed}

        def row(kind: str, trigger: str, doc: str | None, as_of: str | None, fields: list[str], grounds: list[str], rights: list[str],
                extra: dict[str, Any] | None = None, _n: int = n, _common: dict[str, Any] = common) -> dict[str, Any]:
            return {
                **_common, "update_id": f"t3-{_n:03d}-{kind}", "change_type": kind, "trigger": trigger, "new_document": doc, "as_of": as_of,
                "expected": {"fields": fields, "grounds": grounds, "rights_changed": rights},
                "reopened_factors": reopened_factors(fields, rights),
                "unchanged_fields": [x for x in DOSSIER_FIELDS if x not in fields], **(extra or {}),
            }

        day = rng.choice((45, 58, 62, 75, 90, 120))
        doc, filed = _charge_sheet_doc(base, accused, day)
        rows.append(row("charge_sheet_filed", "new_document", doc, filed.isoformat(), ["charge_sheet"], ["charge_sheet_filed"], ["default_bail"],
                        {"new_value": {"charge_sheet": {"filed": True, "date": filed.isoformat()}}, "day_of_remand": day}))
        when = date.fromisoformat(base["first_remand"]) + timedelta(days=rng.randrange(20, 200))
        rows.append(row("co_accused_bail", "new_document", _co_accused_doc(base, accused, co, when), when.isoformat(), ["co_accused_bail"],
                        ["parity_with_co_accused"], [], {"new_value": {"co_accused_bail": [{"id": co, "outcome": "granted", "date": when.isoformat()}]}}))
        if n % 2 == 0:  # default-bail window: day 60 -> day 61 of the 60-day limit (seven-year offence, no charge sheet)
            fr = date.fromisoformat(base["first_remand"])
            rows.append(row("time_crosses_threshold", "clock", None, (fr + timedelta(days=60)).isoformat(), ["custody_days"], ["custody_period"],
                            ["default_bail"], {"baseline_as_of": (fr + timedelta(days=59)).isoformat(), "threshold": "default_bail_day_61",
                                               "new_value": {"custody_days": (fr + timedelta(days=60) - date.fromisoformat(base["arrest_date"])).days}}))
        else:  # BNSS s.479 one-third (first-time offender, seven years): 852 days
            ar = date.fromisoformat(base["arrest_date"])
            rows.append(row("time_crosses_threshold", "clock", None, (ar + timedelta(days=852)).isoformat(), ["custody_days"], ["undertrial_period"],
                            ["undertrial_limit"], {"baseline_as_of": (ar + timedelta(days=851)).isoformat(), "threshold": "undertrial_one_third_852",
                                                   "new_value": {"custody_days": 852}}))
        rows.append(row("noop", "new_document", case["facts_text"], None, [], [], [], {"duplicate_of": case["case_id"]}))
    rows.sort(key=lambda r: (r["update_id"].split("-")[1], CHANGE_TYPES.index(r["change_type"])))
    out = Path(out_dir)
    rows_to_file(out / "updates.jsonl", rows)
    kinds = Counter(r["change_type"] for r in rows)
    clock = Counter(r["threshold"] for r in rows if r["change_type"] == "time_crosses_threshold")
    details = {
        "seed": SEED, "cases": N_CASES, "per_change_type": dict(kinds), "per_court": dict(Counter(c["court"] for c in chosen)),
        "bns_era_cases": sum(bool(c.get("bns_era")) for c in chosen), "clock_thresholds": dict(clock),
        "cases_not_avoiding_prior_charge_sheet_or_bail": relaxed,
        "baseline_values_read_from_g3": {k: sum(k not in r["constructed"] for r in rows if r["change_type"] == "noop") for k in ("arrest_date", "first_remand", "sections")},
        "source_cases_sha256": sha256_file(Path(t1_dir) / "cases.jsonl"), "blind_slice_used": False,
        "not_built": [], "dependency_model": "plan §10; FACTOR_FIELDS and FACTOR_RIGHTS of agents/vakeel/facts.py (checked by a test)",
    }
    manifest = TestSetManifest(set_id="T3", size=len(rows), answers_from="construction: the planted change and the plan §10 dependency model",
                               used_for=["F2"], path=str(out), details=details)
    write_manifest(manifest, str(out))
    return manifest


def main(argv: list[str] | None = None) -> int:
    """CLI."""
    from vakeel_sahayak.config import load_config

    base = Path(load_config().paths.testsets_dir)
    ap = argparse.ArgumentParser(description="Build T3 (change sets)")
    ap.add_argument("--t1", default=str(base / "t1"))
    ap.add_argument("--out", default=str(base / "t3"))
    args = ap.parse_args(argv)
    m = build_t3(args.t1, args.out)
    print(json.dumps({"size": m.size, **{k: m.details[k] for k in ("per_change_type", "clock_thresholds", "bns_era_cases")}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
