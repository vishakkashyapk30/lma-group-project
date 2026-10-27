"""T5 batch set: 200 T1 cases plus 100 T4 scenarios with deadlines planted in the next 7 days; 300 cases (plan §15.2).

One shared "today" (`AS_OF`) for the whole desk. The 200 T1 cases are the background: they carry no planted deadline. 100 T4 scenarios are re-dated so
that a legal deadline falls inside the next seven days: for a default-bail scenario the 60- or 90-day window opens on day limit+1, which is moved to
AS_OF + k; for an undertrial scenario the one-third or one-half threshold of BNSS s.479 is reached on AS_OF + k (k between 1 and 7, spread evenly and
shuffled). The scenario's own rule text (the same independent derivation as T4, `rights_spec_writer`) fixes the limit; the Radar is not consulted.

Gold ranking by the stated urgency rule (plan §11, deadlines first, the nearest first): `rank` 1..100 over the planted cases by deadline date (ties
broken by default-bail before s.479, then by case id); T1 cases have rank None. FIFO order is the file order of `cases.jsonl` after a seeded shuffle that
mixes planted and background cases, so a policy that is not urgency-aware misses deadlines. Each planted case has its documents under `bundles/<case_id>/`.

Outputs in `out_dir`: `cases.jsonl` (case_id, source T1|T4, scenario_id, as_of, deadline, deadline_kind, days_to_deadline, rank, urgent, designed_answer_now,
designed_answer_on_deadline, facts), `bundles/`, `manifest.json`. CLI: `python -m vakeel_sahayak.testsets.t5_batch [--t1 DIR --t4 DIR --out DIR]`.
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
    load_t1_cases,
    rows_from_file,
    rows_to_file,
    write_manifest,
)
from vakeel_sahayak.testsets.rights_spec_writer import parse_max_punishment, undertrial_thresholds
from vakeel_sahayak.testsets.t4_rights_scenarios import render_scenario_documents

SEED = 20260428
AS_OF = "2026-11-02"
N_T1, N_T4 = 200, 100
WINDOW_DAYS = 7


def _ha03_scenario(spec: dict[str, Any]) -> bool:
    """True for a T4 scenario added after the HA-03 check (special-act sections, pending-case flag, or a rule T5 does not plant)."""
    inputs = spec["inputs"]
    return spec["rule"] in ("antil_category", "statutory_bar") or "sections" in inputs or "other_pending" in inputs


def _plant_default_bail(spec: dict[str, Any], k: int, as_of: date) -> dict[str, Any] | None:
    kind, years, floor = parse_max_punishment(str(spec["inputs"]["max_punishment"]))
    if kind == "unknown" or (kind == "years" and years == 10 and not floor) or spec["inputs"].get("charge_sheet"):
        return None  # the limit is unsettled or the window is already closed: no clean deadline
    limit = 90 if kind in ("death", "life") or (years or 0) > 10 or (years == 10 and floor) else 60
    first_remand = as_of - timedelta(days=limit - k)
    inputs = {**spec["inputs"], "first_remand": first_remand.isoformat(), "day": limit + 1 - k, "charge_sheet": None}
    return {"inputs": inputs, "deadline": (as_of + timedelta(days=k)).isoformat(), "kind": "default_bail_window_opens", "now": "NOT_YET", "then": "ELIGIBLE"}


def _plant_undertrial(spec: dict[str, Any], k: int, as_of: date) -> dict[str, Any] | None:
    kind, years, _ = parse_max_punishment(str(spec["inputs"]["max_punishment"]))
    first = spec["inputs"].get("first_time")
    if kind != "years" or first is None:
        return None
    third, half = undertrial_thresholds(years or 0)
    threshold = third if first else half
    custody = threshold - k
    if custody < 1:
        return None
    inputs = {**spec["inputs"], "custody_days": custody, "as_of": as_of.isoformat(), "arrest_date": (as_of - timedelta(days=custody)).isoformat()}
    return {"inputs": inputs, "deadline": (as_of + timedelta(days=k)).isoformat(), "kind": "s479_threshold", "now": "NOT_YET", "then": "ELIGIBLE"}


def build_t5(t1_dir: str, t4_dir: str, out_dir: str) -> TestSetManifest:
    """Plant deadlines and record them as truth.

    Args:
        t1_dir: see behaviour
        t4_dir: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.

    Raises:
        ValueError: fewer than 200 T1 cases or fewer than 100 T4 scenarios that can carry a planted deadline.
    """
    rng = random.Random(SEED)
    t1 = load_t1_cases(t1_dir, open_only=False)  # the plan's "200 T1 cases": all of them run; nothing here scores the sealed slice
    if len(t1) < N_T1:
        raise ValueError(f"T5 needs {N_T1} T1 cases, found {len(t1)}")
    scenarios = [s for s in rows_from_file(Path(t4_dir) / "scenarios.jsonl") if not _ha03_scenario(s)]  # the original 500 only: the HA-03 additions never carry a planted deadline
    if len(scenarios) < N_T4:
        raise ValueError(f"T5 needs {N_T4} T4 scenarios, found {len(scenarios)}")
    as_of = date.fromisoformat(AS_OF)
    shuffled = sorted(scenarios, key=lambda s: str(s["id"]))
    rng.shuffle(shuffled)
    ks = [1 + i % WINDOW_DAYS for i in range(N_T4)]
    rng.shuffle(ks)
    planted: list[tuple[dict[str, Any], dict[str, Any]]] = []
    skipped = Counter()
    for spec in shuffled:
        if len(planted) == N_T4:
            break
        planter = _plant_default_bail if spec["rule"] == "default_bail" else _plant_undertrial if spec["rule"] == "undertrial_limit" else None
        got = planter(spec, ks[len(planted)], as_of) if planter else None
        if got is None:
            skipped[spec["rule"]] += 1
            continue
        planted.append((spec, got))
    if len(planted) < N_T4:
        raise ValueError(f"only {len(planted)} T4 scenarios can carry a planted deadline (need {N_T4})")
    names = faker_names(SEED, 2 * N_T4)
    out = Path(out_dir)
    rows: list[dict[str, Any]] = []
    for i, (spec, got) in enumerate(planted):
        case_id = f"t5-{spec['id']}"
        replanted = {**spec, "inputs": got["inputs"]}
        docs, _ = render_scenario_documents(replanted, (names[2 * i], names[2 * i + 1]), i)
        folder = out / "bundles" / case_id
        folder.mkdir(parents=True, exist_ok=True)
        for fname, text in docs.items():
            (folder / fname).write_text(text, encoding="utf-8")
        (folder / "facts.json").write_text(json.dumps({"as_of": AS_OF, **got["inputs"]}, ensure_ascii=False, sort_keys=True, indent=1), encoding="utf-8")
        rows.append({"case_id": case_id, "source": "T4", "scenario_id": spec["id"], "as_of": AS_OF, "deadline": got["deadline"], "deadline_kind": got["kind"],
                     "days_to_deadline": (date.fromisoformat(got["deadline"]) - as_of).days, "designed_answer_now": got["now"],
                     "designed_answer_on_deadline": got["then"], "bundle": f"bundles/{case_id}", "facts": {"as_of": AS_OF, **got["inputs"]}})
    order = sorted((r for r in rows), key=lambda r: (r["deadline"], r["deadline_kind"] != "default_bail_window_opens", r["case_id"]))
    for rank, r in enumerate(order, start=1):
        r["rank"], r["urgent"] = rank, True
    for c in t1:
        rows.append({"case_id": c["case_id"], "source": "T1", "scenario_id": None, "as_of": AS_OF, "deadline": None, "deadline_kind": None, "days_to_deadline": None,
                     "designed_answer_now": None, "designed_answer_on_deadline": None, "bundle": None, "facts": None, "rank": None, "urgent": False})
    rng.shuffle(rows)  # the file order is the FIFO order and mixes planted and background cases
    rows_to_file(out / "cases.jsonl", rows)
    planted_rows = [r for r in rows if r["deadline"]]
    details = {
        "seed": SEED, "as_of": AS_OF, "t1_cases": len(t1), "t4_scenarios_planted": len(planted_rows),
        "deadline_days": dict(sorted(Counter(r["days_to_deadline"] for r in planted_rows).items())), "per_deadline_kind": dict(Counter(r["deadline_kind"] for r in planted_rows)),
        "t4_scenarios_not_plantable": dict(skipped), "fifo_position_of_first_planted": next(i for i, r in enumerate(rows) if r["deadline"]) + 1,
        "gold_ranking": [r["case_id"] for r in order], "urgency_rule": "plan §11: legal deadline first, nearest first; default-bail windows before s.479 on a tie",
        "not_built": [],
    }
    manifest = TestSetManifest(set_id="T5", size=len(rows), answers_from="construction: deadlines planted by re-dating T4 scenarios; gold ranking by the urgency rule",
                               used_for=["F4"], path=str(out), details=details)
    write_manifest(manifest, str(out))
    return manifest


def main(argv: list[str] | None = None) -> int:
    """CLI."""
    from vakeel_sahayak.config import load_config

    base = Path(load_config().paths.testsets_dir)
    ap = argparse.ArgumentParser(description="Build T5 (batch set)")
    ap.add_argument("--t1", default=str(base / "t1"))
    ap.add_argument("--t4", default=str(base / "t4"))
    ap.add_argument("--out", default=str(base / "t5"))
    args = ap.parse_args(argv)
    m = build_t5(args.t1, args.t4, args.out)
    print(json.dumps({"size": m.size, **{k: m.details[k] for k in ("deadline_days", "per_deadline_kind", "t4_scenarios_not_plantable")}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
